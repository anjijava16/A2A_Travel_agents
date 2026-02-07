# A2A Workshop - Workshop Materials

This directory contains all materials for the "Inter-Agent Systems with Strands Agents, Amazon Bedrock, MCP, and A2A" workshop.

## 🎯 Pre-Deployed Infrastructure

**The following infrastructure has been automatically deployed before you started:**

### Core Infrastructure (Running and Ready)
✅ **Code-Server** - Browser-based VS Code environment (you're using it now!)
✅ **VPC & Networking** - Private network for secure agent communication (2 AZs, Internet Gateway, NAT Gateway, Security Groups)
✅ **ECS Fargate Cluster** - Serverless container orchestration for agents
✅ **AWS CloudMap** - Service discovery system (agents find each other automatically)
✅ **Application Load Balancer** - HTTP routing for agent services
✅ **ECR Repositories** - Docker image storage for all components
✅ **IAM Roles** - Permissions for agents to access Bedrock, CloudMap, EventBridge
✅ **CloudWatch Logs** - Logging and monitoring for all services

### Core Services (Deployed and Running)
✅ **MCP Gateway** - Integration endpoint for Claude Code AI assistant (DesiredCount=1)
✅ **Travel Orchestrator** - Multi-agent coordinator that delegates tasks (DesiredCount=1)

### Specialist Agents (Pre-Deployed, Enable During Workshop)
✅ **Location-Loader** - Location data service (enabled in Chapter 1)
✅ **Geography Agent** - Geographic filtering specialist (enabled in Chapter 3)
✅ **Restaurant Agent** - Dining recommendations specialist (enabled in Chapter 4)
✅ **Weather Agent** - Weather forecast specialist (enabled in Chapter 5)
✅ **Budget Agent** - Budget calculation specialist (enabled in Chapter 7)
✅ **Events Agent** - Event discovery specialist (enabled in various chapters)

**You do NOT need to deploy any of this infrastructure!** The core infrastructure and services are running. The six specialist agents are pre-deployed with Docker images ready but initially disabled (DesiredCount=0). You'll enable them during the workshop using `enable-agent.sh`, which takes only 60-90 seconds per agent.

**You WILL build and deploy:** Two additional agents (Hotel Agent in Chapter 6, Itinerary Agent in Chapter 8) from scratch using `deploy-agent.sh`.

## 📄 Workshop PDF Guide

A comprehensive PDF version of all workshop content is available for download. This is perfect if you:
- Want to review content offline
- Didn't complete all chapters during the workshop
- Need a reference guide for later

**Download:** [workshop-guide.pdf](https://ws-assets-prod-iad-r-pdx-f3b3f9f1a7d6a3d0.s3.us-west-2.amazonaws.com/c079209e-3f27-4614-9b4f-48eae3921e57/workshop-guide.pdf) (~5MB, 100+ pages)

The PDF includes:
- All chapters from Prologue through Epilogue
- All architecture diagrams and screenshots
- Code examples and configuration snippets
- Step-by-step instructions
- Agent design patterns and best practices

## 🚀 Your Task: Deploy Specialist Agents

Your job is to deploy the **specialist agents** that provide travel information. These agents automatically register with CloudMap and integrate with the orchestrator.

**Note:** The MCP Gateway and Orchestrator are already running! You only need to deploy the specialist agents.

### Module 1: Build Docker Images for Specialist Agents (Required First Step)

```bash
cd /home/participant/workshop
./scripts/build-and-push-images.sh
```

**What this does:**
- Builds Docker images for all 5 specialist agents (weather, events, restaurant, geography, budget)
- Pushes images to Amazon ECR
- Takes approximately 10-15 minutes
- **Note:** MCP Gateway and Orchestrator images are already deployed - you don't need to build them!

### Module 2: Deploy Specialist Agents (Required)

```bash
./scripts/deploy-agent.sh events-agent
./scripts/deploy-agent.sh restaurant-agent
```

**What these do:**
- **Events Agent** - Suggests indoor/outdoor activities based on weather
- **Restaurant Agent** - Recommends dining options

### Module 3: Add Weather Intelligence (Required)

```bash
./scripts/deploy-agent.sh weather-agent
```

**What this does:**
- **Weather Agent** - Provides 7-day weather forecasts
- **Enables orchestration** - Orchestrator now filters activities based on rain

### Module 4: Add Geography Filtering (Optional)

```bash
./scripts/deploy-agent.sh geography-agent
```

**What this does:**
- **Geography Agent** - Filters events and restaurants by proximity using OpenStreetMap data

### Module 5: Add Budget Analysis (Optional Challenge)

```bash
./scripts/deploy-agent.sh budget-agent
```

**What this does:**
- **Budget Agent** - Analyzes travel cost data and provides financial recommendations

### Alternative: Deploy All Specialist Agents at Once

If you prefer to deploy all specialist agents in one command after building images:

```bash
./scripts/deploy-all.sh
```

**What this does:**
- Deploys all 5 specialist agents (weather, events, restaurant, geography, budget) in sequence
- All services deploy automatically

**Note:** This is convenient for testing but less educational. The step-by-step approach above helps you understand each agent's role.

## 📁 Directory Structure

```
.
├── agents/                          # Agent source code
│   ├── base/                        # Domain-agnostic framework
│   ├── common/                      # CloudMap utilities
│   └── travel/                      # Travel domain agents
├── config/                          # Agent configurations
│   └── domains/
│       └── travel.yaml              # Travel domain config
├── core/                            # Core modules
├── data/                            # Mock data
│   └── mock/
│       ├── weather/                 # Weather data (rainy Seattle!)
│       ├── events/                  # Indoor/outdoor activities
│       └── restaurants/             # Restaurant recommendations
├── static/
│   └── cloudformation/              # CloudFormation templates
│       ├── agent-service-template.yaml  # Template YOU use
│       └── parameters/              # Agent configurations
│           ├── weather-agent.json
│           ├── events-agent.json
│           ├── restaurant-agent.json
│           └── budget-analyzer.json
├── scripts/                         # Deployment scripts
│   ├── deploy-agent.sh              # ← USE THIS to deploy agents
│   └── README.md                    # Detailed script documentation
├── requirements.txt                 # Python dependencies
└── README.md                        # This file
```

## 🛠️ How Agent Deployment Works

When you run `./scripts/deploy-agent.sh weather-agent`:

1. **Script validates** - Checks AWS credentials, infrastructure stack exists
2. **CloudFormation deploys** - Creates ECS service with your agent
3. **Docker image pulled** - ECS pulls pre-built agent image from ECR
4. **Agent starts** - Container runs Python agent code
5. **CloudMap registration** - Agent registers itself for service discovery
6. **Ready!** - Orchestrator can now discover and invoke your agent

## 📚 CloudFormation Templates

### Pre-Deployed (Reference Only)

These are already deployed - you can view them in the GitHub repository for learning:

- `a2a-workshop-main.yaml` - Parent stack that deploys everything via nested stacks
- `code-server.yaml` - Your browser-based VS Code environment
- `infrastructure-stack.yaml` - VPC, ECS cluster, CloudMap, IAM roles, ECR, ALB
- `mcp-gateway-stack.yaml` - MCP Gateway service for Claude Code integration
- `orchestrator-stack.yaml` - Travel Orchestrator multi-agent coordinator

### Student-Deployed (You Use These!)

- `agent-service-template.yaml` - **Reusable agent deployment template**
  - Used for Weather, Events, Restaurant, Budget Analyzer agents
  - Creates: ECS task definition, ECS service, CloudMap service, Log group
- `parameters/*.json` - Agent-specific configurations
  - Each agent gets unique port, name, resource allocation

## 🧑‍💻 Agent Source Code

Explore the agent implementations in `agents/`:

- **weather_agent/main.py** - Provides 7-day weather forecasts using mock data
- **events_agent/main.py** - Suggests activities (filters outdoor events if raining!)
- **restaurant_agent/main.py** - Recommends restaurants based on cuisine preferences
- **orchestrator/main.py** - Coordinates multiple agents, delegates tasks intelligently

**Framework code** (in `agents/base/`):
- **agent_interface.py** - BaseAgent abstract class with A2A protocol
- **config_loader.py** - YAML configuration parser
- **mock_data_factory.py** - Loads mock data from `data/mock/`

## 🎭 Mock Data (For Learning)

We use **pedagogically-designed mock data** instead of external APIs:

- ✅ **Reliable** - No external API dependencies, no failures
- ✅ **Predictable** - Same data every workshop run
- ✅ **Educational** - Seattle has heavy rain to demonstrate orchestration filtering
- ✅ **Cost** - Zero external API costs

**Example:** Seattle weather shows "Heavy Rain" → Orchestrator filters out outdoor events → Students see intelligent multi-agent coordination!

## 🔍 Deployment Scripts

The `scripts/` directory contains deployment automation:

```bash
# Deploy an agent
./scripts/deploy-agent.sh <agent-name>

# Examples
./scripts/deploy-agent.sh weather-agent
./scripts/deploy-agent.sh events-agent
./scripts/deploy-agent.sh restaurant-agent

# Deploy core services
./scripts/deploy-mcp-gateway.sh
./scripts/deploy-orchestrator.sh

# Deploy everything at once
./scripts/deploy-all.sh

# Get help
./scripts/deploy-agent.sh --help

# Delete an agent
./scripts/deploy-agent.sh --delete weather-agent
```

**What deployment scripts do:**
1. Validate AWS credentials and infrastructure
2. Check if agent stack already exists
3. Deploy CloudFormation stack with agent template + parameters
4. Wait for completion (~4-6 minutes per agent)
5. Show deployment info (CloudMap service, ECS service, CloudWatch Logs)

## 🧪 Testing Your Agents

After deploying agents, test them via:

1. **AWS Console** - Check ECS service status, view logs in CloudWatch
2. **Claude Code** - Use MCP integration to invoke agents
3. **Orchestrator** - Send requests to orchestrator, observe multi-agent coordination

**Example orchestrator request:**
```
"Plan a trip to Seattle next week"
```

**What happens:**
1. Orchestrator discovers agents via CloudMap
2. Queries Weather Agent → sees "Heavy Rain"
3. Queries Events Agent → filters out outdoor activities
4. Queries Restaurant Agent → suggests indoor dining
5. Returns coordinated travel plan

## 📊 Observability & Monitoring

Monitor and debug your multi-agent system using CloudWatch Logs with pre-built queries and real-time monitoring tools.

### CloudWatch Logs Insights Queries

**14 pre-configured queries** are automatically available in CloudWatch Logs Insights:

1. **Trace Single Request End-to-End** - Follow one request through all agents
2. **Find All Workflow Executions** - See orchestrator workflows
3. **Track Agent Performance** - Analyze duration and success rates
4. **Debug Workflow Stage Execution** - Understand multi-stage workflows
5. **Find All Errors with Context** - Troubleshoot failures
6. **Agent Discovery Events** - Debug service discovery
7. **LLM Interaction Analysis** - Track AI model usage
8. **Budget Agent Processing** - Debug budget extraction
9. **Geography Proximity Filtering** - Understand proximity calculations
10. **Workshop Learning Journey** - See complete system flow
11. **Request Volume by Hour** - Monitor system activity
12. **Parallel vs Sequential Patterns** - Analyze workflow types
13. **Agent Input/Output Analysis** - Understand agent contracts
14. **Find Slow Operations** - Identify performance bottlenecks

**Access saved queries:**
1. Open CloudWatch Console → Logs → Insights
2. Select log groups (e.g., `/ecs/a2a/orchestrator`)
3. Click "Queries" tab → Find queries prefixed with `[a2a]`
4. Click a query → "Run query"

### Live Tail Monitoring

**Real-time log streaming** using CloudWatch Console:

1. Open CloudWatch Logs Console
2. Select your log group (e.g., `/ecs/a2a/orchestrator`)
3. Click **Actions** → **Start Live Tail**
4. Use filter patterns to focus on specific events

**Useful Filter Patterns:**
- `"📥"` - Watch agent inputs
- `"📤"` - Watch agent outputs
- `"ERROR"` - Monitor errors in real-time
- `"🤖"` - Track LLM interactions
- `"req=abc12345"` - Follow specific request
- `performance` - Monitor timing and durations

### Visual Log Markers

Logs include educational markers to help you understand workflows:
- 🎯 = Milestone or stage boundary
- ✅ = Success / Completion
- ❌ = Error or failure
- 📥 = Input received
- 📤 = Output sent
- 🤖 = LLM interaction

### Comprehensive Guide

For detailed observability documentation, see **[docs/OBSERVABILITY.md](docs/OBSERVABILITY.md)**:
- Complete logging architecture
- Request tracing patterns
- Troubleshooting workflows
- Workshop learning scenarios
- Advanced CloudWatch topics

## 📖 Next Steps

1. **Review workshop modules** in Workshop Studio UI
2. **Deploy agents** as instructed in each module
3. **Test via Claude Code** - Use MCP integration to invoke agents
4. **Observe orchestration** - Watch how agents coordinate intelligently
5. **Explore code** - Read agent implementations to understand patterns
6. **Optional challenge** - Implement budget-analyzer agent

## 🆘 Troubleshooting

**Agent deployment fails?**
- Check CloudFormation console for error messages
- Verify infrastructure stack is complete
- Check IAM permissions in code-server instance role

**Agent not discoverable?**
- Check CloudMap services (AWS Console → Cloud Map)
- Verify agent ECS service is running (AWS Console → ECS → Clusters)
- Check agent logs in CloudWatch Logs

**Need help?**
- Contact your workshop instructor
- Review `scripts/README.md` for detailed deployment documentation

## 📚 Additional Resources

- **Deployment Script Documentation** - See `scripts/README.md`
- **Workshop GitHub Repository** - Full source code and templates
- **Agent Source Code** - Explore `agents/` directory to understand implementation patterns

---

**Workshop:** Inter-Agent Systems with Strands, Bedrock, MCP, and A2A
**Version:** 1.0
**Last Updated:** 2025-10-30
**Author:** AWS Solutions Architects
