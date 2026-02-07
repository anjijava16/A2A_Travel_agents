#!/bin/bash
# Copyright 2025 Amazon.com and its affiliates; all rights reserved.
# This file is Amazon Web Services Content and may not be duplicated or distributed without permission.

#############################################################################
# A2A Workshop - Agent Deployment Script (3-Step Workflow)
#
# This script deploys agents using a 3-step process:
#   Step 1: Deploy resources stack (ECR + CloudWatch Logs)
#   Step 2: Build and push Docker image to ECR
#   Step 3: Deploy service stack (ECS + CloudMap)
#
# This ensures pure Infrastructure-as-Code - all AWS resources created
# via CloudFormation, not AWS CLI.
#
# Features:
#   - Deploy single or multiple agents
#   - Parallel deployment for faster multi-agent deployment
#   - Automatic validation of all agent resources
#   - Deployment summary with success/failure tracking
#
# Usage:
#   ./deploy-agent.sh <agent-name> [<agent-name> ...]
#   ./deploy-agent.sh <agent-name> [<agent-name> ...] --delete
#
# Examples:
#   ./deploy-agent.sh weather-agent
#   ./deploy-agent.sh weather-agent events-agent restaurant-agent budget-agent
#   ./deploy-agent.sh weather-agent --delete
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
TEMPLATE_DIR="static/cloudformation"
PARAMETERS_DIR="static/cloudformation/parameters"
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
Usage: $0 <agent-name> [<agent-name> ...] [OPTIONS]

Deploys one or more agents to AWS ECS Fargate using a 3-step workflow.
Multiple agents will be deployed in parallel for faster deployment.

Available agents:
EOF

    # Dynamically list agents that have both Dockerfile and parameter file
    for dir in services/*/; do
        if [ -d "$dir" ]; then
            local service_name=$(basename "$dir")
            if [ -f "${dir}Dockerfile" ] && [ -f "${PARAMETERS_DIR}/${service_name}.json" ]; then
                echo "  - $service_name"
            fi
        fi
    done

    cat << EOF

Options:
  -h, --help              Show this help message
  -d, --delete            Delete agent stacks (both resources and service)
  -l, --log-level LEVEL   Set log level (DEBUG, INFO, WARNING, ERROR) [default: INFO]

Examples:
  $0 weather-agent                                    # Deploy single agent
  $0 weather-agent events-agent restaurant-agent      # Deploy multiple agents in parallel
  $0 weather-agent --log-level DEBUG                  # Deploy with DEBUG logging
  $0 events-agent --delete                            # Delete single agent
  $0 weather-agent events-agent restaurant-agent -d   # Delete multiple agents in parallel

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

    # Check jq
    if ! command -v jq &> /dev/null; then
        print_error "jq not found. Please install jq (e.g., 'brew install jq' on macOS)."
        exit 1
    fi
    print_success "jq found"

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

validate_agent_resources() {
    local agent_name=$1
    local agent_dir="services/${agent_name}"
    local dockerfile="${agent_dir}/Dockerfile"
    local parameters_file="${PARAMETERS_DIR}/${agent_name}.json"

    print_info "Validating agent resources..."

    # Check if agent directory exists
    if [ ! -d "$agent_dir" ]; then
        print_error "Agent directory not found: $agent_dir"
        echo ""
        echo "Available agents (with Dockerfile and parameters):"

        # List directories in services/ that have both Dockerfile and parameter file
        for dir in services/*/; do
            if [ -d "$dir" ]; then
                local service_name=$(basename "$dir")
                if [ -f "${dir}Dockerfile" ] && [ -f "${PARAMETERS_DIR}/${service_name}.json" ]; then
                    echo "  - $service_name"
                fi
            fi
        done
        exit 1
    fi
    print_success "Agent directory found: $agent_dir"

    # Check if Dockerfile exists
    if [ ! -f "$dockerfile" ]; then
        print_error "Dockerfile not found: $dockerfile"
        echo ""
        echo "Each agent must have a Dockerfile in its directory."
        exit 1
    fi
    print_success "Dockerfile found: $dockerfile"

    # Check if parameter file exists
    if [ ! -f "$parameters_file" ]; then
        print_error "Parameter file not found: $parameters_file"
        echo ""
        echo "Available parameter files:"
        ls -1 "${PARAMETERS_DIR}"/*.json 2>/dev/null | xargs -n1 basename | sed 's/^/  - /'
        exit 1
    fi
    print_success "Parameter file found: $parameters_file"

    print_success "All agent resources validated"
}

#############################################################################
# Step 1: Deploy Resources Stack (ECR + Logs)
#############################################################################

deploy_resources_stack() {
    local agent_name=$1
    local resources_stack="${agent_name}-resources"

    print_header "Step 1: Deploy Resources Stack (ECR + Logs)"

    local template_file="${TEMPLATE_DIR}/agent-resources-template.yaml"

    if [ ! -f "$template_file" ]; then
        print_error "Template file not found: $template_file"
        exit 1
    fi

    # Check if stack exists
    local existing_status=$(aws cloudformation describe-stacks \
        --stack-name "$resources_stack" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "$existing_status" != "NOT_FOUND" ]; then
        print_info "Resources stack already exists: $resources_stack"
        print_success "Skipping resources stack (already deployed)"
        return 0
    fi

    print_info "Creating resources stack: $resources_stack"
    aws cloudformation create-stack \
        --stack-name "$resources_stack" \
        --template-body "file://${template_file}" \
        --parameters \
            ParameterKey=ProjectName,ParameterValue="${PROJECT_NAME}" \
            ParameterKey=Environment,ParameterValue="${ENVIRONMENT}" \
            ParameterKey=AgentName,ParameterValue="${agent_name}" \
        --capabilities CAPABILITY_IAM \
        --tags "Key=Project,Value=${PROJECT_NAME}" "Key=Environment,Value=${ENVIRONMENT}" "Key=Agent,Value=${agent_name}" \
        --region "$AWS_REGION" || {
            print_error "Failed to create resources stack"
            exit 1
        }

    print_info "Waiting for resources stack creation..."
    aws cloudformation wait stack-create-complete \
        --stack-name "$resources_stack" \
        --region "$AWS_REGION" || {
            print_error "Resources stack creation failed"
            exit 1
        }

    print_success "Resources stack created: $resources_stack"
}

#############################################################################
# Step 2: Build and Push Docker Image
#############################################################################

build_and_push_image() {
    local agent_name=$1
    local resources_stack="${agent_name}-resources"

    print_header "Step 2: Build and Push Docker Image"

    # Get ECR repository URI from resources stack
    local ecr_repo_uri=$(aws cloudformation describe-stacks \
        --stack-name "$resources_stack" \
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
        "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com" 2>&1 | grep -v "keychain" | grep -v "Error saving credentials" || true

    # Check if login was successful by testing Docker access
    if ! docker pull "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/a2a-workshop/${agent_name}:latest" 2>/dev/null > /dev/null; then
        # If can't pull, login was successful but image doesn't exist yet - that's fine
        :
    fi
    print_success "ECR authentication successful"

    # Build Docker image
    print_info "Building Docker image..."
    docker build \
        --no-cache \
        --platform linux/amd64 \
        -t "${agent_name}:latest" \
        -t "${ecr_repo_uri}:latest" \
        -f "services/${agent_name}/Dockerfile" \
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
    local agent_name=$1
    local service_stack="${agent_name}-stack"

    print_header "Step 3: Deploy Service Stack (ECS + CloudMap)"

    local template_file="${TEMPLATE_DIR}/agent-service-template.yaml"
    local parameters_file="${PARAMETERS_DIR}/${agent_name}.json"

    if [ ! -f "$template_file" ]; then
        print_error "Template file not found: $template_file"
        exit 1
    fi

    if [ ! -f "$parameters_file" ]; then
        print_error "Parameters file not found: $parameters_file"
        exit 1
    fi

    # Check if stack exists
    local existing_status=$(aws cloudformation describe-stacks \
        --stack-name "$service_stack" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "$existing_status" != "NOT_FOUND" ]; then
        print_info "Service stack already exists - updating: $service_stack"

        # Update LogLevel in parameters
        local temp_params="/tmp/${agent_name}-params-$$.json"
        jq --arg log_level "$LOG_LEVEL" \
            'map(if .ParameterKey == "LogLevel" then .ParameterValue = $log_level else . end)' \
            "$parameters_file" > "$temp_params"

        print_info "Updating service stack: $service_stack"
        aws cloudformation update-stack \
            --stack-name "$service_stack" \
            --template-body "file://${template_file}" \
            --parameters "file://${temp_params}" \
            --capabilities CAPABILITY_IAM \
            --region "$AWS_REGION" 2>&1 | tee /tmp/cfn-update.log
        local update_exit_code=${PIPESTATUS[0]}

        rm -f "$temp_params"

        if [ $update_exit_code -eq 0 ]; then
            print_info "Waiting for service stack update..."
            aws cloudformation wait stack-update-complete \
                --stack-name "$service_stack" \
                --region "$AWS_REGION"

            print_success "Service stack updated: $service_stack"
        else
            if grep -q "No updates are to be performed" /tmp/cfn-update.log; then
                print_info "No CloudFormation changes detected."
                print_info "Forcing ECS service to use new Docker image..."

                # Get ECS cluster name from infrastructure stack
                local infra_stack=$(aws cloudformation describe-stacks \
                    --query 'Stacks[?contains(StackName, `Infrastructure`) || contains(StackName, `infrastructure`)].StackName' \
                    --output text 2>/dev/null | head -n1)

                local ecs_cluster=$(aws cloudformation describe-stacks \
                    --stack-name "$infra_stack" \
                    --query 'Stacks[0].Outputs[?OutputKey==`ECSClusterName`].OutputValue' \
                    --output text 2>/dev/null)

                local ecs_service=$(aws cloudformation describe-stacks \
                    --stack-name "$service_stack" \
                    --query 'Stacks[0].Outputs[?OutputKey==`ECSServiceName`].OutputValue' \
                    --output text 2>/dev/null)

                if [ -n "$ecs_cluster" ] && [ -n "$ecs_service" ]; then
                    aws ecs update-service \
                        --cluster "$ecs_cluster" \
                        --service "$ecs_service" \
                        --force-new-deployment \
                        --region "$AWS_REGION" > /dev/null
                    print_success "Forced new deployment for ECS service"
                fi
                return 0
            else
                print_error "Stack update failed"
                exit 1
            fi
        fi
    else
        # Update LogLevel in parameters
        local temp_params="/tmp/${agent_name}-params-$$.json"
        jq --arg log_level "$LOG_LEVEL" \
            'map(if .ParameterKey == "LogLevel" then .ParameterValue = $log_level else . end)' \
            "$parameters_file" > "$temp_params"

        print_info "Creating service stack: $service_stack"
        aws cloudformation create-stack \
            --stack-name "$service_stack" \
            --template-body "file://${template_file}" \
            --parameters "file://${temp_params}" \
            --capabilities CAPABILITY_IAM \
            --tags "Key=Project,Value=${PROJECT_NAME}" "Key=Environment,Value=${ENVIRONMENT}" "Key=Agent,Value=${agent_name}" \
            --region "$AWS_REGION" || {
                print_error "Service stack creation failed"
                rm -f "$temp_params"
                exit 1
            }

        rm -f "$temp_params"

        print_info "Waiting for service stack creation..."
        aws cloudformation wait stack-create-complete \
            --stack-name "$service_stack" \
            --region "$AWS_REGION" || {
                print_error "Service stack creation failed"
                exit 1
            }

        print_success "Service stack created: $service_stack"
    fi
}

#############################################################################
# Delete Stacks
#############################################################################

delete_stacks() {
    local agent_name=$1
    local resources_stack="${agent_name}-resources"
    local service_stack="${agent_name}-stack"

    print_header "Delete ${agent_name} Stacks"

    # Delete service stack first
    local service_status=$(aws cloudformation describe-stacks \
        --stack-name "$service_stack" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "$service_status" != "NOT_FOUND" ]; then
        print_info "Deleting service stack: $service_stack"
        aws cloudformation delete-stack \
            --stack-name "$service_stack" \
            --region "$AWS_REGION"

        print_info "Waiting for service stack deletion..."
        aws cloudformation wait stack-delete-complete \
            --stack-name "$service_stack" \
            --region "$AWS_REGION"

        print_success "Service stack deleted: $service_stack"
    else
        print_info "Service stack not found: $service_stack"
    fi

    # Delete resources stack (ECR + logs will be retained due to DeletionPolicy)
    local resources_status=$(aws cloudformation describe-stacks \
        --stack-name "$resources_stack" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "$resources_status" != "NOT_FOUND" ]; then
        print_info "Deleting resources stack: $resources_stack"
        aws cloudformation delete-stack \
            --stack-name "$resources_stack" \
            --region "$AWS_REGION"

        print_info "Waiting for resources stack deletion..."
        aws cloudformation wait stack-delete-complete \
            --stack-name "$resources_stack" \
            --region "$AWS_REGION"

        print_success "Resources stack deleted: $resources_stack"
    else
        print_info "Resources stack not found: $resources_stack"
    fi

    print_success "${agent_name} stacks deleted"
}

#############################################################################
# Show Deployment Info
#############################################################################

show_deployment_info() {
    local agent_name=$1
    local resources_stack="${agent_name}-resources"
    local service_stack="${agent_name}-stack"

    print_header "Deployment Complete"

    print_info "CloudMap Service:"
    local cloudmap_name=$(aws cloudformation describe-stacks \
        --stack-name "$service_stack" \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudMapServiceName`].OutputValue' \
        --output text 2>/dev/null || echo "N/A")
    echo "  Service Name: $cloudmap_name"
    echo "  Access: Private (CloudMap only)"
    echo ""

    print_info "ECS Service:"
    local ecs_service=$(aws cloudformation describe-stacks \
        --stack-name "$service_stack" \
        --query 'Stacks[0].Outputs[?OutputKey==`ECSServiceName`].OutputValue' \
        --output text 2>/dev/null || echo "N/A")
    echo "  Service Name: $ecs_service"
    echo ""

    print_info "CloudWatch Logs:"
    local log_group=$(aws cloudformation describe-stacks \
        --stack-name "$resources_stack" \
        --query 'Stacks[0].Outputs[?OutputKey==`LogGroupName`].OutputValue' \
        --output text 2>/dev/null || echo "N/A")
    echo "  Log Group: $log_group"
    echo ""

    print_success "${agent_name} deployed successfully!"
    echo ""
    print_info "Next steps:"
    echo "  1. Deploy other agents as needed"
    echo "  2. Test agent discovery via CloudMap"
    echo "  3. Query the orchestrator to invoke your agent"
}

#############################################################################
# Deploy Single Agent (for parallel execution)
#############################################################################

deploy_single_agent() {
    local agent_name=$1
    local log_file="/tmp/deploy-${agent_name}-$$.log"
    local status_file="/tmp/deploy-${agent_name}-status-$$.txt"

    {
        echo "STARTING" > "$status_file"

        echo "RESOURCES_STACK" > "$status_file"
        deploy_resources_stack "$agent_name"

        echo "DOCKER_BUILD" > "$status_file"
        build_and_push_image "$agent_name"

        echo "SERVICE_STACK" > "$status_file"
        deploy_service_stack "$agent_name"

        echo "COMPLETE" > "$status_file"
        show_deployment_info "$agent_name"
    } > "$log_file" 2>&1

    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        print_success "${agent_name} deployment completed"
        rm -f "$status_file"
        rm -f "$log_file"
        return 0
    else
        print_error "${agent_name} deployment failed - see logs below:"
        cat "$log_file"
        rm -f "$status_file"
        rm -f "$log_file"
        return 1
    fi
}

#############################################################################
# Monitor Deployment Progress
#############################################################################

monitor_deployments() {
    local agent_names=("$@")
    local last_status=""

    while true; do
        local all_done=true
        local current_status=""

        for agent_name in "${agent_names[@]}"; do
            local status_file=$(ls /tmp/deploy-${agent_name}-status-*.txt 2>/dev/null | head -1)

            if [ -f "$status_file" ]; then
                local status=$(cat "$status_file" 2>/dev/null || echo "STARTING")
                all_done=false

                case $status in
                    STARTING)
                        current_status+="  ${agent_name}: Starting...\n"
                        ;;
                    RESOURCES_STACK)
                        current_status+="  ${agent_name}: Deploying resources stack\n"
                        ;;
                    DOCKER_BUILD)
                        current_status+="  ${agent_name}: Building Docker image\n"
                        ;;
                    SERVICE_STACK)
                        current_status+="  ${agent_name}: Creating ECS service\n"
                        ;;
                esac
            else
                # Check if CloudFormation stack exists and show its status
                local service_stack="${agent_name}-stack"
                local stack_status=$(aws cloudformation describe-stacks \
                    --stack-name "$service_stack" \
                    --query 'Stacks[0].StackStatus' \
                    --output text 2>/dev/null || echo "NOT_FOUND")

                if [ "$stack_status" != "NOT_FOUND" ]; then
                    case $stack_status in
                        CREATE_IN_PROGRESS)
                            current_status+="  ${agent_name}: ⏳ Creating service stack...\n"
                            all_done=false
                            ;;
                        CREATE_COMPLETE|UPDATE_COMPLETE)
                            current_status+="  ${agent_name}: ✓ Deployment complete\n"
                            ;;
                        *FAILED*|*ROLLBACK*)
                            current_status+="  ${agent_name}: ✗ Deployment failed\n"
                            ;;
                    esac
                fi
            fi
        done

        # Only print if status changed
        if [ "$current_status" != "$last_status" ] && [ -n "$current_status" ]; then
            clear
            echo ""
            print_header "Deployment Progress"
            echo -e "$current_status"
            last_status="$current_status"
        fi

        if $all_done; then
            break
        fi

        sleep 3
    done
}

#############################################################################
# Main Script
#############################################################################

main() {
    local agent_names=()
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
    echo -e "${BLUE}║      A2A Workshop - Agent Deployment (3-Step Workflow)            ║${NC}"
    echo -e "${BLUE}║                                                                   ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Agents: ${agent_names[*]}"
    echo ""

    # Check prerequisites once
    check_prerequisites
    echo ""

    # Validate all agent resources exist before starting
    print_info "Validating all agent resources..."
    for agent_name in "${agent_names[@]}"; do
        validate_agent_resources "$agent_name"
    done
    print_success "All agent resources validated"
    echo ""

    if [ "$delete_mode" = true ]; then
        # Delete in parallel
        print_info "Deleting ${#agent_names[@]} agent(s) in parallel..."
        local pids=()
        local failed_agents=()

        for agent_name in "${agent_names[@]}"; do
            delete_stacks "$agent_name" &
            pids+=($!)
        done

        # Wait for all deletions to complete
        for i in "${!pids[@]}"; do
            wait "${pids[$i]}"
            if [ $? -ne 0 ]; then
                failed_agents+=("${agent_names[$i]}")
            fi
        done

        echo ""
        if [ ${#failed_agents[@]} -eq 0 ]; then
            print_success "All agents deleted successfully"
        else
            print_error "Failed to delete: ${failed_agents[*]}"
            exit 1
        fi
    else
        check_infrastructure_stack
        echo ""

        # Deploy in parallel if multiple agents
        if [ ${#agent_names[@]} -eq 1 ]; then
            # Single agent - deploy normally
            agent_name="${agent_names[0]}"
            deploy_resources_stack "$agent_name"
            echo ""

            build_and_push_image "$agent_name"
            echo ""

            deploy_service_stack "$agent_name"
            echo ""

            show_deployment_info "$agent_name"
        else
            # Multiple agents - deploy in parallel
            print_info "Deploying ${#agent_names[@]} agents in parallel..."
            echo ""

            local pids=()
            local failed_agents=()

            # Start all deployments in parallel
            for agent_name in "${agent_names[@]}"; do
                print_info "Starting ${agent_name}..."
                deploy_single_agent "$agent_name" &
                pids+=($!)
                sleep 0.5  # Small delay to stagger starts
            done

            echo ""
            print_success "All ${#agent_names[@]} agents started in parallel"
            print_info "Starting real-time progress monitoring..."
            sleep 2

            # Monitor deployments in real-time
            monitor_deployments "${agent_names[@]}" &
            local monitor_pid=$!

            # Wait for all deployments to complete
            for i in "${!pids[@]}"; do
                wait "${pids[$i]}"
                local exit_code=$?

                if [ $exit_code -ne 0 ]; then
                    failed_agents+=("${agent_names[$i]}")
                fi
            done

            # Stop the monitor
            kill $monitor_pid 2>/dev/null || true
            wait $monitor_pid 2>/dev/null || true

            # Final summary
            clear
            echo ""
            print_header "Deployment Summary"
            if [ ${#failed_agents[@]} -eq 0 ]; then
                print_success "All ${#agent_names[@]} agents deployed successfully!"
                echo ""
                print_info "Deployed agents:"
                for agent_name in "${agent_names[@]}"; do
                    echo "  ✓ ${agent_name}"
                done
                echo ""
                print_info "Next steps:"
                echo "  1. View agent logs in CloudWatch"
                echo "  2. Test agent discovery via CloudMap"
                echo "  3. Query the orchestrator to invoke your agents"
            else
                print_warning "Some deployments failed"
                echo ""
                print_info "Successful deployments:"
                for agent_name in "${agent_names[@]}"; do
                    if [[ ! " ${failed_agents[*]} " =~ " ${agent_name} " ]]; then
                        echo "  ✓ ${agent_name}"
                    fi
                done
                echo ""
                print_error "Failed deployments:"
                for agent_name in "${failed_agents[@]}"; do
                    echo "  ✗ ${agent_name}"
                done
                exit 1
            fi
        fi
    fi
}

# Run main function
main "$@"
