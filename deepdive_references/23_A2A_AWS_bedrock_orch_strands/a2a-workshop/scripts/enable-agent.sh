#!/bin/bash
# Copyright 2025 Amazon.com and its affiliates; all rights reserved.
# This file is Amazon Web Services Content and may not be duplicated or distributed without permission.

#############################################################################
# A2A Workshop - Agent Enablement Script
#
# This script enables pre-deployed agents by setting DesiredCount=1.
# Works with ANY agent stack that exists with DesiredCount=0.
#
# Key Features:
#   - Fast agent startup (~60-90 seconds vs ~5 minutes with deploy-agent.sh)
#   - Works with pre-deployed agents (location-loader, geography-agent, etc.)
#   - Works with learner-created agents (hotel-agent, itinerary-agent) after deployment
#   - Idempotent (safe to run multiple times)
#   - Supports enabling multiple agents at once
#
# Prerequisites:
#   - Agent stack must already exist in CloudFormation
#   - Agent must have DesiredCount=0 (or script will show current status)
#
# Usage:
#   ./enable-agent.sh <agent-name> [<agent-name> ...]
#
# Examples:
#   ./enable-agent.sh location-loader
#   ./enable-agent.sh restaurant-agent events-agent
#   ./enable-agent.sh weather-agent
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

Enables pre-deployed agents by setting DesiredCount=1.

This script works with:
  - Pre-deployed agents (location-loader, geography-agent, restaurant-agent,
    weather-agent, budget-agent, events-agent)
  - Learner-created agents (hotel-agent, itinerary-agent) after they've been
    deployed with deploy-agent.sh

Prerequisites:
  - Agent CloudFormation stack must exist (e.g., location-loader-stack)
  - Agent must have DesiredCount=0 (if already running, script shows status)

Examples:
  $0 location-loader
  $0 restaurant-agent events-agent
  $0 weather-agent

To deploy a NEW agent from scratch, use:
  ./deploy-agent.sh <agent-name>

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
    local stack_pattern="*${pascal_name}ServiceStack*"

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
# Enable Agent
#############################################################################

enable_single_agent() {
    local agent_name=$1
    local stack_name=$(find_service_stack "$agent_name")

    print_header "Enabling ${agent_name}"

    # Check if stack exists
    if [ -z "$stack_name" ]; then
        print_error "Stack not found for agent: $agent_name"
        echo ""
        echo "This agent has not been deployed yet."
        echo "To deploy a new agent, use: ./deploy-agent.sh $agent_name"
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

    # Check if already enabled
    if [ "$current_desired_count" -gt 0 ]; then
        print_warning "$agent_name is already enabled (DesiredCount=$current_desired_count)"
        echo ""
        echo "The agent is already running. No action needed."
        echo ""
        return 0
    fi

    # Update stack to DesiredCount=1
    print_info "Updating stack to enable agent (DesiredCount=1)..."

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
            ParameterKey=DesiredCount,ParameterValue=1 \
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

    # Custom wait loop with 5-second polling interval
    local max_wait=300  # 5 minutes timeout
    local elapsed=0
    local poll_interval=5

    while [ $elapsed -lt $max_wait ]; do
        local status=$(aws cloudformation describe-stacks \
            --stack-name "$stack_name" \
            --region "$AWS_REGION" \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null)

        case "$status" in
            UPDATE_COMPLETE)
                echo ""  # New line after progress dots
                print_success "Stack update complete"
                break
                ;;
            UPDATE_ROLLBACK_COMPLETE|UPDATE_ROLLBACK_FAILED|UPDATE_FAILED)
                echo ""
                print_error "Stack update failed with status: $status"
                return 1
                ;;
            UPDATE_IN_PROGRESS|UPDATE_COMPLETE_CLEANUP_IN_PROGRESS)
                echo -n "."
                sleep $poll_interval
                elapsed=$((elapsed + poll_interval))
                ;;
            *)
                echo ""
                print_error "Unexpected stack status: $status"
                return 1
                ;;
        esac
    done

    if [ $elapsed -ge $max_wait ]; then
        echo ""
        print_error "Stack update timed out after ${max_wait} seconds"
        return 1
    fi

    print_success "Agent enabled successfully!"

    # Show CloudMap info
    local cloudmap_name=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudMapServiceName`].OutputValue' \
        --output text 2>/dev/null || echo "N/A")

    echo ""
    print_info "CloudMap Service: $cloudmap_name"
    print_info "The orchestrator will discover this agent on the next request."
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
    echo -e "${BLUE}║          A2A Workshop - Enable Pre-Deployed Agents                ║${NC}"
    echo -e "${BLUE}║                                                                   ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Agents to enable: ${agent_names[*]}"
    echo ""

    # Check prerequisites once
    check_prerequisites
    echo ""

    # Enable agents in parallel for faster startup
    local failed_agents=()
    local pids=()
    local agent_statuses=()

    # Start all stack updates in parallel
    for agent_name in "${agent_names[@]}"; do
        enable_single_agent "$agent_name" &
        pids+=($!)
        agent_statuses+=("$agent_name:pending")
    done

    # Wait for all background processes to complete
    local index=0
    for pid in "${pids[@]}"; do
        if wait $pid; then
            agent_statuses[$index]="${agent_names[$index]}:success"
        else
            agent_statuses[$index]="${agent_names[$index]}:failed"
            failed_agents+=("${agent_names[$index]}")
        fi
        ((index++))
    done

    # Final summary
    echo ""
    print_header "Summary"

    if [ ${#failed_agents[@]} -eq 0 ]; then
        print_success "All ${#agent_names[@]} agent(s) enabled successfully!"
        echo ""
        print_info "Next steps:"
        echo "  1. Test the agent(s) by sending requests to the orchestrator"
        echo "  2. View agent logs in CloudWatch"
        echo "  3. To disable an agent: ./disable-agent.sh <agent-name>"
        echo ""
    else
        print_warning "Some agents failed to enable"
        echo ""
        print_info "Successfully enabled:"
        for agent_name in "${agent_names[@]}"; do
            if [[ ! " ${failed_agents[*]} " =~ " ${agent_name} " ]]; then
                echo "  ✓ ${agent_name}"
            fi
        done
        echo ""
        print_error "Failed to enable:"
        for agent_name in "${failed_agents[@]}"; do
            echo "  ✗ ${agent_name}"
        done
        echo ""
        exit 1
    fi
}

# Run main function
main "$@"
