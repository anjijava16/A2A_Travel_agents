#!/bin/bash
# Copyright 2025 Amazon.com and its affiliates; all rights reserved.
# This file is Amazon Web Services Content and may not be duplicated or distributed without permission.

#############################################################################
# A2A Workshop - Delete Learner-Created Agent Stacks
#
# This script deletes ONLY the agent stacks created by learners during
# the workshop exercises (hotel-agent, itinerary-agent).
#
# It does NOT delete:
#   - Pre-deployed agents (location-loader, geography-agent, restaurant-agent,
#     weather-agent, budget-agent, events-agent) - These are managed by the
#     main a2a-workshop CloudFormation stack and will be deleted when that
#     stack is deleted
#   - Workshop infrastructure (Code Server, MCP Gateway, Orchestrator, VPC,
#     ECS Cluster, CloudMap, Application Load Balancer)
#
# Use this script to clean up learner-created agents during Chapter 6-7
# exercises while preserving the workshop environment and pre-deployed agents.
#
# To delete the entire workshop infrastructure (including all agents), delete
# the main a2a-workshop CloudFormation stack from the AWS Console.
#
# Usage:
#   ./delete-agents.sh                 # Delete learner-created agent stacks
#   ./delete-agents.sh --dry-run       # Preview what would be deleted
#
#############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: $0 [--dry-run]"
            exit 1
            ;;
    esac
done

# Detect AWS region
export AWS_REGION=${AWS_REGION:-$(aws configure get region 2>/dev/null || echo "us-east-1")}

################################################################################
# Learner-created agents only
#
# These are the agents learners deploy manually during workshop exercises:
#   - hotel-agent (Chapter 6)
#   - itinerary-agent (Chapter 7)
#
# Pre-deployed agents are NOT included here because they are managed by
# the main a2a-workshop CloudFormation stack:
#   - location-loader
#   - geography-agent
#   - restaurant-agent
#   - weather-agent
#   - budget-agent
#   - events-agent
#
# To delete pre-deployed agents, delete the a2a-workshop CloudFormation stack.
################################################################################
AGENT_NAMES=(
  "hotel-agent"
  "itinerary-agent"
)

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  A2A Workshop - Learner-Created Agent Cleanup${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}\n"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}DRY-RUN MODE: No stacks will be deleted${NC}\n"
fi

echo -e "${BLUE}Region: $AWS_REGION${NC}\n"

# Discover existing agent stacks (service and resources)
SERVICE_STACKS=()
RESOURCES_STACKS=()

for agent in "${AGENT_NAMES[@]}"; do
  # Check for service stack
  if aws cloudformation describe-stacks \
      --region "$AWS_REGION" \
      --stack-name "${agent}-stack" &>/dev/null; then
    SERVICE_STACKS+=("${agent}-stack")
  fi

  # Check for resources stack
  if aws cloudformation describe-stacks \
      --region "$AWS_REGION" \
      --stack-name "${agent}-resources" &>/dev/null; then
    RESOURCES_STACKS+=("${agent}-resources")
  fi
done

if [ ${#SERVICE_STACKS[@]} -eq 0 ] && [ ${#RESOURCES_STACKS[@]} -eq 0 ]; then
    echo -e "${YELLOW}No learner-created agent stacks found to delete${NC}"
    echo -e "${BLUE}Note: Pre-deployed agents (location-loader, geography-agent, etc.) are${NC}"
    echo -e "${BLUE}managed by the main a2a-workshop CloudFormation stack.${NC}\n"
    exit 0
fi

if [ ${#SERVICE_STACKS[@]} -gt 0 ]; then
    echo -e "${GREEN}Found ${#SERVICE_STACKS[@]} service stack(s):${NC}"
    for stack in "${SERVICE_STACKS[@]}"; do
        echo -e "  • $stack"
    done
    echo ""
fi

if [ ${#RESOURCES_STACKS[@]} -gt 0 ]; then
    echo -e "${GREEN}Found ${#RESOURCES_STACKS[@]} resources stack(s):${NC}"
    for stack in "${RESOURCES_STACKS[@]}"; do
        echo -e "  • $stack"
    done
    echo ""
fi

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[DRY-RUN] Would delete the above stacks in two phases:${NC}"
    echo -e "${YELLOW}  Phase 1: Service stacks (wait for completion)${NC}"
    echo -e "${YELLOW}  Phase 2: Resources stacks (after service stacks deleted)${NC}"
    exit 0
fi

# Confirm deletion
read -p "Delete these agent stacks? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${BLUE}Deletion cancelled${NC}"
    exit 0
fi

# Phase 1: Delete service stacks (ECS services + CloudMap)
if [ ${#SERVICE_STACKS[@]} -gt 0 ]; then
    echo -e "${BLUE}Phase 1: Deleting service stacks (ECS + CloudMap)...${NC}\n"

    for stack in "${SERVICE_STACKS[@]}"; do
        echo -e "${BLUE}Deleting $stack...${NC}"
        if aws cloudformation delete-stack \
            --region "$AWS_REGION" \
            --stack-name "$stack" 2>/dev/null; then
            echo -e "${GREEN}✓ Deletion initiated for $stack${NC}"
        else
            echo -e "${RED}✗ Failed to initiate deletion for $stack${NC}"
        fi
    done

    echo ""
    echo -e "${BLUE}Waiting for service stacks to complete deletion...${NC}\n"

    # Wait for all service stacks to delete
    for stack in "${SERVICE_STACKS[@]}"; do
        echo -e "${BLUE}Waiting for $stack...${NC}"
        if aws cloudformation wait stack-delete-complete \
            --region "$AWS_REGION" \
            --stack-name "$stack" 2>/dev/null; then
            echo -e "${GREEN}✓ $stack deleted${NC}"
        else
            # Check if stack is actually gone
            if ! aws cloudformation describe-stacks \
                --region "$AWS_REGION" \
                --stack-name "$stack" &>/dev/null; then
                echo -e "${GREEN}✓ $stack deleted${NC}"
            else
                echo -e "${RED}✗ $stack deletion failed${NC}"
            fi
        fi
    done
    echo ""
fi

# Phase 2: Delete resources stacks (ECR + CloudWatch Logs)
if [ ${#RESOURCES_STACKS[@]} -gt 0 ]; then
    echo -e "${BLUE}Phase 2: Deleting resources stacks (ECR + Logs)...${NC}\n"

    for stack in "${RESOURCES_STACKS[@]}"; do
        echo -e "${BLUE}Deleting $stack...${NC}"
        if aws cloudformation delete-stack \
            --region "$AWS_REGION" \
            --stack-name "$stack" 2>/dev/null; then
            echo -e "${GREEN}✓ Deletion initiated for $stack${NC}"
        else
            echo -e "${RED}✗ Failed to initiate deletion for $stack${NC}"
        fi
    done

    echo ""
    echo -e "${BLUE}Waiting for resources stacks to complete deletion...${NC}\n"

    # Wait for all resources stacks to delete
    for stack in "${RESOURCES_STACKS[@]}"; do
        echo -e "${BLUE}Waiting for $stack...${NC}"
        if aws cloudformation wait stack-delete-complete \
            --region "$AWS_REGION" \
            --stack-name "$stack" 2>/dev/null; then
            echo -e "${GREEN}✓ $stack deleted${NC}"
        else
            # Check if stack is actually gone
            if ! aws cloudformation describe-stacks \
                --region "$AWS_REGION" \
                --stack-name "$stack" &>/dev/null; then
                echo -e "${GREEN}✓ $stack deleted${NC}"
            else
                echo -e "${RED}✗ $stack deletion failed${NC}"
            fi
        fi
    done
    echo ""
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Learner-Created Agent Stack Cleanup Complete${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}\n"
echo -e "${BLUE}Pre-deployed agents (location-loader, geography-agent, restaurant-agent,${NC}"
echo -e "${BLUE}weather-agent, budget-agent, events-agent) remain active and are managed${NC}"
echo -e "${BLUE}by the main a2a-workshop CloudFormation stack.${NC}\n"
echo -e "${BLUE}Workshop infrastructure (Code Server, MCP Gateway, Orchestrator, VPC)${NC}"
echo -e "${BLUE}also remains active. To delete everything, delete the a2a-workshop stack${NC}"
echo -e "${BLUE}from the AWS CloudFormation Console.${NC}\n"
