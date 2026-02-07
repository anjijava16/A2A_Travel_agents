#!/usr/bin/env python3
"""
Workflow Generator - LLM-Powered Workflow Configuration Generation

Uses Claude Sonnet 4 to analyze user queries and available agent capabilities,
then generates optimal workflow configurations dynamically.

Key Features:
    - Dynamic pattern selection (map-reduce, sequential, conditional, etc.)
    - Semantic understanding of query intent
    - Optimal agent selection and ordering
    - Fallback to simple parallel execution on errors

Workflow Patterns:
    1. Map-Reduce: Parallel agent calls → Aggregate results
    2. Sequential: Agent chain (A → B → C)
    3. Conditional: Branch based on runtime data (if/then/else)
    4. Scatter-Gather: Broadcast to all → Collect all results
    5. Mixed: Combinations of above patterns

Usage:
    generator = WorkflowGenerator()
    workflow_config = generator.generate_workflow(
        user_query="Process my request using available information sources",
        discovered_agents={...}
    )
"""

import json
from typing import Any

from strands import Agent as StrandsAgent
from strands.models import BedrockModel
from strands.tools import tool

from lib.config import config
from lib.logger import get_logger

from .workflow_models import WorkflowConfig


class WorkflowGenerator:
    """
    Generate workflow configurations using Claude Sonnet 4.

    Analyzes queries and agent capabilities to produce executable workflow configs
    that optimize for the specific query intent.

    Configuration:
        Uses centralized core.config module for all settings.
        Override via environment variables with CORE_ prefix.
    """

    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
        max_tokens: int | None = None,
    ):
        """
        Initialize WorkflowGenerator.

        Args:
            model_id: Claude model ID (defaults to config.bedrock_model_id)
            region: AWS region (defaults to config.aws_region)
            max_tokens: Max tokens for generation (defaults to 2000)
        """
        self.model_id = model_id or config.bedrock_model_id
        self.region = region or config.aws_region
        self.max_tokens = max_tokens or 2000

        # Initialize logger
        self.logger = get_logger(context={"component": "WorkflowGenerator"})

        # Initialize Bedrock model
        try:
            self.bedrock_model = BedrockModel(
                model_id=self.model_id,
                streaming=False,
                region_name=self.region,
                max_tokens=self.max_tokens,
            )

            # Storage for tool call parameters (captured as side effect)
            self._tool_result = None

            # Define workflow generation tool using @tool decorator
            # The tool function captures parameters as a side effect
            @tool(
                name="generate_workflow",
                description="Generate an optimal workflow configuration for a user query",
            )
            def generate_workflow(
                pattern: str,
                reasoning: str,
                nodes: list[dict[str, Any]],
                flow: list[list[str]],
                metadata: dict[str, Any],
            ) -> dict[str, Any]:
                """Generate workflow configuration.

                Args:
                    pattern: Workflow execution pattern (map_reduce, sequential, conditional, scatter_gather, mixed, error)
                    reasoning: Why this pattern is optimal for the query
                    nodes: List of workflow nodes (agent calls, routers, joiners)
                    flow: Execution flow as stages of node IDs
                    metadata: Additional metadata about the workflow (query_analysis, estimated_agents)

                Returns:
                    Complete workflow configuration dictionary
                """
                # Store parameters as side effect so we can access them after agent runs
                workflow_data = {
                    "pattern": pattern,
                    "reasoning": reasoning,
                    "nodes": nodes,
                    "flow": flow,
                    "metadata": metadata,
                }
                self._tool_result = workflow_data

                # Return dict for LLM context
                return workflow_data

            self.strands_agent = StrandsAgent(
                model=self.bedrock_model,
                system_prompt=self._get_system_prompt(),
                tools=[generate_workflow],
            )

            self.logger.info(
                "Initialized WorkflowGenerator",
                extra={
                    "model_id": self.model_id,
                    "region": self.region,
                    "max_tokens": self.max_tokens,
                },
            )

        except Exception as e:
            self.logger.error(
                "Failed to initialize Bedrock model",
                extra={"model_id": self.model_id, "error": str(e)},
                exc_info=True,
            )
            raise

    def _get_system_prompt(self) -> str:
        """
        Generate comprehensive system prompt for workflow generation.

        Returns:
            System prompt teaching Claude about workflow patterns
        """
        return """You are an expert workflow architect. Your job is to analyze user queries and generate optimal workflow configurations for multi-agent orchestration.

You will be given:
1. A user query (any domain)
2. Available specialist agents with their capabilities

Your task:
- Analyze the query to understand dependencies between information needs
- Select relevant agents from the available list (NEVER make up agents)
- Use the generate_workflow tool to return a valid workflow configuration
- Choose the right pattern for the query characteristics

IMPORTANT: You MUST call the generate_workflow tool with your workflow configuration. Do not output JSON directly.

⚠️ CRITICAL - DOMAIN-AGNOSTIC CONSTRAINT ⚠️

The examples below use generic placeholder agent IDs (agent-a, agent-b, agent-c, etc.) for TEACHING PURPOSES ONLY.
These are NOT real agents. They DO NOT EXIST in your environment.

YOU MUST ONLY use agents from the "Available Specialist Agents" list provided in each request.
- NEVER reference agent-a, agent-b, agent-c, agent-d, agent-e, or agent-f in actual workflows
- ONLY use agent IDs that appear in the discovered agents list
- If an agent type isn't available, work with whatever agents ARE available (graceful degradation)
- Do NOT assume or hallucinate agents that weren't discovered

The system is completely domain-agnostic. It works across ANY domain (finance, healthcare, travel, retail, etc.).
You have zero built-in knowledge of what agents exist - you learn this dynamically from discovery.

## Workflow Patterns

### 1. MAP-REDUCE (Parallel → Aggregate)
**When to use:**
- Multiple agents can work independently
- No dependencies between agent results
- Results need to be combined

**Example Query:** "Process my request using available information sources"

**Workflow:**
```json
{
  "pattern": "map_reduce",
  "nodes": [
    {"id": "weather_call", "type": "agent_call", "agent_id": "agent-a"},
    {"id": "events_call", "type": "agent_call", "agent_id": "agent-b"},
    {"id": "restaurants_call", "type": "agent_call", "agent_id": "agent-c"},
    {"id": "aggregate", "type": "joiner", "strategy": "merge"}
  ],
  "flow": [
    ["weather_call", "events_call", "restaurants_call"],
    ["aggregate"]
  ]
}
```

### 2. SEQUENTIAL (A → B → C)
**When to use:**
- Agent B needs output from Agent A
- There's a clear pipeline/dependency chain
- Each step builds on previous results

**Example Query:** "Process my multi-step request sequentially"

**Workflow:**
```json
{
  "pattern": "sequential",
  "nodes": [
    {"id": "hotel_search", "type": "agent_call", "agent_id": "agent-e"},
    {"id": "restaurant_search", "type": "agent_call", "agent_id": "agent-c"}
  ],
  "flow": [
    ["hotel_search"],
    ["restaurant_search"]
  ]
}
```

### 3. CONDITIONAL (If/Then/Else)
**When to use:**
- Query requires branching logic
- Different paths based on runtime data
- Weather-dependent or condition-dependent queries

**Example Query:** "Process my request with conditional logic"

**Workflow:**
```json
{
  "pattern": "conditional",
  "nodes": [
    {"id": "weather_check", "type": "agent_call", "agent_id": "agent-a"},
    {
      "id": "weather_condition",
      "type": "condition",
      "expression": "data.get('weather_data', {}).get('condition', '').lower() in ['rain', 'heavy rain', 'drizzle']",
      "true_branch": "indoor_router",
      "false_branch": "outdoor_router"
    },
    {
      "id": "indoor_router",
      "type": "router",
      "parallel": true,
      "rules": [
        {"target": "agent-b"},
        {"target": "agent-c"}
      ]
    },
    {
      "id": "outdoor_router",
      "type": "router",
      "parallel": true,
      "rules": [
        {"target": "agent-b"},
        {"target": "agent-f"}
      ]
    },
    {"id": "aggregate", "type": "joiner", "strategy": "merge"}
  ],
  "flow": [
    ["weather_check"],
    ["weather_condition"],
    ["aggregate"]
  ]
}
```

### 4. SCATTER-GATHER (Broadcast → Collect All)
**When to use:**
- Query needs comprehensive information from all agents
- No specific filtering needed
- Want maximum coverage

**Example Query:** "Provide comprehensive information on my topic"

**Workflow:**
```json
{
  "pattern": "scatter_gather",
  "nodes": [
    {
      "id": "broadcast",
      "type": "router",
      "parallel": true,
      "rules": [
        {"target": "agent-a"},
        {"target": "agent-b"},
        {"target": "agent-c"},
        {"target": "agent-e"}
      ]
    },
    {"id": "gather", "type": "joiner", "strategy": "merge"}
  ],
  "flow": [
    ["broadcast"],
    ["gather"]
  ]
}
```

## ADK Primitives Reference

### agent_call
Calls an A2A agent with optional input mapping.

**Basic agent_call** (uses user query directly):
```json
{
  "id": "weather_call",
  "type": "agent_call",
  "agent_id": "agent-a"
}
```

**agent_call with input_mapping** (maps data from previous stages):
```json
{
  "id": "filter_results",
  "type": "agent_call",
  "agent_id": "agent-d",
  "input_mapping": {
    "locations": "$.events_call.events",
    "center_lat": "$.coords_call.latitude",
    "center_lon": "$.coords_call.longitude"
  }
}
```

**CRITICAL - Data Mapping Rules:**

You MUST provide `input_mapping` for agents that need data from previous stages OR from the user query.

**🚨 SCHEMA FIELD NAME RULE - READ THIS CAREFULLY:**

When mapping data from one agent's output to another agent's input, you MUST use the EXACT field names from the source agent's `output_schema`. DO NOT invent, assume, or generalize field names.

**WRONG - Inventing field names:**
```json
// agent-a output_schema has: {"items": [...]}
// You write: "data": "$.agent_a_call.data"  ❌ WRONG - "data" doesn't exist in output_schema
```

**CORRECT - Using exact schema field names:**
```json
// agent-a output_schema has: {"items": [...]}
// agent-b input_schema expects: {"data": [...]}
// You write: "data": "$.agent_a_call.items"  ✅ CORRECT - maps "items" to "data"
```

**How to Create Correct Mappings - Step by Step:**

1. **Read the TARGET agent's input_schema** - What parameters does it need?
   - Example: agent-b needs `"data"` (array parameter)

2. **Read the SOURCE agent's output_schema** - What does it actually return?
   - Example: agent-a returns `"items"` (array)
   - Example: agent-c returns `"results"` (array)

3. **Create the mapping using SOURCE field name, TARGET parameter name:**
   - Format: `"<target_param>": "$.<source_node>.<source_field>"`
   - Example: `"data": "$.agent_a_call.items"` (maps items → data)
   - Example: `"data": "$.agent_c_call.results"` (maps results → data)

**Common Mistakes to AVOID:**

❌ **Don't assume generic names**: Just because the target needs "data" doesn't mean the source returns "data"
❌ **Don't use plural/singular conversions**: If source has "items", don't write "item"
❌ **Don't abbreviate**: If source has "results", don't write "res" or "output"
❌ **Always check BOTH schemas**: Never guess - read both input_schema and output_schema

**TWO SOURCES OF DATA:**

1. **From Previous Agents** (using JSONPath):
   - Check previous agents' `output_schema` for available fields
   - Use JSONPath to map data: `$.node_id.field_name`
   - **Use the EXACT field name from output_schema, not a made-up name**

2. **From User Query** (using literal values):
   - Analyze the user query to extract parameters
   - Use LITERAL VALUES for query-derived data
   - **CRITICAL**: ALL values must be STRINGS (even numbers): `"count": "5"` not `"count": 5`

**Step-by-Step Process:**

1. **Check agent's `input_schema.required` fields** - What does the agent need?
2. **Determine data source for EACH required field:**
   - If it comes from another agent's output → Use JSONPath mapping
   - If it should be extracted from user query → Use LITERAL VALUE
3. **Generate complete input_mapping** with ALL required fields

**CRITICAL - User Query Extraction:**

When you see field descriptions like:
- "The specific place mentioned in the user's query"
- "The landmark or neighborhood mentioned"
- "Extract from query what comes after 'near'"

You MUST analyze the user query, extract that information, and provide it as a LITERAL VALUE in input_mapping.

JSONPath Syntax (for agent-to-agent mappings):
- `$.node_id.field_name` - Access field from specific node result
- `$.node_id.nested.field` - Access nested fields
- `$.node_id.array[0]` - Access array elements (usually just pass whole array)

**Example 1 - Agent-to-Agent Mapping:**
```
agent-d needs: ["data" (array), "param_a" (number), "param_b" (number)]
Previous stages:
  - agent_a_call returned: {items: [...], total_count: 20}
  - agent_b_call returned: {value_x: 47.6, value_y: -122.3}

Generated input_mapping:
  "data": "$.agent_a_call.items"          // From previous agent (JSONPath)
  "param_a": "$.agent_b_call.value_x"     // From previous agent (JSONPath)
  "param_b": "$.agent_b_call.value_y"     // From previous agent (JSONPath)
```

**Example 2 - Mixed (Agent Data + Query Extraction):**
```
User Query: "Process items with [specific parameter]"

agent-c needs: ["items" (array), "parameter" (string)]
Previous stages:
  - agent_a_call returned: {results: [...], count: 15}

Agent's parameter description: "The specific value mentioned in user's query"

Generated input_mapping:
  "items": "$.agent_a_call.results"           // From previous agent (JSONPath)
  "parameter": "[extracted parameter value]"  // Extracted from query (LITERAL STRING)
```

**Example 3 - Pure Query Extraction:**
```
User Query: "[Action] with [parameter]"

agent-b needs: ["parameter" (string)]
No previous stages

Agent's parameter description: "Parameter from user query"

Generated input_mapping:
  "parameter": "[extracted parameter]"  // Extracted from query (LITERAL STRING)
```

### router
Routes work to multiple targets (parallel or sequential).
```json
{
  "id": "parallel_router",
  "type": "router",
  "parallel": true,
  "rules": [
    {"target": "agent-a"},
    {"target": "agent-b", "condition": "data.get('value', 0) > 50"}
  ]
}
```

### joiner
Aggregates results from multiple sources.
```json
{
  "id": "aggregate",
  "type": "joiner",
  "strategy": "merge",
  "wait_for": ["node-a", "node-b"]
}
```
Strategies:
- "merge" (combine dicts) - DEFAULT for ALL final Joiners and most aggregation. The orchestrator always synthesizes at the end, so Joiners should only combine data, not synthesize it.
- "concatenate" (create list of results) - For preserving multiple perspectives or creating lists
- "vote" (return most common result for consensus) - For selecting best answer from multiple sources
- "synthesize" (LLM synthesis) - ONLY for intermediate branch Joiners that create summaries for next decision stage. NEVER for final Joiners (wastes ~140K tokens via redundant synthesis).

**CRITICAL RULES:**
1. Final Joiner (last stage before orchestrator returns) → MUST use "merge"
2. Simple map-reduce (parallel agents → aggregate) → MUST use "merge"
3. Router-based conditionals → MUST use "merge"
4. Branch Joiners in conditionals → MAY use "synthesize" ONLY IF creating summaries for comparison/selection

**CRITICAL - wait_for Semantics:**

The `wait_for` field controls which node results are passed to synthesis. This is ESSENTIAL for preventing two issues:
1. **Stage history pruning**: Nodes not explicitly referenced by future stages will be removed to save tokens
2. **Synthesis receiving wrong data**: Without wait_for, synthesis may miss context data it needs

**WHEN to populate wait_for:**
- **ALWAYS** for joiner nodes with "synthesize" strategy
- **OPTIONAL** for other joiner strategies (merge/concatenate/vote typically receive all inputs)

**HOW to determine what to include in wait_for:**

Analyze the workflow pattern and apply these rules:

**Pattern 1: Sequential Pipeline (load → filter → refine)**
```
Example: Load 1000 restaurants → Filter to nearby → Refine to vegan
```
- **Include**: ONLY the final refined result (e.g., vegan restaurants)
- **Exclude**: Intermediate bulk data (e.g., all 1000 restaurants, all nearby restaurants)
- **Reasoning**: User wants refined results, not intermediate data

**Pattern 2: Parallel Context Agents**
```
Example: Get weather + Find events + Find restaurants (all independent)
```
- **Include**: ALL parallel results
- **Exclude**: Nothing (all results are valuable)
- **Reasoning**: Each agent provides unique information user needs

**Pattern 3: Mixed Pattern (parallel load → filter + independent context)**
```
Example: (Load entertainment + Load events + Load restaurants + Get weather) → (Filter entertainment + Filter events + Filter restaurants) → Synthesis
```
- **Include**: All filtered results + context agents (e.g., filtered entertainment, filtered events, filtered restaurants, weather)
- **Exclude**: Bulk unfiltered loaders (e.g., load_entertainment, load_events, load_restaurants)
- **Reasoning**: Filtered data is relevant, context provides decision-making info, bulk data is noise

**Decision Tree - Include a node in wait_for if:**

1. **It's in the final stage before synthesis** (e.g., agent enrichment calls)
2. **It provides context/insights** rather than bulk data (check: is output_size "large"? Check: is it a filter's input?)
3. **It's NOT consumed by an enhancement agent** (e.g., geography filters restaurants, so exclude raw restaurants)
4. **It's parallel to other synthesis inputs** (e.g., weather + events both go to synthesis)

**Decision Tree - Exclude a node from wait_for if:**

1. **Its output is fed into another agent** that IS included (e.g., load_restaurants → filter_nearby → synthesis: exclude load_restaurants, include filter_nearby)
2. **It's bulk data** that was filtered (e.g., 1000 restaurants before proximity filter)
3. **Its output_size is "large"** and a downstream agent refined it to "small" or "medium"

**Using Agent Metadata for wait_for Decisions:**

Agents declare metadata you can use:
- `service_type`: "primary" (include) or "enhancement" (check if its output is further refined)
- `provides_for`: If agent A provides_for agent B, and B is included, exclude A
- `output_size`: If "large", prefer downstream refined versions

**Example 1: Simple Map-Reduce (CORRECT)** ✅

```json
{
  "nodes": [
    {"id": "agent_a", "type": "agent_call", "agent_id": "location-loader"},
    {"id": "agent_b", "type": "agent_call", "agent_id": "restaurant-agent"},
    {"id": "agent_c", "type": "agent_call", "agent_id": "weather-agent"},
    {"id": "final_aggregate", "type": "joiner", "strategy": "merge", "wait_for": ["agent_a", "agent_b", "agent_c"]}
  ],
  "flow": [
    ["agent_a", "agent_b", "agent_c"],
    ["final_aggregate"]
  ]
}
```
**Why**: Final Joiner uses "merge" (combines dicts), orchestrator synthesizes once. Efficient.

**Example 2: Pipeline with Filtering (CORRECT)** ✅

```json
{
  "nodes": [
    {"id": "load_bulk_data", "type": "agent_call", "agent_id": "location-loader"},
    {"id": "apply_filter", "type": "agent_call", "agent_id": "geography-agent", "input_mapping": {"items": "$.load_bulk_data.items"}},
    {"id": "refine_results", "type": "agent_call", "agent_id": "filter-agent", "input_mapping": {"items": "$.apply_filter.filtered_items"}},
    {"id": "get_context", "type": "agent_call", "agent_id": "weather-agent"},
    {"id": "final_aggregate", "type": "joiner", "strategy": "merge", "wait_for": ["refine_results", "get_context"]}
  ],
  "flow": [
    ["load_bulk_data", "get_context"],
    ["apply_filter"],
    ["refine_results"],
    ["final_aggregate"]
  ]
}
```
**Why**: Final Joiner uses "merge" to combine refined results + context. Orchestrator synthesizes.
**wait_for excludes**: load_bulk_data, apply_filter (intermediate steps, already refined)

**Example 3: WRONG - Final Joiner Synthesizes** ❌

```json
{
  "nodes": [
    {"id": "agent_a", "type": "agent_call"},
    {"id": "agent_b", "type": "agent_call"},
    {"id": "final_aggregate", "type": "joiner", "strategy": "synthesize"}  // ❌ WRONG
  ]
}
```
**Why wrong**: Final Joiner synthesizes (140K tokens), then orchestrator synthesizes again (redundant!). The auto-correction will fix this to "merge".

### condition
Conditional branching.
```json
{
  "id": "check_weather",
  "type": "condition",
  "expression": "data.get('temp', 0) > 80",
  "true_branch": "hot_weather_router",
  "false_branch": "normal_router"
}
```

## Enhancement Services Pattern

Some agents provide **enhancement services** that augment primary agents rather than directly serving end users.

**Agent Relationship Metadata:**

Agents may declare relationships via these optional fields:
- `optional_enhancements`: List of agent IDs that can enhance this capability
- `provides_for`: List of agent IDs this agent provides services for
- `service_type`: "primary" (user-facing) or "enhancement" (supports other agents)

**When to Include Enhancement Services:**

1. **Analyze Query Semantics**: Match query against all agent tags/examples to understand intent
2. **Select Primary Agents**: Choose agents that directly address the user's query
3. **Check for Enhancements**: If primary agent declares `optional_enhancements`, check if enhancement would add value
4. **Evaluate Benefit**: Use semantic understanding to decide if enhancement improves the response
5. **Coordinate Execution**: Determine if enhancement can run in parallel OR needs sequential execution

**CRITICAL - Check Data Dependencies:**

Before deciding parallel vs sequential execution, ALWAYS CHECK the agent capability's `input_schema` for `required` fields:

- If a capability requires data that comes from ANOTHER agent's output (e.g., "items", "results", "data"), use **SEQUENTIAL** execution
- If all required fields can be derived from the user query alone, use **PARALLEL** execution

**How to Identify Dependencies:**

1. Look at each agent's capability `input_schema`
2. Check the `required` array
3. Determine if those fields come from:
   - **User query** (can extract directly) → Parallel OK
   - **Another agent's output** (needs that agent to run first) → Must be Sequential

**Example - Parallel (No Dependencies):**

```json
// Agent A requires: ["user_query", "location"]  ← Both from user input
// Agent B requires: ["category", "limit"]       ← Both from user input
// These can run in parallel

{
  "pattern": "map_reduce",
  "nodes": [
    {"id": "call_a", "type": "agent_call", "agent_id": "agent-a"},
    {"id": "call_b", "type": "agent_call", "agent_id": "agent-b"},
    {"id": "aggregate", "type": "joiner", "strategy": "merge"}
  ],
  "flow": [
    ["call_a", "call_b"],
    ["aggregate"]
  ]
}
```

**Example - Sequential (Has Dependencies):**

```json
// Agent A requires: ["user_query"]          ← From user
// Agent B requires: ["items", "filter"]     ← "items" must come from Agent A output
// Agent B depends on Agent A - must be sequential

{
  "pattern": "sequential",
  "reasoning": "Agent B requires data from Agent A's output",
  "nodes": [
    {"id": "call_a", "type": "agent_call", "agent_id": "agent-a"},
    {"id": "call_b", "type": "agent_call", "agent_id": "agent-b"},
    {"id": "aggregate", "type": "joiner", "strategy": "merge"}
  ],
  "flow": [
    ["call_a"],
    ["call_b"],
    ["aggregate"]
  ]
}
```

**Key Principle**: Let the agent capability schemas guide your workflow design. Check `input_schema.required` fields to identify true data dependencies. Use parallel execution whenever possible for performance, but switch to sequential when one agent needs another agent's output data.

## Agent Self-Description Pattern - READ AGENT DECLARATIONS

**CRITICAL PRINCIPLE: Agents declare HOW they should be used.**

Your workflow decisions should be guided by what agents TELL YOU about themselves, not by assumptions or domain knowledge. Each agent's capability includes rich self-descriptions that explain:
- When to use them
- What data they expect
- How they relate to other agents
- Their role in multi-step workflows

**How to Discover Composition Patterns:**

1. **Read Agent Descriptions**: Agent capability descriptions contain USAGE instructions
   - Look for sections like "USAGE:", "WORKFLOW:", "WHY", "PREFERRED USAGE"
   - These guide you on agent composition patterns

2. **Respect Agent Declarations**: If an agent says "Use me after loading" or "Use me before refinement", follow that guidance
   - Agents know their responsibilities and dependencies
   - Their descriptions encode workflow best practices

3. **Follow Declared Patterns**: Agents may describe multi-step patterns like:
   - "Load → Filter → Refine" (data loading, then spatial filtering, then domain refinement)
   - "Primary → Enhancement" (primary agent, then enhancement service)
   - "Objective → Subjective" (hard data filtering first, soft selection second)

4. **Check Service Types**: `service_type` field indicates agent's role
   - `"primary"`: Directly serves user queries
   - `"enhancement"`: Supports other agents (check `provides_for` field)

**Example Discovery Process:**

```
User Query: "Process my data set"

Step 1: Discover agents
- agent-loader: description says "I load complete datasets (unfiltered)"
- agent-filter: description says "Use me after loading to filter by criteria"
- agent-refiner: description says "Use me after filtering for domain-specific refinement"

Step 2: Infer Pattern from Descriptions
- agent-loader says "no filtering" → It returns ALL data
- agent-filter says "Use me after loading" → Depends on loader output
- agent-refiner says "Use me after filtering" → Can work with filtered OR unfiltered

Step 3: Compose Workflow
Sequential pattern: load → filter → refine
Reasoning: Agents explicitly declare dependencies through usage instructions
```

**Anti-Pattern - DON'T DO THIS:**
```
❌ Ignoring agent descriptions and assuming patterns based on agent names
❌ Making up workflows without reading capability descriptions
❌ Hardcoding domain knowledge instead of reading agent metadata
```

**Best Practice - DO THIS:**
```
✅ Read each agent's capability description for usage instructions
✅ Respect declared dependencies ("Use me after X")
✅ Follow efficiency guidance ("Filter 2,000 → 20 first, then select 10")
✅ Trust agent expertise about their role and optimal usage
```

**Remember**: You have ZERO built-in domain knowledge. Learn everything from agent declarations. Agents are the experts on how they should be used.

## Output Format

Generate workflow configuration as JSON:
```json
{
  "pattern": "map_reduce|sequential|conditional|scatter_gather|mixed",
  "reasoning": "Why this pattern is optimal for the query",
  "nodes": [
    // List of node configurations
  ],
  "flow": [
    ["stage1_node_ids"],
    ["stage2_node_ids"],
    ["stage3_node_ids"]
  ],
  "metadata": {
    "query_analysis": "Brief analysis of query intent",
    "estimated_agents": 3
  }
}
```

## Important Guidelines

1. **CRITICAL - Agent Constraint**: You MUST ONLY use agents from the "Available Specialist Agents" list provided above. NEVER reference agents that don't exist.

2. **CRITICAL - Selective Agent Inclusion**: Analyze the user query semantically. ONLY include agents that are directly relevant to the query. Do NOT include every available agent "just in case."

   Examples:
   - Query: "What's the weather in Seattle?" → Include: weather-agent ONLY
   - Query: "Find restaurants in Seattle" → Include: restaurant-agent ONLY (not weather, not budget)
   - Query: "Plan a $800 trip to Seattle" → Include: budget-agent, events-agent, restaurant-agent, weather-agent
   - Query: "What should I do?" → Include: events-agent, weather-agent (NOT budget unless mentioned)

3. **Graceful Degradation Philosophy**: If a RELEVANT agent is unavailable, work with available alternatives. Graceful degradation means "work with what you have when something is missing" NOT "include everything just in case."

4. **Prefer Parallel When Possible**: Parallelism improves performance

5. **Use Sequential Only When Necessary**: When there are true dependencies

6. **Keep It Simple**: Don't over-engineer - simplest pattern that works

7. **Agent Selection**: Select agents that directly address the query. If the query doesn't mention budget, don't include budget-agent. If it doesn't ask about weather, don't include weather-agent.

8. **Flow Stages**: Each stage executes before next stage begins

9. **Node IDs**: Use descriptive, unique IDs (e.g., "weather_call", "indoor_router")

10. **Condition Expressions**: Use safe Python expressions with data.get() pattern

## Graceful Degradation - Work with What You Have

**CRITICAL**: The system is designed for dynamic agent availability. Agents can be added or removed at any time. NEVER return an error workflow due to "missing" agents.

**Core Principles**:

1. **Always Try to Help**: Use whatever agents are available, even if the answer will be incomplete
2. **Explain Limitations**: In your reasoning, note which capabilities are missing and how that affects results
3. **Maximize Coverage**: Include ALL agents that could contribute anything relevant to the query
4. **Degrade Quality, Not Availability**: Return partial results rather than no results

**Graceful Degradation Patterns**:

### When a filtering/refinement agent is unavailable:
- ✅ **Do**: Return unfiltered results from available agents
- ❌ **Don't**: Return error saying filtering is required
- **Reasoning note**: "Without [agent-type], returning unfiltered results. User will get complete list instead of refined subset."

### When a primary capability agent is unavailable:
- ✅ **Do**: Use related agents that could provide partial information
- ❌ **Don't**: Return error saying capability is required
- **Reasoning note**: "Without [agent-type], using [available-agents] to provide related information. Results may be less specific but still helpful."

### When only ONE agent is available:
- ✅ **Do**: Use that agent and note limitations
- ❌ **Don't**: Return error saying more agents are needed
- **Reasoning note**: "Limited agents available. Providing best possible answer with [agent-name]. Results incomplete but useful."

### When NO agents match the query perfectly:
- ✅ **Do**: Use agents with any potential relevance
- ❌ **Don't**: Return error saying no capable agents exist
- **Reasoning note**: "No agents directly match query. Using [available-agents] to provide tangentially related information."

**Example Workflow Structure** (generic - works for any domain):
```json
{
  "pattern": "map_reduce",
  "reasoning": "[Explain what's available, what's missing, and how that affects the answer quality]",
  "nodes": [
    {"id": "agent_1_call", "type": "agent_call", "agent_id": "[first-available-agent]"},
    {"id": "agent_2_call", "type": "agent_call", "agent_id": "[second-available-agent]"},
    {"id": "aggregate", "type": "joiner", "strategy": "merge"}
  ],
  "flow": [
    ["agent_1_call", "agent_2_call"],
    ["aggregate"]
  ]
}
```

## Fallback Strategy

When uncertain about workflow structure, use a simple map-reduce pattern with agents that are semantically relevant to the query. Analyze query keywords and intent before selecting agents - do NOT include all agents by default.
"""

    def generate_workflow(
        self, user_query: str, discovered_agents: dict[str, dict[str, Any]]
    ) -> WorkflowConfig:
        """
        Generate workflow configuration for user query.

        Args:
            user_query: User's question or request
            discovered_agents: Dictionary mapping agent_id -> agent_info
                              (includes base_url, agent_card, etc.)

        Returns:
            WorkflowConfig object with nodes and execution flow

        Raises:
            ValueError: If query is empty or no agents provided
            RuntimeError: If LLM invocation fails critically
        """
        # Validation
        if not user_query or not user_query.strip():
            raise ValueError("Query cannot be empty")

        if not discovered_agents:
            raise ValueError("No agents provided")

        self.logger.info(
            "Generating workflow",
            extra={"query": user_query[:100], "num_agents": len(discovered_agents)},
        )

        # Build agent capability summary
        agent_summary = self._build_agent_summary(discovered_agents)

        # Create prompt for LLM
        prompt = f"""User Query: "{user_query}"

Available Specialist Agents:
{agent_summary}

Analyze this query and use the generate_workflow tool to create an optimal workflow configuration."""

        try:
            # Clear previous tool result
            self._tool_result = None

            # Invoke LLM with tool calling
            self.logger.info("Invoking Claude Sonnet 4 for workflow generation")
            _ = self.strands_agent(prompt)  # Tool result captured in callback

            # Check if tool was called and captured parameters
            if self._tool_result is None:
                self.logger.warning(
                    "Tool was not called or parameters not captured, using fallback"
                )
                return self._create_fallback_workflow(user_query, discovered_agents)

            pattern = self._tool_result.get("pattern")
            num_nodes = len(self._tool_result.get("nodes", []))
            num_stages = len(self._tool_result.get("flow", []))
            self.logger.debug(
                f"Tool result captured successfully: pattern={pattern} num_nodes={num_nodes} num_stages={num_stages}"
            )

            # Build workflow from captured tool parameters
            workflow_config = self._build_workflow_from_tool_response(
                self._tool_result, user_query, discovered_agents
            )

            self.logger.debug(
                f"Workflow generated successfully: pattern={workflow_config.pattern} num_nodes={len(workflow_config.nodes)} num_stages={len(workflow_config.flow)}"
            )

            return workflow_config

        except Exception as e:
            # Other exceptions (JSON parsing, LLM errors) - use fallback
            query_preview = user_query[:100]
            self.logger.error(
                f"Workflow generation failed: error={e!s} query={query_preview}"
            )
            # Return fallback workflow
            self.logger.warning("Using fallback workflow (simple parallel)")
            return self._create_fallback_workflow(user_query, discovered_agents)

    def _build_agent_summary(self, discovered_agents: dict[str, dict[str, Any]]) -> str:
        """
        Build human-readable summary of available agents for LLM.

        Args:
            discovered_agents: Dictionary of agent_id -> agent_info

        Returns:
            Formatted string describing all agents
        """
        summary_lines = []

        for agent_id, agent_info in discovered_agents.items():
            agent_card = agent_info.get("agent_card", {})
            agent_name = agent_card.get("name", agent_id)
            description = agent_card.get("description", "No description")

            # Skip orchestrators
            if (
                "orchestrator" in agent_name.lower()
                or "orchestration" in agent_name.lower()
            ):
                continue

            summary_lines.append(f"\n{agent_id}:")
            summary_lines.append(f"  Name: {agent_name}")
            summary_lines.append(f"  Description: {description}")

            # List capabilities with schemas
            skills = agent_card.get("skills", [])
            if skills:
                summary_lines.append("  Capabilities:")
                for skill in skills[:3]:  # Limit to first 3 for brevity
                    if isinstance(skill, dict):
                        skill_name = skill.get("name", "Unknown")
                        skill_desc = skill.get("description", "")
                        input_schema = skill.get("input_schema", {})
                        output_schema = skill.get("output_schema", {})
                    else:
                        skill_name = skill.name if hasattr(skill, "name") else "Unknown"
                        skill_desc = (
                            skill.description if hasattr(skill, "description") else ""
                        )
                        input_schema = getattr(skill, "input_schema", {})
                        output_schema = getattr(skill, "output_schema", {})

                    summary_lines.append(f"    - {skill_name}: {skill_desc}")

                    # Add input schema details
                    if input_schema and "properties" in input_schema:
                        summary_lines.append("      Input:")
                        required_fields = input_schema.get("required", [])
                        for field_name, field_def in input_schema["properties"].items():
                            field_type = field_def.get("type", "unknown")
                            field_desc = field_def.get("description", "")
                            is_required = (
                                "required"
                                if field_name in required_fields
                                else "optional"
                            )
                            summary_lines.append(
                                f"        - {field_name} ({field_type}, {is_required}): {field_desc}"
                            )

                            # Add enum constraint if present
                            enum_values = field_def.get("enum")
                            if enum_values:
                                enum_str = ", ".join(f'"{v}"' for v in enum_values)
                                summary_lines.append(
                                    f"          Valid values: [{enum_str}]"
                                )

                    # Add output schema details
                    if output_schema and "properties" in output_schema:
                        summary_lines.append("      Output:")
                        for field_name, field_def in output_schema[
                            "properties"
                        ].items():
                            field_type = field_def.get("type", "unknown")
                            field_desc = field_def.get("description", "")
                            summary_lines.append(
                                f"        - {field_name} ({field_type}): {field_desc}"
                            )

        return "\n".join(summary_lines)

    def _parse_workflow_response(
        self,
        llm_response: str,
        user_query: str,
        discovered_agents: dict[str, dict[str, Any]],
    ) -> WorkflowConfig:
        """
        Parse LLM JSON response into WorkflowConfig.

        Args:
            llm_response: Raw LLM output (should contain JSON)
            user_query: Original user query
            discovered_agents: Available agents

        Returns:
            WorkflowConfig object

        Raises:
            RuntimeError: If parsing fails
        """
        try:
            # Extract JSON from response using multiple strategies
            json_str = llm_response.strip()

            # Strategy 1: Try parsing directly (handles clean responses)
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # Strategy 2: Remove markdown fences and try again
                cleaned = json_str
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                try:
                    data = json.loads(cleaned)
                except json.JSONDecodeError:
                    # Strategy 3: Extract JSON object with proper brace matching
                    # LLM may include thinking before/after the JSON
                    start_idx = cleaned.find("{")
                    if start_idx == -1:
                        raise json.JSONDecodeError(
                            "No JSON object found", cleaned, 0
                        ) from None

                    # Find matching closing brace using brace counting
                    brace_count = 0
                    end_idx = -1
                    in_string = False
                    escape_next = False

                    for i in range(start_idx, len(cleaned)):
                        char = cleaned[i]

                        if escape_next:
                            escape_next = False
                            continue

                        if char == "\\":
                            escape_next = True
                            continue

                        if char == '"' and not escape_next:
                            in_string = not in_string
                            continue

                        if not in_string:
                            if char == "{":
                                brace_count += 1
                            elif char == "}":
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i
                                    break

                    if end_idx == -1:
                        raise json.JSONDecodeError(
                            "No matching closing brace found", cleaned, 0
                        ) from None

                    json_str = cleaned[start_idx : end_idx + 1]
                    data = json.loads(json_str)

            # Extract fields
            pattern = data.get("pattern", "map_reduce")
            nodes = data.get("nodes", [])
            flow = data.get("flow", [])
            reasoning = data.get("reasoning", "")
            metadata = data.get("metadata", {})

            # Add query and reasoning to metadata
            metadata["query"] = user_query
            metadata["llm_reasoning"] = reasoning

            # Check if this is an error workflow (missing capabilities)
            if pattern == "error" or metadata.get("error") == "missing_capabilities":
                missing_agents = metadata.get("missing_agents", [])
                required_capabilities = metadata.get("required_capabilities", [])
                self.logger.warning(
                    f"LLM detected missing capabilities: missing_agents={missing_agents} required_capabilities={required_capabilities} reasoning={reasoning}"
                )

                # Return error workflow config (don't raise exception)
                missing_agents = metadata.get("missing_agents", ["unknown"])
                error_message = f"Cannot fulfill query - missing required agents: {', '.join(missing_agents)}. Reason: {reasoning}"

                return WorkflowConfig(
                    pattern="error",
                    nodes=[],
                    flow=[],
                    metadata=metadata,
                    error_info={
                        "missing_agents": metadata.get("missing_agents", []),
                        "required_capabilities": metadata.get(
                            "required_capabilities", []
                        ),
                        "message": error_message,
                    },
                )

            # Validate that all referenced agents exist
            referenced_agents = set()
            for node in nodes:
                if node.get("type") == "agent_call":
                    agent_id = node.get("agent_id")
                    if agent_id:
                        referenced_agents.add(agent_id)

            missing = referenced_agents - set(discovered_agents.keys())
            if missing:
                available = list(discovered_agents.keys())
                self.logger.error(
                    f"Workflow references non-existent agents: missing={list(missing)} available={available}"
                )
                raise RuntimeError(
                    f"Workflow references agents that don't exist: {', '.join(missing)}. "
                    f"Available agents: {', '.join(discovered_agents.keys())}"
                ) from None

            # Create workflow config
            workflow_config = WorkflowConfig(
                pattern=pattern, nodes=nodes, flow=flow, metadata=metadata
            )

            # Validate workflow
            validation_errors = workflow_config.validate()
            if validation_errors:
                self.logger.warning(
                    f"Workflow validation errors: errors={validation_errors}"
                )
                # Still return it - executor will handle errors

            # Check for synthesize joiners without wait_for
            for node in workflow_config.nodes:
                if (
                    node.get("type") == "joiner"
                    and node.get("strategy") == "synthesize"
                ):
                    if not node.get("wait_for"):
                        self.logger.warning(
                            f"Joiner node '{node.get('id')}' uses 'synthesize' strategy but lacks 'wait_for' list. "
                            f"This may cause stage history pruning to remove context data needed for synthesis. "
                            f"Consider adding 'wait_for' to explicitly specify which node results should be included."
                        )

            # Auto-correct final Joiners that use synthesize strategy
            # The orchestrator ALWAYS synthesizes at the end, so final Joiners should only merge/combine data
            if workflow_config.flow:
                final_stage = workflow_config.flow[-1]
                for node_id in final_stage:
                    # Find the node
                    node = next(
                        (n for n in workflow_config.nodes if n.get("id") == node_id),
                        None,
                    )
                    if node and node.get("type") == "joiner":
                        if node.get("strategy") == "synthesize":
                            node["strategy"] = "merge"
                            self.logger.info(
                                f"🔧 Auto-corrected final Joiner '{node_id}': strategy=synthesize → strategy=merge. "
                                f"Reason: Orchestrator always synthesizes final results, so final Joiner should only combine data. "
                                f"This saves ~140K tokens per query by avoiding redundant synthesis."
                            )

            return workflow_config

        except json.JSONDecodeError as e:
            response_preview = llm_response[:200].replace(chr(10), " ")
            self.logger.error(
                f"Failed to parse LLM JSON: error={e!s} response_preview={response_preview}"
            )
            raise RuntimeError(f"Invalid JSON from LLM: {e}") from e

        except Exception as e:
            self.logger.error(f"Failed to parse workflow response: error={e!s}")
            raise RuntimeError(f"Workflow parsing failed: {e}") from e

    def _build_workflow_from_tool_response(
        self,
        tool_data: dict[str, Any],
        user_query: str,
        discovered_agents: dict[str, dict[str, Any]],
    ) -> WorkflowConfig:
        """
        Build WorkflowConfig from structured tool response.

        Args:
            tool_data: Dictionary from tool call with workflow fields
            user_query: Original user query
            discovered_agents: Available agents

        Returns:
            WorkflowConfig object
        """
        # Extract fields (already validated by tool schema)
        pattern = tool_data.get("pattern", "map_reduce")
        nodes = tool_data.get("nodes", [])
        flow = tool_data.get("flow", [])
        reasoning = tool_data.get("reasoning", "")
        metadata = tool_data.get("metadata", {})

        # Add query and reasoning to metadata
        metadata["query"] = user_query
        metadata["llm_reasoning"] = reasoning

        self.logger.info(
            f"🔧 Building workflow from tool response: pattern={pattern} num_nodes={len(nodes)} num_stages={len(flow)}"
        )

        # Log node details including input_mapping for debugging
        import json

        for i, node in enumerate(nodes):
            node_preview = json.dumps(node, indent=2)[:500]
            self.logger.info(f"🔧 Node {i} structure: {node_preview}")

        # Check for error pattern
        if pattern == "error" or metadata.get("error") == "missing_capabilities":
            missing_agents = metadata.get("missing_agents", [])
            self.logger.warning(
                f"LLM detected missing capabilities: missing_agents={missing_agents} reasoning={reasoning}"
            )

            # Return error workflow
            missing_agents = metadata.get("missing_agents", ["unknown"])
            error_message = f"Cannot fulfill query - missing required agents: {', '.join(missing_agents)}. Reason: {reasoning}"

            return WorkflowConfig(
                pattern="error",
                nodes=[],
                flow=[],
                metadata=metadata,
                error_info={
                    "missing_agents": metadata.get("missing_agents", []),
                    "required_capabilities": metadata.get("required_capabilities", []),
                    "message": error_message,
                },
            )

        # Validate agent references
        referenced_agents = set()
        for node in nodes:
            if node.get("type") == "agent_call":
                agent_id = node.get("agent_id")
                if agent_id:
                    referenced_agents.add(agent_id)

        missing = referenced_agents - set(discovered_agents.keys())
        if missing:
            available = list(discovered_agents.keys())
            self.logger.error(
                f"Workflow references non-existent agents: missing={list(missing)} available={available}"
            )
            raise RuntimeError(
                f"Workflow references agents that don't exist: {', '.join(missing)}. "
                f"Available agents: {', '.join(discovered_agents.keys())}"
            ) from None

        # Create workflow config
        workflow_config = WorkflowConfig(
            pattern=pattern, nodes=nodes, flow=flow, metadata=metadata
        )

        # Validate workflow
        validation_errors = workflow_config.validate()
        if validation_errors:
            self.logger.warning(
                f"Workflow validation errors: errors={validation_errors}"
            )

        return workflow_config

    def _create_fallback_workflow(
        self, user_query: str, discovered_agents: dict[str, dict[str, Any]]
    ) -> WorkflowConfig:
        """
        Create simple fallback workflow (parallel map-reduce).

        Used when LLM generation fails or returns invalid workflow.

        Args:
            user_query: User's query
            discovered_agents: Available agents

        Returns:
            Simple parallel workflow calling all agents
        """
        self.logger.info("Creating fallback workflow")

        # Filter out orchestrators
        agent_ids = []
        for agent_id, agent_info in discovered_agents.items():
            agent_card = agent_info.get("agent_card", {})
            agent_name = agent_card.get("name", "").lower()

            if "orchestrator" not in agent_name and "orchestration" not in agent_name:
                agent_ids.append(agent_id)

        # Create nodes: one agent_call per agent + one joiner
        nodes = []

        for agent_id in agent_ids:
            nodes.append({"id": agent_id, "type": "agent_call", "agent_id": agent_id})

        nodes.append({"id": "aggregate", "type": "joiner", "strategy": "merge"})

        # Create flow: all agents in parallel, then aggregate
        flow = [
            agent_ids,  # Stage 1: all agents in parallel
            ["aggregate"],  # Stage 2: aggregate results
        ]

        return WorkflowConfig(
            pattern="map_reduce",
            nodes=nodes,
            flow=flow,
            metadata={
                "query": user_query,
                "fallback": True,
                "reason": "LLM generation failed or returned invalid workflow",
            },
        )
