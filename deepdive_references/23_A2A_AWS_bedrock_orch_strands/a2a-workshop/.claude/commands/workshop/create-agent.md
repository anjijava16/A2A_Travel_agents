---
description: Create a new specialist agent for the workshop
---

# Create Workshop Agent

Create a new specialist agent implementation. This command supports two patterns:
- **Simple agents** (BaseAgent) - Rule-based lookup agents (hotel, transportation)
- **Reasoning agents** (AgenticBaseAgent) - LLM-powered planning agents (budget, itinerary)

**Usage:**
```
/workshop:create-agent <agent-type>
```

**Supported agent types:**
| Type | Pattern | Reference Agent | Description |
|------|---------|-----------------|-------------|
| `hotel` | Simple | `agents/restaurant_agent/main.py` | Hotel and lodging lookup |
| `transportation` | Simple | `agents/weather_agent/main.py` | Transportation options lookup |
| `budget` | Reasoning | `agents/budget_agent/main.py` | Budget planning with cost analysis |
| `itinerary` | Reasoning | `agents/budget_agent/main.py` | Itinerary planning with scheduling |

---

## Instructions

**IMPORTANT: Local testing is NOT possible** - dependencies (a2a, strands, etc.) are only available inside Docker containers. Do NOT attempt to run Python scripts locally.

**INSTRUCTIONAL APPROACH**: As you create files, ALWAYS explain to the learner:
- **What** you're creating (file purpose, role in the system)
- **Why** this file is needed (how it fits into the agent architecture)
- **What changes** you're making from the template (specific adaptations for their domain)
- **Key concepts** being demonstrated (A2A protocol, capability definitions, tool patterns, etc.)

Think of this as a guided tutorial where you're teaching while building. Use phrases like:
- "I'm now creating the main.py file, which defines your agent's business logic..."
- "This capability definition tells the orchestrator what your agent can do..."
- "Notice how we're adapting the input schema to match your domain..."

You will create a complete agent by:
1. Reading an existing agent as a template
2. Copying and adapting the agent for the new domain
3. Copying and adapting deployment files (Dockerfile, parameters)
4. Deploying to AWS ECS
5. Verifying the deployment via AWS CLI and orchestrator

### Step 1: Read Reference Agent (REQUIRED)

**BEFORE READING**: Explain to the learner:
- "I'm going to read an existing agent as a template. This helps us understand the exact structure and patterns we need to follow."
- "For [simple/reasoning] agents, I'll use [restaurant/budget] agent as the reference."

**You MUST read an existing agent file completely before creating a new one.**

**For simple agents (hotel, transportation):**
```bash
cat agents/restaurant_agent/main.py
```
Read the entire file. This will be your template.

**AFTER READING**: Explain what you learned:
- "I've just read the restaurant agent. Here are the key components I'll adapt for your [agent-type] agent:"
- "1. Class structure: Inherits from BaseAgent for rule-based lookups"
- "2. Capability definition: Tells the orchestrator what this agent can do"
- "3. Input schema: Defines expected parameters (location, filters, etc.)"
- "4. Processing logic: Fetches mock data and applies domain-specific filters"
- "5. Response formatting: Creates human-readable output"

**For reasoning agents (budget, itinerary):**
```bash
cat agents/budget_agent/main.py
```
Read the entire file. This will be your template.

**AFTER READING**: Explain what you learned:
- "I've just read the budget agent. Here are the key components I'll adapt for your [agent-type] agent:"
- "1. Class structure: Inherits from AgenticBaseAgent for LLM-powered reasoning"
- "2. Tool functions: Domain-specific helpers that the LLM can call"
- "3. System prompt: Instructions that guide the LLM's decision-making"
- "4. Capability definition: More complex schema for reasoning tasks"

**Do not skip this step.** You need to understand the exact patterns used.

### Step 2: Create Agent Directory

**BEFORE CREATING**: Explain to the learner:
- "I'm creating a directory for your [agent-type] agent. This follows the workshop's naming convention: agents/<agent-type>_agent/"
- "This directory will contain your agent's main.py file, which implements the business logic."

```bash
mkdir -p agents/<agent-type>_agent
cd agents/<agent-type>_agent
```

**AFTER CREATING**: Confirm:
- "✓ Created agents/<agent-type>_agent/ directory"
- "Next, I'll create the main.py file by adapting the [reference] agent template."

### Step 3: Copy and Adapt main.py

**BEFORE WRITING**: Explain the adaptation strategy:
- "I'm now creating the main.py file for your [agent-type] agent."
- "I'll adapt the [reference] agent template by making these domain-specific changes:"
- "  • Class name: [Reference]Agent → [AgentType]Agent"
- "  • Capability ID: Describes what your agent does in the A2A protocol"
- "  • Input schema: Parameters specific to your domain (e.g., location, amenities for hotels)"
- "  • Processing logic: Domain-specific filtering and data retrieval"
- "  • Response format: How results are presented to users"

**Copy the reference agent** to your new agent directory:

```bash
cp agents/restaurant_agent/main.py agents/<agent-type>_agent/main.py
```

**AS YOU ADAPT**: Narrate each significant change:
- "Changing class name to [AgentType]Agent..."
- "Updating capability ID to '[capability-id]' - this tells the orchestrator when to use this agent..."
- "Modifying input schema to accept [domain-specific parameters]..."
- "Adapting filter logic for [domain attributes]..."
- "Updating response format to display [domain-specific fields]..."

**Then adapt** the copied file with these changes only:

1. **Class name**: `RestaurantAgent` → `<AgentType>Agent`
2. **Agent name**: `"restaurant-agent"` → `"<agent-type>-agent"`
3. **Capability ID**: `"refine-restaurants"` → appropriate ID for your domain
4. **Capability description**: Update to match your domain
5. **Tags**: Update to include relevant domain terms
6. **Input schema**: Modify parameters for your domain's filtering needs
7. **Filtering logic**: Adapt `_apply_filters()` for your domain's attributes
8. **Mock data method**: Use appropriate `mock_factory.get_*()` method
9. **Response formatting**: Update `_format_response()` for your data structure

**Keep everything else the same** - imports, base class, helper methods, entry points.

**Example changes for hotel agent:**
- Class: `RestaurantAgent` → `HotelAgent`
- Capability: `"refine-restaurants"` → `"refine-hotels"`
- Filters: dietary restrictions → amenities (gym, pool, breakfast, air_conditioning)
- Mock data: `get_restaurants()` → `get_accommodations()`
- Response: Format hotel name, price_per_night, rating, amenities

**For reasoning agents (budget, itinerary):**

Copy the budget agent as your starting point:
```bash
cp agents/budget_agent/main.py agents/<agent-type>_agent/main.py
```

**Then make these specific changes:**

1. **Class name** (line ~70): `BudgetPlanningAgent` → `<AgentType>PlanningAgent`
2. **Logger message** (line ~74): `"Budget Planning Agent initialized"` → `"<AgentType> Planning Agent initialized"`
3. **Tool functions** (lines ~76-500): Replace all 3 tool functions with your domain-specific tools
4. **System prompt** (lines ~533-650): Completely rewrite for your domain
5. **Capability definition** (lines ~661-760):
   - Capability ID: `"plan-budget"` → `"<your-capability-id>"`
   - Name, description, tags: Update for your domain
   - Input schema: Define your domain's required inputs
   - Output schema: Define your domain's expected outputs
6. **Type hints in entry points** (line ~856): `def get_agent() -> BudgetPlanningAgent:` → `def get_agent() -> <AgentType>PlanningAgent:`
7. **Docstrings**: Update all docstrings referencing "budget" to your domain

**Critical:** Use Find & Replace to change ALL occurrences of `BudgetPlanningAgent` to `<AgentType>PlanningAgent` in the file.

**Verification Checklist for Reasoning Agents:**

Before proceeding, verify you've updated:
- [ ] Class definition: `class <AgentType>PlanningAgent(AgenticBaseAgent):`
- [ ] All tool functions are domain-specific (not budget-related)
- [ ] System prompt describes your domain (not budget planning)
- [ ] Capability ID is domain-specific (not "plan-budget")
- [ ] `get_agent()` type hint: `-> <AgentType>PlanningAgent:`
- [ ] Agent initialization log message mentions your domain
- [ ] All docstrings reference your domain (not budget)

**⚠️ DO NOT attempt to test locally.** Dependencies are not installed. Proceed directly to Step 4.

### Step 4: Create Deployment Files

**BEFORE CREATING DEPLOYMENT FILES**: Explain the deployment architecture:
- "Now I'll create the deployment files needed to run your agent in AWS ECS."
- "We need two files:"
- "  1. Dockerfile - Defines the container image for your agent"
- "  2. CloudFormation parameters - Configuration for the ECS service"
- "These files follow Infrastructure as Code principles, making deployment repeatable and version-controlled."

Before deploying, create the necessary Docker and CloudFormation files **by copying from an existing agent**.

#### 4.1 Create Dockerfile

**BEFORE CREATING DOCKERFILE**: Explain:
- "The Dockerfile packages your agent code into a Docker container."
- "Key components:"
- "  • Base image: Python 3.12 with all dependencies"
- "  • COPY commands: Brings in your agent code, shared libraries, and config"
- "  • ENV variables: Sets the agent type for runtime discovery"
- "  • HEALTHCHECK: Ensures ECS knows when your agent is ready"
- "  • CMD: Starts the FastAPI server with your agent"

**Read an existing Dockerfile as a template:**

```bash
# For simple agents, use restaurant-agent as template:
cat services/restaurant-agent/Dockerfile

# For reasoning agents, use budget-agent as template:
cat services/budget-agent/Dockerfile
```

**Copy and adapt** the Dockerfile to `services/<agent-type>-agent/Dockerfile`:

- Keep the entire structure exactly as-is
- Only change the `ENV AGENT_TYPE` value to match your new agent type
- Only change the `--agent-type` argument in the CMD line to match your new agent type
- Everything else stays the same (base image, COPY commands, HEALTHCHECK, etc.)

**AS YOU CREATE THE DOCKERFILE**: Narrate:
- "Creating services/[agent-type]-agent/Dockerfile..."
- "The only changes needed are:"
- "  • ENV AGENT_TYPE=[agent-type]-agent - This tells the runtime which agent to load"
- "  • CMD --agent-type [agent-type]-agent - This parameter is passed to the FastAPI startup"
- "Everything else remains the same - the base image, dependencies, and structure are universal."

**Example:** For a hotel agent, you would:
1. Copy `services/restaurant-agent/Dockerfile` to `services/hotel-agent/Dockerfile`
2. Change `ENV AGENT_TYPE=restaurant-agent` to `ENV AGENT_TYPE=hotel-agent`
3. Change CMD line: `--agent-type restaurant-agent` to `--agent-type hotel-agent`

**AFTER CREATING**: Confirm:
- "✓ Created services/[agent-type]-agent/Dockerfile"
- "This file is ready for Docker to build your container image."

#### 4.2 Create CloudFormation Parameters

**BEFORE CREATING PARAMETERS**: Explain:
- "CloudFormation parameters define how your agent runs in ECS:"
- "  • AgentName & AgentType: Identity for service discovery"
- "  • ContainerCpu/Memory: Resource allocation (512 CPU units, 1GB RAM)"
- "  • AgentPort: Port 8000 for the FastAPI server"
- "  • DesiredCount: 1 means one running instance"
- "These match the reusable CloudFormation template that creates ECS services."

**Read an existing parameters file as a template:**

```bash
cat static/cloudformation/parameters/restaurant-agent.json
```

**Copy and adapt** to `static/cloudformation/parameters/<agent-type>-agent.json`:

- Copy the entire JSON structure
- Update `AgentName` and `AgentType` values to match your new agent type
- Everything else stays the same (ProjectName, Environment, ports, resources)

**AS YOU CREATE THE PARAMETERS**: Narrate:
- "Creating static/cloudformation/parameters/[agent-type]-agent.json..."
- "Updating AgentName and AgentType to '[agent-type]-agent'..."
- "All other parameters (CPU, memory, port) remain standard for consistency."

**Example:** For a hotel agent:
1. Copy `static/cloudformation/parameters/restaurant-agent.json` to `static/cloudformation/parameters/hotel-agent.json`
2. Change `"ParameterValue": "restaurant-agent"` to `"ParameterValue": "hotel-agent"` for both AgentName and AgentType keys
3. Leave all other parameters unchanged

**AFTER CREATING**: Confirm and summarize:
- "✓ Created static/cloudformation/parameters/[agent-type]-agent.json"
- "**Summary of files created:**"
- "  1. agents/[agent-type]_agent/main.py - Your agent's business logic (A2A protocol implementation)"
- "  2. services/[agent-type]-agent/Dockerfile - Container packaging instructions"
- "  3. static/cloudformation/parameters/[agent-type]-agent.json - ECS service configuration"
- "These three files are everything needed to deploy your agent to AWS!"

### Step 5: Deploy to AWS ECS

**BEFORE DEPLOYMENT**: Explain the deployment process:
- "We're now ready to deploy your agent to AWS ECS using the deploy-agent.sh script."
- "This script performs a 3-step deployment:"
- "  **Step 1: Resources Stack** - Creates ECR repository + CloudWatch log group"
- "  **Step 2: Build & Push** - Builds Docker image and pushes to ECR (~3-4 minutes)"
- "  **Step 3: Service Stack** - Creates ECS service + registers in CloudMap (~2-3 minutes)"
- "Total time: ~5-10 minutes depending on image size and AWS API response times."

**Files created so far:**
- `agents/<agent-type>_agent/main.py` - Agent implementation
- `services/<agent-type>-agent/Dockerfile` - Container configuration
- `static/cloudformation/parameters/<agent-type>-agent.json` - Stack parameters

**Confirm deployment:**
Deployment takes 5-10 minutes and will build Docker image, push to ECR, and create ECS service.

Ask the user: **"Ready to deploy to AWS? This will take 5-10 minutes. (yes/no)"**

If confirmed, run the deployment script:

```bash
./scripts/deploy-agent.sh <agent-type>-agent
```

The script performs a 3-step deployment:
1. **Deploy Resources Stack** - Creates ECR repository + CloudWatch Logs
2. **Build & Push Image** - Builds Docker image and pushes to ECR
3. **Deploy Service Stack** - Creates ECS service + CloudMap registration

Wait for the script to complete. It will display:
- CloudMap service name
- ECS service name
- CloudWatch log group

### Step 6: Verify Deployment

After the deployment script completes successfully, verify your agent is running.

#### 6.1 Check ECS Service Status

```bash
aws ecs describe-services \
  --cluster a2a-workshop-cluster \
  --services a2a-<agent-type>-agent \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

**Expected output:**
```json
{
  "Status": "ACTIVE",
  "Running": 1,
  "Desired": 1
}
```

#### 6.2 Check CloudMap Registration

```bash
aws servicediscovery list-services \
  --query "Services[?contains(Name, '<agent-type>')].{Name:Name,Id:Id}"
```

**Expected:** Service `<agent-type>-agent` should appear in the list.

#### 6.3 Test via Orchestrator

Now test through the deployed system using Claude Code MCP:

**For simple agents:**
```
Find <agent-type> in Seattle
```

**For reasoning agents:**
```
Plan a <domain> for 10 people with $1000 for dining and entertainment in Seattle
```

The orchestrator should discover and invoke your newly deployed agent.

---

## Pattern-Specific Guidance

### Simple Agent (BaseAgent) - Hotel Example

**Mock data location:** `data/mock/hotel/locations.json`

**Key implementation:**
- `_define_capabilities()` - Single capability with input/output schemas
- `_process_task_impl()` - Extract location, call mock_factory, format response
- `_format_response()` - Domain-specific text formatting

**Response format example:**
```python
def _format_response(self, location: str, data: dict) -> str:
    hotels = data.get("hotels", [])
    response = f"Found {len(hotels)} hotels in {location}:\\n\\n"
    for hotel in hotels[:5]:
        name = hotel.get("name")
        price = hotel.get("price_per_night")
        rating = hotel.get("rating")
        amenities = ", ".join(hotel.get("amenities", [])[:3])
        response += f"• {name} - ${price}/night (Rating: {rating}/5) - {amenities}\\n"
    return response
```

### Reasoning Agent (AgenticBaseAgent) - Itinerary Example

**Pattern:** Based on budget_agent

**⚠️ CRITICAL: Class Name References**

When copying from budget_agent, you MUST update the class name in multiple places:
1. Class definition: `class ItineraryPlanningAgent(AgenticBaseAgent):`
2. Entry point type hint: `def get_agent() -> ItineraryPlanningAgent:`
3. Docstrings referencing the class

**Missing even ONE reference will cause deployment failure.** Use Find & Replace to ensure all occurrences are updated.

**Required tools (example):**
- `calculate_travel_time` - Estimate travel time between locations
- `check_opening_hours` - Verify venue hours
- `optimize_schedule` - Create optimal time-based itinerary
- `check_conflicts` - Detect scheduling conflicts

**System prompt structure:**
```
You are an itinerary planning specialist...

Your tools:
1. calculate_travel_time - Use for transit estimates
2. check_opening_hours - Verify venue availability
3. optimize_schedule - Create time-optimal itinerary

Step-by-step process:
1. Analyze all provided locations and times
2. Calculate travel times between venues
3. Check opening hours for conflicts
4. Create optimal schedule within time constraints
5. Return structured itinerary with timing details
```

**Capability definition:**
```python
AgentCapability(
    id="plan-itinerary",
    name="Plan Itinerary",
    description="Create time-optimized itineraries for multi-venue visits",
    service_type="reasoning",  # Mark as reasoning
    wait_for=True,  # Allow extra time for LLM
    input_schema={
        "type": "object",
        "properties": {
            "restaurants": {"type": "array"},
            "entertainment": {"type": "array"},
            "start_time": {"type": "string"},
            "end_time": {"type": "string"}
        },
        "required": ["restaurants", "entertainment", "start_time", "end_time"]
    }
)
```

---

## Troubleshooting

**"Agent not being called"**
- Check ECS service: `aws ecs list-services --cluster strands-agents-cluster`
- Check CloudMap: `aws servicediscovery list-services`
- Check agent card: `curl http://<agent-name>.strands-agents.local:8000/.well-known/agent.json`

**"Type errors in reasoning agent"**
- Convert string inputs to proper types: `budget = float(user_input.get("budget", 0))`
- Check orchestrator passes strings, convert as needed

**"Mock data not found"**
- Verify data file exists: `cat data/mock/<agent-type>/locations.json`
- Check category name matches: `mock_factory.get_data(category="hotel", ...)`

---

## Validation

After creating files, verify Python syntax:

```bash
python3 -m py_compile agents/<agent-type>_agent/main.py
```

No output means syntax is valid. **Full testing requires deployment** - proceed to Step 5 (Deploy to AWS ECS).

---

## Key Learnings

**Simple agents (BaseAgent):**
✅ Rule-based lookup pattern
✅ Mock data integration
✅ A2A capability definition
✅ FastAPI endpoint structure

**Reasoning agents (AgenticBaseAgent):**
✅ LLM-powered decision making
✅ Tool-based architecture with Strands
✅ System prompt engineering
✅ Complex multi-step reasoning

---

## Next Steps

After creating your agent:
1. Validate: `/workshop:validate-agent <agent-type>`
2. Deploy: `/workshop:deploy-agent <agent-type>`
3. Test through Claude Code MCP with natural language queries

**Need help?**
- For capability design: Use the `agent-architect` consultation agent
- For validation: Use the `agent-validator` consultation agent
- For deployment issues: Check CloudWatch logs in AWS Console
