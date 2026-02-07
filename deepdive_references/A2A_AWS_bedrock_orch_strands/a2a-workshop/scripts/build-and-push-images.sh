#!/bin/bash
set -e

################################################################################
# A2A Workshop - Build and Push Docker Images
#
# IMPORTANT: This script only builds and pushes images. It does NOT create
# ECR repositories. ECR repositories must be created first via CloudFormation
# resource stacks using the individual deployment scripts:
#
#   ./scripts/deploy-orchestrator.sh
#   ./scripts/deploy-mcp-gateway.sh
#   ./scripts/deploy-agent.sh <agent-name>
#
# Each deployment script follows a 3-step workflow:
#   1. Deploy resources stack (creates ECR + logs via CloudFormation)
#   2. Build and push Docker image (this script or individual builds)
#   3. Deploy service stack (creates ECS service)
#
# This script is typically used for bulk rebuilds when all resource stacks
# already exist.
################################################################################

echo "════════════════════════════════════════════════════════════════"
echo "A2A Workshop - Build and Push Docker Images"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Get AWS account info
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION="us-east-1"  # Fixed to us-east-1 for this workshop
PROJECT_NAME=${PROJECT_NAME:-a2a-workshop}
ENVIRONMENT=${ENVIRONMENT:-workshop}

echo "Configuration:"
echo "  AWS Account: $AWS_ACCOUNT_ID"
echo "  AWS Region: $AWS_REGION"
echo "  Project: $PROJECT_NAME"
echo "  Environment: $ENVIRONMENT"
echo ""

# Login to ECR
echo "→ Authenticating with Amazon ECR..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

if [ $? -eq 0 ]; then
  echo "✓ ECR authentication successful"
else
  echo "✗ ECR authentication failed"
  exit 1
fi
echo ""

#############################################################################
# Helper Functions
#############################################################################
# NOTE: ECR repositories are now created by CloudFormation resource stacks.
# Each service has a {service}-resources stack that creates the ECR repo.
# This script only builds and pushes images to existing repositories.

# Define all services to build (matching actual agent names and directories)
SERVICES="orchestrator weather events restaurant budget geography"

# Build each service
for service in $SERVICES; do
  echo "════════════════════════════════════════════════════════════════"
  echo "Building: $service"
  echo "════════════════════════════════════════════════════════════════"

  # Map service name to dockerfile path
  # orchestrator doesn't have -agent suffix, others do
  if [ "$service" = "orchestrator" ]; then
    DOCKERFILE_PATH="services/$service/Dockerfile"
  else
    DOCKERFILE_PATH="services/${service}-agent/Dockerfile"
  fi

  # Construct ECR repository URI
  ECR_REPO="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT_NAME/$service"

  # Check if ECR repository exists (created by CloudFormation)
  echo "→ Checking ECR repository: $PROJECT_NAME/$service"
  if ! aws ecr describe-repositories \
    --repository-names "$PROJECT_NAME/$service" \
    --region "$AWS_REGION" &>/dev/null; then
    echo "  ✗ ECR repository not found: $PROJECT_NAME/$service"
    echo "  Please deploy the ${service}-resources stack first:"
    echo "    ./scripts/deploy-${service}.sh"
    exit 1
  fi
  echo "  ✓ Repository exists"
  echo ""

  # Build Docker image
  echo "→ Building image from: $DOCKERFILE_PATH"
  docker build \
    --platform linux/amd64 \
    -t "$service:latest" \
    -t "$ECR_REPO:latest" \
    -f "$DOCKERFILE_PATH" \
    . 2>&1 | grep -v "^#" || true

  if [ $? -eq 0 ]; then
    echo "✓ Build successful: $service"
  else
    echo "✗ Build failed: $service"
    exit 1
  fi

  # Push to ECR
  echo "→ Pushing to ECR: $ECR_REPO:latest"
  docker push "$ECR_REPO:latest"

  if [ $? -eq 0 ]; then
    echo "✓ Push successful: $service"
  else
    echo "✗ Push failed: $service"
    exit 1
  fi

  echo ""
done

echo "════════════════════════════════════════════════════════════════"
echo "Build Summary"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "All Docker images built and pushed successfully!"
echo ""
echo "Images available in ECR:"
for service in $SERVICES; do
  echo "  ✓ $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT_NAME/$service:latest"
done
echo ""
echo "Build complete!"
