#!/bin/bash
# Copyright 2025 Amazon.com and its affiliates; all rights reserved.
# This file is Amazon Web Services Content and may not be duplicated or distributed without permission.

#############################################################################
# A2A Workshop - Agent Disablement Script
#
# This script disables agents by setting DesiredCount=0.
# Useful for workshop reset or resource conservation.
#
# Key Features:
#   - Fast agent shutdown (~30 seconds)
#   - CloudMap deregistration happens automatically
#   - Idempotent (safe to run multiple times)
#   - Supports disabling multiple agents at once
#
# Prerequisites:
#   - Agent stack must exist in CloudFormation
#   - Agent must have DesiredCount > 0 (if already stopped, script shows status)
#
# Usage:
#   ./disable-agent.sh <agent-name> [<agent-name> ...]
#
# Examples:
#   ./disable-agent.sh location-loader
#   ./disable-agent.sh restaurant-agent events-agent
#   ./disable-agent.sh weather-agent
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
Usage: $0 <agent-name> [<agent-name> ...]

Disables agents by setting DesiredCount=0.
Tasks stop and deregister from CloudMap automatically.

This script works with any agent that has been deployed or enabled.

Examples:
  $0 location-loader
  $0 restaurant-agent events-agent
  $0 weather-agent

To enable an agent again:
  ./enable-agent.sh <agent-name>

Options:
  -h, --help    Show this help message

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

    # Search for nested stack
    local stack_name=$(aws cloudformation list-stacks \
        --region "$AWS_REGION" \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE \
        --query "StackSummaries[?contains(StackName, '${pascal_name}ServiceStack')].StackName" \
        --output text 2>/dev/null | head -1)

    echo "$stack_name"
}

check_stack_exists() {
    local agent_name=$1
    local stack_name=$(find_service_stack "$agent_name")

    if [ -z "$stack_name" ]; then
        return 1
    fi
    return 0
}

get_stack_desired_count() {
    local agent_name=$1
    local stack_name=$(find_service_stack "$agent_name")

    if [ -z "$stack_name" ]; then
        echo ""
        return 1
    fi

    # Get DesiredCount parameter from stack
    local desired_count=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Parameters[?ParameterKey==`DesiredCount`].ParameterValue' \
        --output text 2>/dev/null || echo "")

    echo "$desired_count"
}

#############################################################################
# Disable Agent
#############################################################################

disable_single_agent() {
    local agent_name=$1
    local stack_name=$(find_service_stack "$agent_name")

    print_header "Disabling ${agent_name}"

    # Check if stack exists
    if [ -z "$stack_name" ]; then
        print_error "Stack not found for agent: $agent_name"
        echo ""
        echo "This agent has not been deployed."
        echo ""
        return 1
    fi

    print_success "Stack found: $stack_name"

    # Get current DesiredCount
    local current_desired_count=$(get_stack_desired_count "$agent_name")

    if [ -z "$current_desired_count" ]; then
        print_error "Could not determine DesiredCount for $agent_name"
        return 1
    fi

    print_info "Current DesiredCount: $current_desired_count"

    # Check if already disabled
    if [ "$current_desired_count" -eq 0 ]; then
        print_warning "$agent_name is already disabled (DesiredCount=0)"
        echo ""
        echo "The agent is already stopped. No action needed."
        echo ""
        return 0
    fi

    # Update stack to DesiredCount=0
    print_info "Updating stack to disable agent (DesiredCount=0)..."

    aws cloudformation update-stack \
        --stack-name "$stack_name" \
        --region "$AWS_REGION" \
        --use-previous-template \
        --parameters \
            ParameterKey=ProjectName,UsePreviousValue=true \
            ParameterKey=Environment,UsePreviousValue=true \
            ParameterKey=AgentName,UsePreviousValue=true \
            ParameterKey=AgentType,UsePreviousValue=true \
            ParameterKey=AgentPort,UsePreviousValue=true \
            ParameterKey=ContainerImage,UsePreviousValue=true \
            ParameterKey=ContainerCpu,UsePreviousValue=true \
            ParameterKey=ContainerMemory,UsePreviousValue=true \
            ParameterKey=DesiredCount,ParameterValue=0 \
            ParameterKey=LogLevel,UsePreviousValue=true \
        --capabilities CAPABILITY_IAM \
        2>&1 | tee /tmp/cfn-update-$agent_name.log

    local update_exit_code=${PIPESTATUS[0]}

    if [ $update_exit_code -ne 0 ]; then
        if grep -q "No updates are to be performed" /tmp/cfn-update-$agent_name.log; then
            print_warning "Stack is already in desired state"
            rm -f /tmp/cfn-update-$agent_name.log
            return 0
        else
            print_error "Failed to update stack"
            rm -f /tmp/cfn-update-$agent_name.log
            return 1
        fi
    fi

    rm -f /tmp/cfn-update-$agent_name.log

    print_info "Waiting for stack update to complete..."
    print_info "This typically takes ~30 seconds (ECS task shutdown + CloudMap deregistration)"

    if ! aws cloudformation wait stack-update-complete \
        --stack-name "$stack_name" \
        --region "$AWS_REGION"; then
        print_error "Stack update failed or timed out"
        return 1
    fi

    print_success "Agent disabled successfully!"

    echo ""
    print_info "The agent task has been stopped and deregistered from CloudMap."
    print_info "To enable the agent again: ./enable-agent.sh $agent_name"
    echo ""

    return 0
}

#############################################################################
# Main Script
#############################################################################

main() {
    local agent_names=()

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                ;;
            -*)
                print_error "Unknown option: $1"
                usage
                ;;
            *)
                agent_names+=("$1")
                shift
                ;;
        esac
    done

    # Validate at least one agent name provided
    if [ ${#agent_names[@]} -eq 0 ]; then
        print_error "At least one agent name is required"
        echo ""
        usage
    fi

    # Print banner
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                                   ║${NC}"
    echo -e "${BLUE}║             A2A Workshop - Disable Agents                         ║${NC}"
    echo -e "${BLUE}║                                                                   ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Agents to disable: ${agent_names[*]}"
    echo ""

    # Check prerequisites once
    check_prerequisites
    echo ""

    # Disable agents (sequentially to avoid CloudFormation throttling)
    local failed_agents=()

    for agent_name in "${agent_names[@]}"; do
        if ! disable_single_agent "$agent_name"; then
            failed_agents+=("$agent_name")
        fi
    done

    # Final summary
    echo ""
    print_header "Summary"

    if [ ${#failed_agents[@]} -eq 0 ]; then
        print_success "All ${#agent_names[@]} agent(s) disabled successfully!"
        echo ""
        print_info "Next steps:"
        echo "  1. To enable an agent again: ./enable-agent.sh <agent-name>"
        echo "  2. To permanently delete custom agents: ./delete-agents.sh"
        echo ""
    else
        print_warning "Some agents failed to disable"
        echo ""
        print_info "Successfully disabled:"
        for agent_name in "${agent_names[@]}"; do
            if [[ ! " ${failed_agents[*]} " =~ " ${agent_name} " ]]; then
                echo "  ✓ ${agent_name}"
            fi
        done
        echo ""
        print_error "Failed to disable:"
        for agent_name in "${failed_agents[@]}"; do
            echo "  ✗ ${agent_name}"
        done
        echo ""
        exit 1
    fi
}

# Run main function
main "$@"
