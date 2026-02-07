#!/bin/bash
# Copyright 2025 Amazon.com and its affiliates; all rights reserved.
# This file is Amazon Web Services Content and may not be duplicated or distributed without permission.

#############################################################################
# A2A Workshop - Agent Status Script
#
# This script shows the status of all workshop agents:
#   - Pre-deployed agents (location-loader, geography-agent, etc.)
#   - Learner-created agents (hotel-agent, itinerary-agent)
#
# Status Types:
#   - ENABLED: DesiredCount > 0, tasks running
#   - DISABLED: DesiredCount = 0, no tasks running
#   - NOT_DEPLOYED: Stack doesn't exist
#
# Usage:
#   ./agent-status.sh
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
PROJECT_NAME="a2a"
ENVIRONMENT="workshop"

# Known agents (pre-deployed + learner-created)
PRE_DEPLOYED_AGENTS=(
    "location-loader"
    "geography-agent"
    "restaurant-agent"
    "weather-agent"
    "budget-agent"
    "events-agent"
)

LEARNER_CREATED_AGENTS=(
    "hotel-agent"
    "itinerary-agent"
)

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

#############################################################################
# Status Functions
#############################################################################

find_service_stack() {
    local agent_name=$1

    # Convert agent-name to PascalCase for stack name search
    # e.g., location-loader -> LocationLoader
    local pascal_name=$(echo "$agent_name" | sed -r 's/(^|-)([a-z])/\U\2/g')

    # Search for nested stack
    local stack_name=$(aws cloudformation list-stacks \
        --region "$AWS_REGION" \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE \
        --query "StackSummaries[?contains(StackName, '${pascal_name}ServiceStack')].StackName" \
        --output text 2>/dev/null | head -1)

    echo "$stack_name"
}

check_agent_status() {
    local agent_name=$1
    local stack_name=$(find_service_stack "$agent_name")

    # Check if stack exists
    if [ -z "$stack_name" ]; then
        echo "NOT_DEPLOYED"
        return
    fi

    # Get DesiredCount
    local desired_count=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Parameters[?ParameterKey==`DesiredCount`].ParameterValue' \
        --output text 2>/dev/null || echo "")

    if [ -z "$desired_count" ]; then
        echo "UNKNOWN"
        return
    fi

    if [ "$desired_count" -eq 0 ]; then
        echo "DISABLED"
    else
        # Check if tasks are actually running
        local cluster_name="${PROJECT_NAME}-${ENVIRONMENT}-cluster"
        local service_name="${PROJECT_NAME}-${agent_name}"

        local running_count=$(aws ecs describe-services \
            --cluster "$cluster_name" \
            --services "$service_name" \
            --region "$AWS_REGION" \
            --query 'services[0].runningCount' \
            --output text 2>/dev/null || echo "0")

        if [ "$running_count" -gt 0 ]; then
            echo "ENABLED"
        else
            echo "STARTING"
        fi
    fi
}

format_status() {
    local status=$1

    case $status in
        ENABLED)
            echo -e "${GREEN}●${NC} Enabled  "
            ;;
        DISABLED)
            echo -e "${YELLOW}○${NC} Disabled "
            ;;
        STARTING)
            echo -e "${CYAN}◐${NC} Starting "
            ;;
        NOT_DEPLOYED)
            echo -e "${RED}✗${NC} Not Deployed"
            ;;
        UNKNOWN)
            echo -e "${RED}?${NC} Unknown  "
            ;;
    esac
}

#############################################################################
# Main Script
#############################################################################

main() {
    # Print banner
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                                   ║${NC}"
    echo -e "${BLUE}║              A2A Workshop - Agent Status                          ║${NC}"
    echo -e "${BLUE}║                                                                   ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi

    # Get AWS region
    AWS_REGION=$(get_aws_region)
    print_info "Region: $AWS_REGION"
    echo ""

    # Pre-deployed agents
    print_header "Pre-Deployed Agents"
    printf "%-25s %s\n" "Agent" "Status"
    printf "%-25s %s\n" "-----" "------"

    for agent in "${PRE_DEPLOYED_AGENTS[@]}"; do
        status=$(check_agent_status "$agent")
        formatted_status=$(format_status "$status")
        printf "%-25s %b\n" "$agent" "$formatted_status"
    done

    echo ""

    # Learner-created agents
    print_header "Learner-Created Agents"
    printf "%-25s %s\n" "Agent" "Status"
    printf "%-25s %s\n" "-----" "------"

    for agent in "${LEARNER_CREATED_AGENTS[@]}"; do
        status=$(check_agent_status "$agent")
        formatted_status=$(format_status "$status")
        printf "%-25s %b\n" "$agent" "$formatted_status"
    done

    echo ""

    # Status legend
    print_info "Status Legend:"
    echo -e "  ${GREEN}●${NC} Enabled       - Agent is running and registered in CloudMap"
    echo -e "  ${YELLOW}○${NC} Disabled      - Agent stack exists but DesiredCount=0"
    echo -e "  ${CYAN}◐${NC} Starting      - Agent is starting up (DesiredCount>0 but no tasks yet)"
    echo -e "  ${RED}✗${NC} Not Deployed  - Agent stack does not exist"
    echo ""

    # Quick actions
    print_info "Quick Actions:"
    echo "  Enable an agent:  ./enable-agent.sh <agent-name>"
    echo "  Disable an agent: ./disable-agent.sh <agent-name>"
    echo "  Deploy new agent: ./deploy-agent.sh <agent-name>"
    echo ""
}

# Run main function
main "$@"
