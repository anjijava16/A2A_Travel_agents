#!/bin/bash
# Copyright 2025 Amazon.com and its affiliates; all rights reserved.
# This file is Amazon Web Services Content and may not be duplicated or distributed without permission.

#############################################################################
# A2A Workshop - Orchestrator Deployment Script (3-Step Workflow)
#
# This script deploys the Travel Orchestrator using a 3-step process:
#   Step 1: Deploy resources stack (ECR + CloudWatch Logs)
#   Step 2: Build and push Docker image to ECR
#   Step 3: Deploy service stack (ECS + CloudMap)
#
# This ensures pure Infrastructure-as-Code - all AWS resources created
# via CloudFormation, not AWS CLI.
#
# Usage:
#   ./deploy-orchestrator.sh
#   ./deploy-orchestrator.sh --delete    # Delete both stacks
#
#############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="a2a"
ENVIRONMENT="workshop"
COMPONENT_NAME="orchestrator"
TEMPLATE_DIR="static/cloudformation"
RESOURCES_STACK="${COMPONENT_NAME}-resources"
SERVICE_STACK="${COMPONENT_NAME}-service"
LOG_LEVEL="INFO"

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

get_aws_region() {
    local region=""

    # 1. Check environment variables (highest priority)
    region="${AWS_REGION:-${AWS_DEFAULT_REGION}}"

    # 2. Try EC2 instance metadata (if running on EC2)
    if [ -z "$region" ]; then
        region=$(curl -s --connect-timeout 1 http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || true)
    fi

    # 3. Try aws configure
    if [ -z "$region" ]; then
        region=$(aws configure get region 2>/dev/null || true)
    fi

    # 4. Try to infer from existing CloudFormation stacks
    if [ -z "$region" ]; then
        # Get region from any existing stack
        region=$(aws cloudformation describe-stacks --query 'Stacks[0].StackId' --output text 2>/dev/null | cut -d: -f4 || true)
    fi

    # 5. Default to us-east-1
    region="${region:-us-east-1}"

    echo "$region"
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploys the Travel Orchestrator to AWS ECS Fargate using a 3-step workflow.

Options:
  -h, --help              Show this help message
  -d, --delete            Delete orchestrator stacks (both resources and service)
  -l, --log-level LEVEL   Set log level (DEBUG, INFO, WARNING, ERROR) [default: INFO]

Examples:
  $0                      # Deploy orchestrator (3-step workflow)
  $0 --log-level DEBUG    # Deploy with DEBUG logging
  $0 --delete             # Delete orchestrator stacks

EOF
    exit 1
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

check_infrastructure_stack() {
    print_info "Checking infrastructure stack..."

    # Look for infrastructure stack
    local stack_name=$(aws cloudformation describe-stacks \
        --query 'Stacks[?contains(StackName, `Infrastructure`) || contains(StackName, `infrastructure`)].StackName' \
        --output text 2>/dev/null | head -n1)

    if [ -z "$stack_name" ]; then
        print_error "Infrastructure stack not found"
        echo ""
        echo "The infrastructure stack must be deployed first."
        echo "Please contact the workshop instructor."
        exit 1
    fi

    local stack_status=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "$stack_status" != "CREATE_COMPLETE" ] && [ "$stack_status" != "UPDATE_COMPLETE" ]; then
        print_error "Infrastructure stack is not ready: $stack_status"
        exit 1
    fi

    print_success "Infrastructure stack found: $stack_name"
}

#############################################################################
# Step 1: Deploy Resources Stack (ECR + Logs)
#############################################################################

deploy_resources_stack() {
    print_header "Step 1: Locate Resources Stack (ECR + Logs)"

    # Find nested resources stack from workshop deployment
    RESOURCES_STACK=$(aws cloudformation describe-stacks \
        --query "Stacks[?contains(StackName, 'a2a-workshop') && contains(StackName, 'Orchestrator') && contains(StackName, 'Resources')].StackName" \
        --output text 2>/dev/null | head -n1)

    if [ -z "$RESOURCES_STACK" ]; then
        print_error "Workshop resources stack not found"
        echo "Expected pattern: a2a-workshop-*Orchestrator*Resources*"
        echo "Available stacks:"
        aws cloudformation list-stacks \
            --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
            --query 'StackSummaries[?contains(StackName, `Orchestrator`)].StackName' \
            --output text
        exit 1
    fi

    print_success "Found resources stack: $RESOURCES_STACK"
}

#############################################################################
# Step 2: Build and Push Docker Image
#############################################################################

build_and_push_image() {
    print_header "Step 2: Build and Push Docker Image"

    # Get ECR repository URI from resources stack
    local ecr_repo_uri=$(aws cloudformation describe-stacks \
        --stack-name "$RESOURCES_STACK" \
        --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryUri`].OutputValue' \
        --output text 2>/dev/null)

    if [ -z "$ecr_repo_uri" ]; then
        print_error "Failed to get ECR repository URI from resources stack"
        exit 1
    fi

    print_info "ECR Repository: $ecr_repo_uri"

    # Login to ECR
    print_info "Authenticating with Amazon ECR..."
    aws ecr get-login-password --region "$AWS_REGION" | \
        docker login --username AWS --password-stdin \
        "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com" || {
            print_error "ECR authentication failed"
            exit 1
        }
    print_success "ECR authentication successful"

    # Build Docker image
    print_info "Building Docker image..."
    docker build \
        --platform linux/amd64 \
        -t "${COMPONENT_NAME}:latest" \
        -t "${ecr_repo_uri}:latest" \
        -f "services/${COMPONENT_NAME}/Dockerfile" \
        . || {
            print_error "Docker build failed"
            exit 1
        }
    print_success "Docker image built"

    # Push to ECR
    print_info "Pushing image to ECR..."
    docker push "${ecr_repo_uri}:latest" || {
        print_error "Docker push failed"
        exit 1
        }
    print_success "Image pushed to ECR"
}

#############################################################################
# Step 3: Deploy Service Stack (ECS + CloudMap)
#############################################################################

deploy_service_stack() {
    print_header "Step 3: Update Service and Force Deployment"

    # Find nested service stack from workshop deployment
    SERVICE_STACK=$(aws cloudformation describe-stacks \
        --query "Stacks[?contains(StackName, 'a2a-workshop') && contains(StackName, 'Orchestrator') && contains(StackName, 'Service')].StackName" \
        --output text 2>/dev/null | head -n1)

    if [ -z "$SERVICE_STACK" ]; then
        print_error "Workshop service stack not found"
        echo "Expected pattern: a2a-workshop-*Orchestrator*Service*"
        echo "Available stacks:"
        aws cloudformation list-stacks \
            --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
            --query 'StackSummaries[?contains(StackName, `Orchestrator`)].StackName' \
            --output text
        exit 1
    fi

    print_success "Found service stack: $SERVICE_STACK"

    # Get infrastructure stack for ECS cluster info
    local infra_stack=$(aws cloudformation describe-stacks \
        --query 'Stacks[?contains(StackName, `a2a-workshop-Infrastructure`)].StackName' \
        --output text 2>/dev/null | head -n1)

    local ecs_cluster=$(aws cloudformation describe-stacks \
        --stack-name "$infra_stack" \
        --query 'Stacks[0].Outputs[?OutputKey==`ECSClusterName`].OutputValue' \
        --output text 2>/dev/null)

    local ecs_service=$(aws cloudformation describe-stacks \
        --stack-name "$SERVICE_STACK" \
        --query 'Stacks[0].Outputs[?OutputKey==`ECSServiceName`].OutputValue' \
        --output text 2>/dev/null)

    if [ -n "$ecs_cluster" ] && [ -n "$ecs_service" ]; then
        print_info "Forcing ECS service to use new Docker image..."
        print_info "  Cluster: $ecs_cluster"
        print_info "  Service: $ecs_service"
        aws ecs update-service \
            --cluster "$ecs_cluster" \
            --service "$ecs_service" \
            --force-new-deployment \
            --region "$AWS_REGION" > /dev/null
        print_success "Forced new deployment for ECS service: $ecs_service"
        print_info "New tasks will be started with the updated image"
    else
        print_error "Could not find ECS cluster or service info"
        echo "  Cluster: $ecs_cluster"
        echo "  Service: $ecs_service"
        exit 1
    fi
}

#############################################################################
# Delete Stacks
#############################################################################

delete_stacks() {
    print_header "Delete Orchestrator Stacks"

    # Delete service stack first
    local service_status=$(aws cloudformation describe-stacks \
        --stack-name "$SERVICE_STACK" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "$service_status" != "NOT_FOUND" ]; then
        print_info "Deleting service stack: $SERVICE_STACK"
        aws cloudformation delete-stack \
            --stack-name "$SERVICE_STACK" \
            --region "$AWS_REGION"

        print_info "Waiting for service stack deletion..."
        aws cloudformation wait stack-delete-complete \
            --stack-name "$SERVICE_STACK" \
            --region "$AWS_REGION"

        print_success "Service stack deleted: $SERVICE_STACK"
    else
        print_info "Service stack not found: $SERVICE_STACK"
    fi

    # Delete resources stack (ECR + logs will be retained due to DeletionPolicy)
    local resources_status=$(aws cloudformation describe-stacks \
        --stack-name "$RESOURCES_STACK" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "$resources_status" != "NOT_FOUND" ]; then
        print_info "Deleting resources stack: $RESOURCES_STACK"
        aws cloudformation delete-stack \
            --stack-name "$RESOURCES_STACK" \
            --region "$AWS_REGION"

        print_info "Waiting for resources stack deletion..."
        aws cloudformation wait stack-delete-complete \
            --stack-name "$RESOURCES_STACK" \
            --region "$AWS_REGION"

        print_success "Resources stack deleted: $RESOURCES_STACK"
    else
        print_info "Resources stack not found: $RESOURCES_STACK"
    fi

    print_success "Orchestrator stacks deleted"
}

#############################################################################
# Show Deployment Info
#############################################################################

show_deployment_info() {
    print_header "Deployment Complete"

    print_info "CloudMap Service Discovery:"
    local cloudmap_name=$(aws cloudformation describe-stacks \
        --stack-name "$SERVICE_STACK" \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudMapServiceName`].OutputValue' \
        --output text 2>/dev/null || echo "N/A")
    echo "  Service Name: $cloudmap_name"
    echo "  Access: Private (CloudMap only)"
    echo ""

    print_info "ECS Service:"
    local ecs_service=$(aws cloudformation describe-stacks \
        --stack-name "$SERVICE_STACK" \
        --query 'Stacks[0].Outputs[?OutputKey==`ECSServiceName`].OutputValue' \
        --output text 2>/dev/null || echo "N/A")
    echo "  Service Name: $ecs_service"
    echo ""

    print_info "CloudWatch Logs:"
    local log_group=$(aws cloudformation describe-stacks \
        --stack-name "$RESOURCES_STACK" \
        --query 'Stacks[0].Outputs[?OutputKey==`LogGroupName`].OutputValue' \
        --output text 2>/dev/null || echo "N/A")
    echo "  Log Group: $log_group"
    echo ""

    print_success "Orchestrator deployed successfully!"
    echo ""
    print_info "Next steps:"
    echo "  1. Configure MCP Server"
    echo "  2. Deploy specialist agents (weather, events, restaurant)"
}

#############################################################################
# Main Script
#############################################################################

main() {
    local delete_mode=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                ;;
            -d|--delete)
                delete_mode=true
                shift
                ;;
            -l|--log-level)
                LOG_LEVEL="$2"
                shift 2
                ;;
            -*)
                print_error "Unknown option: $1"
                usage
                ;;
            *)
                print_error "Unexpected argument: $1"
                usage
                ;;
        esac
    done

    # Print banner
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                                   ║${NC}"
    echo -e "${BLUE}║      A2A Workshop - Orchestrator Deployment (3-Step Workflow)     ║${NC}"
    echo -e "${BLUE}║                                                                   ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Check prerequisites
    check_prerequisites
    echo ""

    if [ "$delete_mode" = true ]; then
        delete_stacks
    else
        check_infrastructure_stack
        echo ""

        deploy_resources_stack
        echo ""

        build_and_push_image
        echo ""

        deploy_service_stack
        echo ""

        show_deployment_info
    fi
}

# Run main function
main "$@"
