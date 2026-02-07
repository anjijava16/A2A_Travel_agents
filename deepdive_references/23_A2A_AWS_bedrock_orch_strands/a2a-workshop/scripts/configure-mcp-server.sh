#!/bin/bash
# Copyright 2025 Amazon.com and its affiliates; all rights reserved.
# This file is Amazon Web Services Content and may not be duplicated or distributed without permission.

################################################################################
# MCP Server Configuration Script
#
# Automatically configures Claude Code's MCP server with the MCP Gateway URL.
# Gets the MCP Gateway ALB URL from the main CloudFormation stack and writes to ~/.mcp.json
#
# Note: This script is provided for manual configuration if needed. The MCP Gateway
# is pre-deployed and auto-configured during code-server bootstrap. You typically
# don't need to run this script manually.
#
# Usage:
#   ./scripts/configure-mcp-server.sh [stack-name] [region]
#
# Example:
#   ./scripts/configure-mcp-server.sh a2a us-east-1
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
STACK_NAME="${1:-a2a-workshop}"
AWS_REGION="${2:-${AWS_REGION:-$(aws configure get region 2>/dev/null || echo "us-east-1")}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSHOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MCP_CONFIG_FILE="${WORKSHOP_DIR}/.mcp.json"
SERVER_NAME="a2a-workshop"

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}" >&2
}

print_header() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_header "MCP Server Configuration"

# Check prerequisites
print_info "Checking prerequisites..."

if ! command -v aws &> /dev/null; then
    print_error "AWS CLI not found. Please install AWS CLI."
    exit 1
fi
print_success "AWS CLI found"

if ! command -v jq &> /dev/null; then
    print_error "jq not found. Please install jq: sudo apt-get install jq"
    exit 1
fi
print_success "jq found"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured. Run 'aws configure' first."
    exit 1
fi
print_success "AWS credentials configured"
print_info "Using AWS region: ${AWS_REGION}"

# Get MCP Gateway URL from CloudFormation
print_info "Retrieving MCP Gateway URL from main CloudFormation stack..."

GATEWAY_URL=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query 'Stacks[0].Outputs[?OutputKey==`MCPGatewayURL`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -z "$GATEWAY_URL" ] || [ "$GATEWAY_URL" == "None" ]; then
    print_error "Could not retrieve MCP Gateway URL from CloudFormation stack: ${STACK_NAME}"
    echo ""
    echo "Possible causes:"
    echo "  1. Main stack '${STACK_NAME}' not found (default: 'a2a-workshop')"
    echo "  2. Wrong AWS region (using: ${AWS_REGION})"
    echo "  3. MCP Gateway not yet deployed in the main stack"
    echo ""
    echo "Note: The MCP Gateway is pre-deployed as part of the main workshop stack."
    echo "If you're deploying standalone, ensure the main stack deployment completed."
    echo ""
    echo "Usage:"
    echo "  ./scripts/configure-mcp-server.sh [stack-name] [region]"
    echo ""
    echo "Example:"
    echo "  ./scripts/configure-mcp-server.sh a2a-workshop us-east-1"
    exit 1
fi

print_success "MCP Gateway URL: ${GATEWAY_URL}"

# Create MCP config directory if it doesn't exist
print_info "Preparing MCP configuration..."
mkdir -p "$(dirname "${MCP_CONFIG_FILE}")"

# Check if config file exists and has content
if [ -f "${MCP_CONFIG_FILE}" ]; then
    print_warning "Existing MCP config found at: ${MCP_CONFIG_FILE}"

    # Backup existing config
    BACKUP_FILE="${MCP_CONFIG_FILE}.backup.$(date +%Y%m%d-%H%M%S)"
    cp "${MCP_CONFIG_FILE}" "${BACKUP_FILE}"
    print_info "Backed up to: ${BACKUP_FILE}"

    # Check if our server already exists
    EXISTING_SERVER=$(jq -r ".mcpServers.\"${SERVER_NAME}\" // empty" "${MCP_CONFIG_FILE}" 2>/dev/null || echo "")

    if [ -n "$EXISTING_SERVER" ]; then
        print_info "Updating existing '${SERVER_NAME}' MCP server configuration"

        # Update existing server config
        jq ".mcpServers.\"${SERVER_NAME}\" = {type: \"http\", url: \"${GATEWAY_URL}\", timeout: 60000}" "${MCP_CONFIG_FILE}" > "${MCP_CONFIG_FILE}.tmp"
        mv "${MCP_CONFIG_FILE}.tmp" "${MCP_CONFIG_FILE}"
    else
        print_info "Adding new '${SERVER_NAME}' MCP server to existing configuration"

        # Add new server to existing config (CloudFormation GatewayURL already includes /mcp)
        jq ".mcpServers.\"${SERVER_NAME}\" = {type: \"http\", url: \"${GATEWAY_URL}\", timeout: 60000}" "${MCP_CONFIG_FILE}" > "${MCP_CONFIG_FILE}.tmp"
        mv "${MCP_CONFIG_FILE}.tmp" "${MCP_CONFIG_FILE}"
    fi
else
    print_info "Creating new MCP configuration file"

    # Create new config file (CloudFormation GatewayURL already includes /mcp)
    cat > "${MCP_CONFIG_FILE}" <<EOF
{
  "mcpServers": {
    "${SERVER_NAME}": {
      "type": "http",
      "url": "${GATEWAY_URL}",
      "timeout": 60000
    }
  }
}
EOF
fi

# Validate JSON
if ! jq empty "${MCP_CONFIG_FILE}" 2>/dev/null; then
    print_error "Invalid JSON in MCP config file"
    if [ -f "${BACKUP_FILE}" ]; then
        print_warning "Restoring from backup..."
        cp "${BACKUP_FILE}" "${MCP_CONFIG_FILE}"
    fi
    exit 1
fi

print_success "MCP configuration updated successfully!"

# Display configuration
print_header "MCP Configuration Summary"

echo "Config file: ${MCP_CONFIG_FILE}"
echo ""
echo "Server name: ${SERVER_NAME}"
echo "Gateway URL: ${GATEWAY_URL}"
echo "Timeout: 60000ms (60 seconds)"
echo ""

print_info "Full configuration:"
jq . "${MCP_CONFIG_FILE}"

print_header "Next Steps"

echo "1. Restart Claude Code to load the new configuration"
echo "   (Close and reopen the Claude Code application)"
echo ""
echo "2. Verify MCP server connection in Claude Code:"
echo "   /mcp list"
echo ""
echo "3. Test the MCP server:"
echo "   /mcp call ask_workshop \"What's the weather in Seattle?\""
echo ""

print_success "Configuration complete!"
