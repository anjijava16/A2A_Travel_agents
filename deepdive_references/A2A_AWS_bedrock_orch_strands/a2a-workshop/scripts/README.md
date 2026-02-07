# A2A Workshop - Deployment Scripts

This directory contains scripts for deploying and managing agents during the A2A Workshop.

## Quick Reference

### Agent Enablement (Pre-Deployed Agents)

Pre-deployed agents are already in ECS with DesiredCount=0. Enable them quickly:

```bash
./scripts/enable-agent.sh location-loader
./scripts/enable-agent.sh geography-agent
./scripts/enable-agent.sh restaurant-agent events-agent  # Multiple at once
./scripts/enable-agent.sh weather-agent
./scripts/enable-agent.sh budget-agent
```

### Agent Management

```bash
./scripts/agent-status.sh                           # Show all agent states
./scripts/disable-agent.sh weather-agent            # Stop agent (~30 seconds)
./scripts/delete-agents.sh                          # Delete learner-created agents
```

### Custom Agent Deployment

Custom agents (hotel, itinerary) require full deployment:

```bash
./scripts/deploy-agent.sh hotel-agent               # ~5 minutes (Chapter 6)
./scripts/deploy-agent.sh itinerary-agent           # ~5 minutes (Chapter 8)
```

---

## enable-agent.sh

Enables pre-deployed agents by setting DesiredCount=1. Fast startup (~60-90 seconds) because Docker images are pre-loaded in ECR and ECS infrastructure is pre-deployed.

### Usage

```bash
./scripts/enable-agent.sh <agent-name> [<agent-name> ...]
```

### Examples

Enable single agent:

```bash
./scripts/enable-agent.sh location-loader
```

Enable multiple agents:

```bash
./scripts/enable-agent.sh restaurant-agent events-agent
```

### Pre-Deployed Agents

- `location-loader` - Location data service (Chapter 1)
- `geography-agent` - Geographic filtering (Chapter 3)
- `restaurant-agent` - Dining recommendations (Chapter 4)
- `events-agent` - Activity suggestions (Chapter 4)
- `weather-agent` - Weather forecasts (Chapter 5)
- `budget-agent` - Budget planning (Chapter 7)

### How It Works

1. Checks if agent stack exists in CloudFormation
2. Verifies current DesiredCount (idempotent - skips if already enabled)
3. Updates stack with DesiredCount=1 using `--use-previous-template`
4. Waits for stack update complete (~60-90 seconds)
5. ECS starts task from pre-built image
6. Task registers in CloudMap when healthy
7. Orchestrator discovers agent automatically

### Deployment Time

- **CloudFormation update**: ~10-20 seconds
- **ECS task startup**: ~40-70 seconds
- **Total**: ~60-90 seconds

Compare to full deployment: ~5 minutes (build + push + deploy)

## disable-agent.sh

Disables agents by setting DesiredCount=0. Stops running ECS tasks and deregisters from CloudMap.

### Usage

```bash
./scripts/disable-agent.sh <agent-name> [<agent-name> ...]
```

### Examples

```bash
./scripts/disable-agent.sh weather-agent
./scripts/disable-agent.sh restaurant-agent events-agent
```

### How It Works

1. Updates CloudFormation stack with DesiredCount=0
2. ECS stops running tasks (~10-20 seconds)
3. CloudMap deregisters service (~10 seconds)
4. Total: ~30 seconds

### When to Use

- Save costs when agent not needed
- Reset workshop state between exercises
- Troubleshoot agent issues (disable, fix, re-enable)

## agent-status.sh

Shows status of all workshop agents (pre-deployed + learner-created).

### Usage

```bash
./scripts/agent-status.sh
```

### Status Types

- **● Enabled** - Agent running and registered in CloudMap (DesiredCount>0, tasks running)
- **○ Disabled** - Agent stack exists but DesiredCount=0 (no tasks running)
- **◐ Starting** - Agent starting up (DesiredCount>0 but tasks not yet running)
- **✗ Not Deployed** - Agent stack doesn't exist
- **? Unknown** - Unable to determine status

### Output Format

```
Pre-Deployed Agents
Agent                     Status
-----                     ------
location-loader           ● Enabled
geography-agent           ○ Disabled
...

Learner-Created Agents
Agent                     Status
-----                     ------
hotel-agent               ✗ Not Deployed
itinerary-agent           ● Enabled
```

### Use Cases

- Check which agents are running
- Verify agent enablement completed
- Debug discovery issues (disabled agents won't appear in CloudMap)

## build-agent-images.sh

**For Workshop Maintainers Only** - Builds Docker images for all pre-deployed agents and saves as compressed tar.gz files for upload to Workshop Studio S3.

### Usage

```bash
./scripts/build-agent-images.sh
```

### What It Does

1. Builds Docker images for 6 pre-deployed agents
2. Saves each image as tar file (`docker save`)
3. Compresses with gzip
4. Output: `static/docker-images/*.tar.gz`

### Built Images

- `location-loader.tar.gz`
- `geography-agent.tar.gz`
- `restaurant-agent.tar.gz`
- `weather-agent.tar.gz`
- `budget-agent.tar.gz`
- `events-agent.tar.gz`

### Build Time

- Per agent: ~2-4 minutes
- Total: ~12-24 minutes
- Platform: `linux/amd64`

### Next Steps

After building, upload to Workshop Studio S3:

```bash
aws s3 cp static/docker-images/ s3://workshop-studio-bucket/docker-images/ --recursive
```

---

## build-and-push-images.sh

Builds all Docker images and pushes them to Amazon ECR. This must be run **after** the infrastructure stack is deployed and **before** deploying individual agents.

### Usage

```bash
./scripts/build-and-push-images.sh
```

### What It Does

1. **Authenticates with ECR** - Uses AWS CLI to get ECR login credentials
2. **Builds all agent images** - Builds Docker images for all 6 services:
   - mcp-gateway
   - orchestrator
   - weather-agent
   - events-agent
   - restaurant-agent
   - budget-analyzer
3. **Pushes to ECR** - Pushes all images to your ECR repositories

### Prerequisites

- AWS CLI installed and configured
- Docker installed and running
- Infrastructure stack deployed (creates ECR repositories)
- Run from the project root directory

### Environment Variables

The script auto-detects AWS configuration, but you can override:

```bash
export AWS_REGION=us-east-1
export PROJECT_NAME=a2a-workshop
export ENVIRONMENT=workshop
./scripts/build-and-push-images.sh
```

### Build Time

- Each image: **2-4 minutes**
- Total for all 6 images: **12-24 minutes**

### Output

The script provides detailed progress:

- ✓ ECR authentication successful
- ✓ Build successful: mcp-gateway
- ✓ Push successful: mcp-gateway
- ... (repeats for each service)

### Troubleshooting

**Error: "Cannot connect to Docker daemon"**

- Ensure Docker Desktop is running
- On Linux: `sudo systemctl start docker`

**Error: "ECR authentication failed"**

- Check AWS credentials: `aws sts get-caller-identity`
- Ensure IAM permissions for ECR

**Error: "Repository does not exist"**

- Deploy infrastructure stack first
- Verify ECR repositories exist: `aws ecr describe-repositories`

**Error: "Build failed"**

- Check Dockerfile exists at `services/<service-name>/Dockerfile`
- Verify all dependencies in requirements.txt are available

## deploy-agent.sh

The main deployment script for workshop students. This script simplifies the process of deploying agents to AWS ECS Fargate using CloudFormation.

### Usage

```bash
./deploy-agent.sh <agent-name>
```

### Available Agents

- `weather-agent` - Weather forecast agent
- `events-agent` - Activity suggestions agent
- `restaurant-agent` - Dining recommendations agent
- `budget-analyzer` - Budget analysis agent (optional)

### Examples

Deploy weather agent:

```bash
./deploy-agent.sh weather-agent
```

Deploy events agent:

```bash
./deploy-agent.sh events-agent
```

Deploy restaurant agent:

```bash
./deploy-agent.sh restaurant-agent
```

Delete an agent:

```bash
./deploy-agent.sh --delete weather-agent
```

### Options

- `-h, --help` - Show help message
- `-r, --region REGION` - Specify AWS region (default: current region)
- `-d, --delete` - Delete the agent stack instead of creating it

### Prerequisites

The script checks for the following prerequisites:

1. **AWS CLI** - Must be installed and in PATH
2. **AWS Credentials** - Must be configured (`aws configure`)
3. **AWS Region** - Must be set in AWS CLI configuration
4. **Infrastructure Stack** - The workshop infrastructure stack must be deployed

### What the Script Does

1. **Validates Prerequisites**

   - Checks AWS CLI installation
   - Verifies AWS credentials
   - Confirms AWS region is set
   - Checks infrastructure stack status

2. **Validates Agent Name**

   - Ensures agent name is one of the supported agents
   - Checks parameter file exists

3. **Deploys CloudFormation Stack**

   - Creates or updates the agent stack
   - Uses agent-specific parameter file
   - Waits for stack completion

4. **Shows Deployment Info**
   - Displays CloudMap service name
   - Shows ECS service name
   - Provides CloudWatch Logs link
   - Suggests next steps

### Error Handling

The script includes comprehensive error handling:

- ✓ Missing AWS CLI
- ✓ Invalid AWS credentials
- ✓ Missing AWS region
- ✓ Infrastructure stack not ready
- ✓ Invalid agent name
- ✓ Missing template or parameter files
- ✓ CloudFormation deployment failures

### Output

The script uses color-coded output:

- 🔵 **Blue** - Informational messages
- ✅ **Green** - Success messages
- ⚠️ **Yellow** - Warning messages
- ❌ **Red** - Error messages

### Deployment Time

Typical deployment times:

- Stack creation: **3-5 minutes**
- Task startup: **30-60 seconds**
- Total: **4-6 minutes** per agent

### Files Used

- **Template**: `static/cloudformation/agent-service-template.yaml`
- **Parameters**: `static/cloudformation/parameters/<agent-name>.json`

### Stack Naming Convention

Agent stacks are named: `<agent-name>-stack`

Examples:

- `weather-agent-stack`
- `events-agent-stack`
- `restaurant-agent-stack`

### CloudFormation Capabilities

The script requests `CAPABILITY_IAM` because the template creates IAM resources (service-linked roles).

### Next Steps After Deployment

After successful deployment:

1. **Check ECS Service Status**

   - Navigate to ECS Console
   - Verify service is running
   - Check task count (should be 1)

2. **View Agent Logs**

   - Navigate to CloudWatch Logs
   - Open log group: `/ecs/a2a-workshop/workshop/<agent-name>`
   - Check for startup messages

3. **Test Agent Discovery**

   - Use CloudMap API to discover agent
   - Verify agent IP address is registered

4. **Query via Orchestrator**
   - Send request to orchestrator
   - Orchestrator should discover and invoke your agent

### Troubleshooting

**Error: "Infrastructure stack not found"**

- The workshop infrastructure must be deployed first
- Contact workshop instructor

**Error: "Docker image not found"**

- The script will continue with default image
- Workshop Studio pre-builds images
- Custom images can be specified with `--image` flag

**Error: "Stack already exists"**

- Script will prompt to update existing stack
- Choose 'y' to update, 'N' to cancel

**Stack creation timeout**

- Check CloudFormation console for detailed error messages
- Common issues: insufficient IAM permissions, resource limits

### Advanced Usage

Specify custom Docker image:

```bash
# (Future enhancement)
./deploy-agent.sh --image 123456789012.dkr.ecr.us-west-2.amazonaws.com/my-agent:v1.0 weather-agent
```

Specify different AWS region:

```bash
./deploy-agent.sh --region us-east-1 weather-agent
```

## For Workshop Instructors

### Pre-Workshop Setup

1. Deploy infrastructure stack (creates VPC, ECS, ECR repositories)
2. Build and push Docker images:
   ```bash
   ./scripts/build-and-push-images.sh
   ```
3. Test deployment script with one agent
4. Verify orchestrator can discover and invoke agents

### Workshop Flow

**Module 2: Deploy Baseline System**

```bash
./deploy-agent.sh events-agent
./deploy-agent.sh restaurant-agent
```

**Module 3: Add Weather Intelligence**

```bash
./deploy-agent.sh weather-agent
```

**Module 4: Add Budget Analysis (Optional)**

```bash
./deploy-agent.sh budget-analyzer
```

### Cleanup After Workshop

Delete all agent stacks:

```bash
./deploy-agent.sh --delete weather-agent
./deploy-agent.sh --delete events-agent
./deploy-agent.sh --delete restaurant-agent
./deploy-agent.sh --delete budget-analyzer
```

Or use CloudFormation console to delete all stacks with pattern `*-agent-stack`.

## deploy-mcp-gateway.sh

Specialized deployment script for the MCP Gateway service. The MCP Gateway provides the integration endpoint for Claude Code AI assistant to interact with the agent system.

### Usage

```bash
./scripts/deploy-mcp-gateway.sh
```

### What It Does

The script follows a **3-step deployment pattern**:

1. **Step 1: Deploy Resources Stack** (CloudFormation)

   - Creates ECR repository for MCP Gateway
   - Creates CloudWatch Log Group
   - Pure Infrastructure as Code - no AWS CLI resource creation

2. **Step 2: Build and Push Docker Image**

   - Authenticates with ECR
   - Builds Docker image (`services/mcp-gateway/Dockerfile`)
   - Pushes image to ECR repository from Step 1

3. **Step 3: Deploy Service Stack** (CloudFormation)
   - Creates ECS Task Definition
   - Creates ECS Service on Fargate
   - Configures Application Load Balancer (ALB)
   - Uses image URI from Step 2

### Prerequisites

- AWS CLI installed and configured
- Docker installed and running
- Infrastructure stack deployed (VPC, ECS cluster, ALB)
- Run from project root directory

### Deployment Time

- Step 1 (Resources): **~2 minutes**
- Step 2 (Build/Push): **~3-5 minutes**
- Step 3 (Service): **~3-5 minutes**
- **Total: ~8-12 minutes**

### Output

Each step provides detailed progress and outputs the resources created.

### Files Used

- **Resources Template**: `static/cloudformation/mcp-gateway-resources-template.yaml`
- **Service Template**: `static/cloudformation/mcp-gateway-service-stack.yaml`
- **Dockerfile**: `services/mcp-gateway/Dockerfile`

### Stack Names

- Resources: `mcp-gateway-resources`
- Service: `mcp-gateway-service`

## deploy-orchestrator.sh

Specialized deployment script for the Travel Orchestrator agent. The Orchestrator coordinates multiple specialist agents to fulfill complex travel planning requests.

### Usage

```bash
./scripts/deploy-orchestrator.sh
```

### What It Does

The script follows a **3-step deployment pattern**:

1. **Step 1: Deploy Resources Stack** (CloudFormation)

   - Creates ECR repository for Orchestrator
   - Creates CloudWatch Log Group
   - Pure Infrastructure as Code

2. **Step 2: Build and Push Docker Image**

   - Authenticates with ECR
   - Builds Docker image (`services/orchestrator/Dockerfile`)
   - Pushes image to ECR repository

3. **Step 3: Deploy Service Stack** (CloudFormation)
   - Creates ECS Task Definition
   - Creates ECS Service on Fargate
   - Registers with AWS CloudMap for service discovery
   - Uses image URI from Step 2

### Prerequisites

- AWS CLI installed and configured
- Docker installed and running
- Infrastructure stack deployed (VPC, ECS cluster, CloudMap namespace)
- Run from project root directory

### Deployment Time

- Step 1 (Resources): **~2 minutes**
- Step 2 (Build/Push): **~3-5 minutes**
- Step 3 (Service): **~3-5 minutes**
- **Total: ~8-12 minutes**

### Files Used

- **Resources Template**: `static/cloudformation/orchestrator-resources-stack.yaml`
- **Service Template**: `static/cloudformation/orchestrator-service-stack.yaml`
- **Dockerfile**: `services/orchestrator/Dockerfile`

### Stack Names

- Resources: `orchestrator-resources`
- Service: `orchestrator-service`

## deploy-all.sh

Convenience script that deploys all services in the correct sequence. Useful for testing or rapid environment setup.

### Usage

```bash
./scripts/deploy-all.sh
```

### What It Does

Deploys services in dependency order:

1. **Specialist Agents** (in parallel after images built)

   - Weather Agent
   - Events Agent
   - Restaurant Agent
   - Geography Agent
   - Budget Analyzer

2. **Orchestrator** (after specialist agents)

   - Coordinates the specialist agents
   - Depends on CloudMap for agent discovery

3. **MCP Gateway** (after orchestrator)
   - Integration endpoint for Claude Code
   - Routes requests to orchestrator

### Prerequisites

- All prerequisites from individual deployment scripts
- Docker images must be built first (via `build-and-push-images.sh`)
- Infrastructure stack must be deployed

### Deployment Time

- **Total: ~30-40 minutes** (agents deploy in sequence)
- Each agent: 3-5 minutes for service stack deployment
- Orchestrator: 3-5 minutes
- MCP Gateway: 3-5 minutes

### When to Use

**Use `deploy-all.sh` when:**

- Testing full system deployment
- Setting up environment for demos
- Rapid iteration during development
- Recovering from full teardown

**Use individual scripts when:**

- Learning the system architecture (educational workshops)
- Deploying/updating single services
- Debugging specific agents
- Following step-by-step workshop modules

### Output

The script shows progress for each deployment phase and reports completion status for all services.

## 3-Step Deployment Pattern

All service deployment scripts (MCP Gateway, Orchestrator, and individual agents via `deploy-agent.sh`) follow the same **3-step pattern**:

### Why This Pattern?

1. **Pure Infrastructure as Code** - ECR repositories created via CloudFormation, not AWS CLI
2. **Clear Separation** - Resources (ECR, logs) separate from services (ECS, networking)
3. **Dependency Management** - Image must exist before ECS service references it
4. **Educational** - Students see exactly what infrastructure is created at each step

### Pattern Breakdown

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Resources Stack (CloudFormation)                       │
│ ─────────────────────────────────────────────────────────────  │
│ • ECR Repository                                                │
│ • CloudWatch Log Group                                          │
│ • Output: ECR Repository URI                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Build & Push Docker Image                              │
│ ─────────────────────────────────────────────────────────────  │
│ • docker login (ECR auth)                                       │
│ • docker build (platform: linux/amd64)                          │
│ • docker push to ECR from Step 1                                │
│ • Output: Image URI with digest                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Service Stack (CloudFormation)                         │
│ ─────────────────────────────────────────────────────────────  │
│ • ECS Task Definition (references image from Step 2)           │
│ • ECS Service (Fargate launch type)                             │
│ • CloudMap Registration OR ALB Target (depending on service)    │
│ • Output: Service endpoint / CloudMap service name              │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decision

**ECR repositories are created in Step 1 (CloudFormation), not pre-created in the infrastructure stack.**

This ensures:

- ✓ Pure IaC approach - all resources defined in CloudFormation
- ✓ Service-specific stacks are self-contained
- ✓ Clean separation between shared infrastructure and service resources
- ✓ Students can deploy/delete services independently
