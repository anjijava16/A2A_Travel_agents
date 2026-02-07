#!/bin/bash
# Copyright 2025 Amazon.com and its affiliates; all rights reserved.
# This file is Amazon Web Services Content and may not be duplicated or distributed without permission.

#############################################################################
# A2A Workshop - Update Agent Script
#
# This script rebuilds a Docker image, pushes to ECR, and restarts the
# ECS service to deploy the updated code. Useful for rapid iteration during
# development.
#
# Usage:
#   ./update-agent.sh <agent-name>
#
# Example:
#   ./update-agent.sh hotel-agent
#
# What it does:
#   1. Finds the agent's CloudFormation stack
#   2. Gets the ECR repository URI from stack outputs
#   3. Builds the Docker image with latest code
#   4. Pushes the new image to ECR
#   5. Forces ECS service to restart with new image
#
# Prerequisites:
#   - AWS CLI installed and configured
#   - Docker installed and running
#   - Agent already deployed (use deploy-agent.sh first)
#
#############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="${PROJECT_NAME:-a2a-workshop}"
ENVIRONMENT="${ENVIRONMENT:-workshop}"

#############################################################################
# Helper Functions
#############################################################################

print_error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_header() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

usage() {
    cat << EOF
Usage: $0 <agent-name>

Rebuilds Docker image, pushes to ECR, and restarts ECS service.

Examples:
  $0 hotel-agent
  $0 location-loader
  $0 weather-agent

Prerequisites:
  - Agent already deployed (use deploy-agent.sh first)
  - AWS CLI installed and configured
  - Docker installed and running

What this script does:
  1. Finds agent's CloudFormation stack
  2. Builds Docker image with latest code
  3. Pushes image to ECR
  4. Forces ECS service restart to pick up new image

EOF
    exit 1
}

get_aws_region() {
    local region=""

    # Try AWS_REGION env var
    region="${AWS_REGION:-}"

    # Try AWS_DEFAULT_REGION env var
    region="${region:-${AWS_DEFAULT_REGION:-}}"

    # Try aws configure
    if [ -z "$region" ]; then
        region=$(aws configure get region 2>/dev/null || echo "")
    fi

    # Default to us-east-1
    region="${region:-us-east-1}"

    echo "$region"
}

#############################################################################
# Validation Functions
#############################################################################

check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi
    print_success "AWS CLI found"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Please install Docker."
        exit 1
    fi
    print_success "Docker found"

    # Check Docker daemon
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi
    print_success "Docker daemon running"

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi
    print_success "AWS credentials configured"

    # Get AWS info
    AWS_REGION=$(get_aws_region)
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    print_success "AWS region: $AWS_REGION"
    print_success "AWS Account ID: $AWS_ACCOUNT_ID"
}

find_service_stack() {
    local agent_name=$1

    # Convert agent-name to PascalCase for stack name search
    # e.g., location-loader -> LocationLoader
    local pascal_name=$(echo "$agent_name" | sed -r 's/(^|-)([a-z])/\U\2/g')

    # Search for nested stack (ServiceStack for pre-deployed agents)
    local stack_name=$(aws cloudformation list-stacks \
        --region "$AWS_REGION" \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE \
        --query "StackSummaries[?contains(StackName, '${pascal_name}ServiceStack')].StackName" \
        --output text 2>/dev/null | head -1)

    # If not found, try standalone stack (learner-created agents)
    if [ -z "$stack_name" ]; then
        stack_name="${agent_name}-stack"
        if ! aws cloudformation describe-stacks \
            --stack-name "$stack_name" \
            --region "$AWS_REGION" &>/dev/null; then
            stack_name=""
        fi
    fi

    echo "$stack_name"
}

find_resources_stack() {
    local agent_name=$1

    # Convert agent-name to PascalCase for stack name search
    local pascal_name=$(echo "$agent_name" | sed -r 's/(^|-)([a-z])/\U\2/g')

    # Search for nested resources stack
    local stack_name=$(aws cloudformation list-stacks \
        --region "$AWS_REGION" \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE \
        --query "StackSummaries[?contains(StackName, '${pascal_name}ResourcesStack')].StackName" \
        --output text 2>/dev/null | head -1)

    # If not found, try standalone resources stack (learner-created agents)
    if [ -z "$stack_name" ]; then
        stack_name="${agent_name}-resources"
        if ! aws cloudformation describe-stacks \
            --stack-name "$stack_name" \
            --region "$AWS_REGION" &>/dev/null; then
            stack_name=""
        fi
    fi

    echo "$stack_name"
}

validate_agent() {
    local agent_name=$1

    # Check if Dockerfile exists
    if [ ! -f "services/${agent_name}/Dockerfile" ]; then
        print_error "Dockerfile not found: services/${agent_name}/Dockerfile"
        echo ""
        echo "Available agents:"
        ls -1 services/ | grep -v "^mcp-gateway$" | grep -v "^orchestrator$"
        echo ""
        exit 1
    fi

    # Check if stack exists
    local stack_name=$(find_service_stack "$agent_name")
    if [ -z "$stack_name" ]; then
        print_error "Agent stack not found: $agent_name"
        echo ""
        echo "This agent has not been deployed yet."
        echo "To deploy a new agent, use: ./deploy-agent.sh $agent_name"
        echo ""
        exit 1
    fi

    print_success "Agent validated: $agent_name"
}

#############################################################################
# Update Functions
#############################################################################

get_ecr_repository() {
    local agent_name=$1
    local resources_stack=$(find_resources_stack "$agent_name")

    if [ -z "$resources_stack" ]; then
        print_error "Resources stack not found for $agent_name"
        return 1
    fi

    # Get ECR repository URI from resources stack outputs
    local ecr_uri=$(aws cloudformation describe-stacks \
        --stack-name "$resources_stack" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
        --output text 2>/dev/null)

    if [ -z "$ecr_uri" ]; then
        print_error "Could not find ECR repository URI in stack outputs"
        return 1
    fi

    echo "$ecr_uri"
}

get_ecs_service_name() {
    local agent_name=$1
    local service_stack=$(find_service_stack "$agent_name")

    if [ -z "$service_stack" ]; then
        print_error "Service stack not found for $agent_name"
        return 1
    fi

    # Get ECS service name from stack outputs
    local service_name=$(aws cloudformation describe-stacks \
        --stack-name "$service_stack" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ServiceName`].OutputValue' \
        --output text 2>/dev/null)

    # If not in outputs, construct from naming convention
    if [ -z "$service_name" ]; then
        service_name="${PROJECT_NAME}-${agent_name}"
    fi

    echo "$service_name"
}

build_and_push_image() {
    local agent_name=$1
    local ecr_uri=$2

    print_header "Building Docker Image"

    print_info "Agent: $agent_name"
    print_info "Dockerfile: services/${agent_name}/Dockerfile"
    print_info "ECR Repository: $ecr_uri"

    # Authenticate with ECR
    print_info "Authenticating with ECR..."
    aws ecr get-login-password --region "$AWS_REGION" | \
        docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    print_success "ECR authentication successful"

    # Build image
    print_info "Building Docker image..."
    if ! docker build \
        --platform linux/amd64 \
        -t "${agent_name}:latest" \
        -f "services/${agent_name}/Dockerfile" \
        . ; then
        print_error "Docker build failed"
        return 1
    fi
    print_success "Docker image built"

    # Tag image
    print_info "Tagging image..."
    docker tag "${agent_name}:latest" "${ecr_uri}:latest"
    print_success "Image tagged"

    # Push image
    print_info "Pushing image to ECR..."
    if ! docker push "${ecr_uri}:latest"; then
        print_error "Docker push failed"
        return 1
    fi
    print_success "Image pushed to ECR"

    return 0
}

restart_ecs_service() {
    local agent_name=$1

    print_header "Restarting ECS Service"

    local cluster_name="${PROJECT_NAME}-${ENVIRONMENT}-cluster"
    local service_name=$(get_ecs_service_name "$agent_name")

    if [ -z "$service_name" ]; then
        print_error "Could not determine ECS service name"
        return 1
    fi

    print_info "Cluster: $cluster_name"
    print_info "Service: $service_name"

    # Force new deployment to pick up new image
    print_info "Forcing new deployment..."
    if ! aws ecs update-service \
        --cluster "$cluster_name" \
        --service "$service_name" \
        --region "$AWS_REGION" \
        --force-new-deployment \
        --no-cli-pager > /dev/null; then
        print_error "Failed to force new deployment"
        return 1
    fi
    print_success "New deployment triggered"

    # Wait for service to stabilize
    print_info "Waiting for service to stabilize (this may take 2-3 minutes)..."
    if ! aws ecs wait services-stable \
        --cluster "$cluster_name" \
        --services "$service_name" \
        --region "$AWS_REGION"; then
        print_warning "Service did not stabilize within timeout"
        echo ""
        echo "The service may still be deploying. Check ECS console for status."
        return 1
    fi
    print_success "Service is stable"

    return 0
}

#############################################################################
# Main Script
#############################################################################

main() {
    # Print banner
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                                   ║${NC}"
    echo -e "${BLUE}║          A2A Workshop - Update Agent                              ║${NC}"
    echo -e "${BLUE}║                                                                   ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Check arguments
    if [ $# -lt 1 ]; then
        usage
    fi

    local agent_name=$1

    # Show usage on help flag
    if [ "$agent_name" == "-h" ] || [ "$agent_name" == "--help" ]; then
        usage
    fi

    print_info "Agent to update: $agent_name"
    echo ""

    # Check prerequisites
    check_prerequisites
    echo ""

    # Validate agent
    validate_agent "$agent_name"
    echo ""

    # Get ECR repository
    print_info "Finding ECR repository..."
    local ecr_uri=$(get_ecr_repository "$agent_name")
    if [ -z "$ecr_uri" ]; then
        print_error "Could not find ECR repository for $agent_name"
        exit 1
    fi
    print_success "ECR repository found: $ecr_uri"
    echo ""

    # Build and push image
    if ! build_and_push_image "$agent_name" "$ecr_uri"; then
        print_error "Failed to build and push image"
        exit 1
    fi
    echo ""

    # Restart ECS service
    if ! restart_ecs_service "$agent_name"; then
        print_error "Failed to restart ECS service"
        exit 1
    fi
    echo ""

    # Success message
    print_header "Update Complete"
    print_success "Agent updated successfully: $agent_name"
    echo ""
    print_info "Next steps:"
    echo "  1. Check ECS console to verify new task is running"
    echo "  2. Check CloudWatch Logs for any startup issues"
    echo "  3. Test the agent by sending a request to the orchestrator"
    echo ""
}

# Run main function
main "$@"
