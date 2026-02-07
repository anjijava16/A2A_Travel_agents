#!/usr/bin/env python3
"""
Dynamic ADK Orchestrator - LLM-Powered Workflow Orchestration

Coordinates multiple specialist agents using dynamically-generated workflows.

Key Learning Objective:
    This orchestrator demonstrates DYNAMIC WORKFLOW GENERATION.

    Capabilities:
        - LLM generates workflow configurations at runtime (Claude Sonnet 4)
        - Executes sequential, parallel, conditional, and mixed workflows
        - Works with ANY specialist agents (domain-agnostic)
        - Optimizes execution patterns based on query analysis

Architecture:
    1. Receive user query
    2. Discover ALL available agents via CloudMap
    3. Generate optimal workflow config using LLM (WorkflowGenerator)
    4. Build executable workflow with ADK primitives
    5. Execute workflow stage-by-stage (WorkflowExecutor)
    6. Return synthesized results

Workflow Patterns Supported:
    - Map-Reduce: Parallel agent calls → Aggregate
    - Sequential: Agent chains (A → B → C)
    - Conditional: Branch based on runtime data
    - Scatter-Gather: Broadcast → Collect all
    - Mixed: Combinations of above

Example Queries:
    Parallel: "What should I do in Seattle this weekend?"
    Sequential: "Find hotels under $200, then restaurants nearby"
    Conditional: "Activities in Seattle? If raining, suggest indoor"
"""

from datetime import UTC, datetime
from typing import Any

from a2a.types import Task

from lib.agents import AgentCapability, BaseAgent
from lib.agents.config_loader import get_agent_config, load_domain_config
from lib.logger import OperationLogger, get_logger, log_educational
from lib.orchestration.generic_synthesizer import GenericSynthesizer
from lib.orchestration.workflow_executor import WorkflowExecutor
from lib.orchestration.workflow_generator import WorkflowGenerator


class DynamicADKOrchestrator(BaseAgent):
    """
    Dynamic workflow orchestrator using ADK primitives.

    Capabilities:
        - coordinate-agents: Generate and execute dynamic workflows across ANY domain
        - synthesize-recommendations: Intelligent synthesis using workflows

    Workflow Generation:
        - Uses Claude Sonnet 4 to analyze queries
        - Generates optimal workflow patterns (sequential, parallel, conditional, etc.)
        - Executes workflows using ADK primitives (Router, Joiner, Condition, AgentCall)

    Configuration:
        Environment Variables:
            - BEDROCK_MODEL_ID: Claude model ID (default: claude-sonnet-4)
            - AWS_PRIMARY_REGION: AWS region (default: us-east-1)
            - ORCHESTRATOR_TIMEOUT: Workflow timeout in seconds (default: 90)
    """

    def __init__(
        self,
        domain: str = "universal",
        agent_name: str = "adk-orchestrator",
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize DynamicADKOrchestrator.

        Args:
            domain: Domain name (default: "universal" - works with any domain)
            agent_name: Agent name (default: "adk-orchestrator")
            config: Optional configuration override
        """
        super().__init__(domain, agent_name, config)

        # Load domain configuration
        try:
            domain_config = load_domain_config(domain)
            agent_config = get_agent_config(domain_config, "orchestrator")
            self.agent_config = agent_config.config
        except Exception:
            self.logger.warning(
                "Could not load domain config",
            )
            self.agent_config = {}

        # Configuration
        self.workflow_timeout = self.agent_config.get("timeout_seconds", 90)

        # Initialize core components
        try:
            with OperationLogger(self.logger, "initialization", log_start=False) as op:
                # Workflow generator (uses Claude Sonnet 4)
                self.workflow_generator = WorkflowGenerator()
                self.logger.info(
                    "✓ WorkflowGenerator initialized",
                )

                # Workflow executor
                self.workflow_executor = WorkflowExecutor(
                    default_timeout=self.workflow_timeout
                )
                self.logger.info(
                    "✓ WorkflowExecutor initialized",
                )

                # Generic synthesizer will be created per-request to prevent state accumulation
                # (moved from __init__ to _process_task_impl)

                op.add_context(
                    {
                        "components": [
                            "WorkflowGenerator",
                            "WorkflowExecutor",
                        ],
                        "workflow_timeout": self.workflow_timeout,
                        "synthesizer_mode": "per-request (prevents state accumulation)",
                    }
                )

        except Exception:
            self.logger.error(
                "❌ Failed to initialize components",
                exc_info=True,
            )
            raise

        log_educational(
            self.logger,
            "Dynamic ADK orchestrator ready",
            what="LLM-powered multi-agent orchestration system",
            why="Dynamically generates and executes workflows based on available agents",
            how="Uses Claude Sonnet 4 to analyze queries and generate optimal coordination patterns",
        )

    def _define_capabilities(self) -> list[AgentCapability]:
        """
        Define orchestrator capabilities.

        Returns:
            List of AgentCapability objects
        """
        return [
            AgentCapability(
                id="coordinate-agents",
                name="Coordinate Agents with Dynamic Workflows",
                description="Generate and execute dynamic workflows (sequential, parallel, conditional) across multiple specialist agents. Uses LLM-powered workflow generation to optimize coordination patterns.",
                tags=[
                    "orchestration",
                    "coordination",
                    "multi-agent",
                    "domain-agnostic",
                    "workflows",
                    "dynamic",
                ],
                examples=[
                    "Coordinate agents to answer my question",
                    "What should I do in Seattle this weekend?",
                    "Find hotels under $200, then restaurants nearby",
                    "Activities in Seattle? If raining, suggest indoor",
                ],
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "User's question or request (any domain)",
                        },
                        "context": {
                            "type": "object",
                            "description": "Optional context parameters (location, date, etc.)",
                        },
                    },
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "recommendations": {
                            "type": "object",
                            "description": "Aggregated results from workflow execution",
                        },
                        "workflow": {
                            "type": "object",
                            "properties": {
                                "pattern": {"type": "string"},
                                "agents_used": {"type": "array"},
                            },
                        },
                    },
                },
            ),
            AgentCapability(
                id="synthesize-recommendations",
                name="Synthesize Recommendations",
                description="Combine and synthesize recommendations from multiple agents using dynamic workflows",
                tags=["synthesis", "ranking", "recommendation", "ai", "universal"],
                examples=["Synthesize recommendations from available agents"],
            ),
        ]

    def _process_task_impl(self, task: Task, user_input: dict[str, Any]) -> Task:
        """
        Process orchestration task using dynamic workflows.

        Flow:
            1. Discover agents from CloudMap
            2. Generate workflow config using LLM (WorkflowGenerator)
            3. Build executable workflow with ADK primitives
            4. Execute workflow stage-by-stage (WorkflowExecutor)
            5. Return results

        Args:
            task: A2A Task object
            user_input: Extracted user input with location and query

        Returns:
            Updated task with orchestrated results
        """
        # Extract parameters
        location = user_input.get("location", "Seattle")
        user_query = user_input.get("query", "What should I do?")

        self.logger.info(
            "📝 Processing orchestration request",
        )

        try:
            # 🎯 MILESTONE: Orchestration workflow begins
            self.logger.info("\n" + "=" * 70)
            self.logger.info(
                "🎯 ORCHESTRATION WORKFLOW - Starting multi-agent coordination"
            )
            self.logger.info("=" * 70 + "\n")

            # Create fresh GenericSynthesizer for this request (prevents state accumulation)
            generic_synthesizer = GenericSynthesizer(max_tokens=2000)
            self.logger.info(
                "✓ Created fresh GenericSynthesizer for this request (invocation #1)"
            )

            # Step 1: Discover all available agents
            log_educational(
                self.logger,
                "🔍 Step 1: Discovering agents via CloudMap",
                what="Querying AWS CloudMap service registry for available agents",
                why="Need to know which agents are available before generating workflow",
                how="CloudMap DiscoverInstances API with HTTP namespace",
            )

            with OperationLogger(self.logger, "agent_discovery") as op:
                discovered_agents = self._discover_all_agents()

                if not discovered_agents:
                    self.logger.error(
                        "❌ No agents discovered",
                    )
                    return self._create_error_task(task, "No agents available")

                op.add_context(
                    {
                        "discovered_count": len(discovered_agents),
                        "agent_ids": list(discovered_agents.keys()),
                    }
                )

            # Step 2: Generate workflow config using LLM
            log_educational(
                self.logger,
                "⚙️ Step 2: Generating workflow with Claude Sonnet 4",
                what="LLM analyzing query and agent capabilities to generate optimal workflow",
                why="Dynamic workflow generation adapts to available agents and query complexity",
                how="Sending agent cards and query to Claude Sonnet 4, parsing structured JSON response",
            )

            with OperationLogger(self.logger, "workflow_generation") as op:
                workflow_config = self.workflow_generator.generate_workflow(
                    user_query=user_query, discovered_agents=discovered_agents
                )

                # With graceful degradation, we should always get a valid workflow
                # (no more error workflows - system adapts to available agents)
                op.add_context(
                    {
                        "pattern": workflow_config.pattern,
                        "nodes": len(workflow_config.nodes),
                        "stages": len(workflow_config.flow),
                        "graceful_degradation": "enabled",
                    }
                )

                # 🔍 DIAGNOSTIC: Log complete generated workflow configuration (DEBUG level)
                self.logger.debug(
                    "⚙️ Generated workflow configuration",
                )

            # Step 3: Build executable workflow
            log_educational(
                self.logger,
                "⚙️ Step 3: Building executable workflow",
                what="Converting LLM-generated config into ADK primitives (AgentCall, Router, Joiner)",
                why="ADK primitives enable composable, testable workflow execution",
                how="Building workflow nodes and connecting them based on LLM's flow specification",
            )

            context = {
                "discovered_agents": discovered_agents,
                "workflow_nodes": {},  # Will be populated during build
                "query": user_query,
                "synthesizer": generic_synthesizer,
            }

            with OperationLogger(self.logger, "workflow_build") as op:
                executable_workflow = self.workflow_executor.build_executable_workflow(
                    workflow_config, context
                )

                # Update context with built nodes
                context["workflow_nodes"] = executable_workflow.nodes

                op.add_context(
                    {
                        "executable_nodes": len(executable_workflow.nodes),
                        "pattern": workflow_config.pattern,
                    }
                )

            # Step 4: Execute workflow
            log_educational(
                self.logger,
                "⚙️ Step 4: Executing workflow",
                what="Running workflow stage-by-stage with agent calls",
                why="Stage-based execution enables parallel and sequential patterns",
                how="WorkflowExecutor coordinates agent calls based on workflow configuration",
            )

            input_data = {
                "query": user_query,
                "location": location,
            }

            with OperationLogger(self.logger, "workflow_execution") as op:
                result = self.workflow_executor.execute_workflow(
                    workflow=executable_workflow, input_data=input_data, context=context
                )

                # Count agents used
                agents_used_count = 0
                if isinstance(result, dict):
                    agents_used_count = sum(
                        1 for key in result if key in discovered_agents
                    )

                op.add_context(
                    {
                        "stages_completed": len(workflow_config.flow),
                        "agents_used": agents_used_count,
                    }
                )

            # Step 5: Synthesize response
            # This is the PRIMARY synthesis point for all workflows
            # Workflows use Joiners for aggregation (merge/concatenate), then synthesis happens here
            self.logger.info(
                "📊 Step 5: Synthesizing final response",
            )
            with OperationLogger(self.logger, "synthesis") as op:
                if isinstance(result, dict):
                    # Result is dict - synthesize to create natural language response
                    # Expected flow: agents → Joiner (aggregate) → orchestrator (synthesize)
                    # After our fix, Joiner returns its aggregated output, not raw agent data

                    # 🔍 DIAGNOSTIC: Log synthesis input size
                    import json

                    result_keys = list(result.keys())
                    result_sizes = {k: len(json.dumps(v)) for k, v in result.items()}
                    self.logger.info(
                        f"🔍 SYNTHESIS INPUT - About to synthesize: "
                        f"agent_count={len(result)} "
                        f"agent_ids={result_keys} "
                        f"sizes={result_sizes}"
                    )

                    synthesized_text = generic_synthesizer.synthesize(
                        user_query=user_query, agent_responses=result, agent_metadata={}
                    )
                    op.add_context({"num_responses": len(result)})
                elif isinstance(result, str):
                    # Result is already string - rare case, typically from specialized workflows
                    synthesized_text = result
                    op.add_context({"pre_synthesized": True})
                else:
                    # Fallback: convert any other type to string
                    synthesized_text = str(result)
                    op.add_context({"converted_to_string": True})

            # Extract agent IDs from workflow nodes
            # The workflow generator MUST include agent_id in nodes with type="agent_call"
            agents_used = []
            for node in workflow_config.nodes:
                if isinstance(node, dict) and node.get("type") == "agent_call":
                    agent_id = node.get("agent_id")
                    if agent_id and agent_id not in agents_used:
                        agents_used.append(agent_id)

            response_data = {
                "location": location,
                "recommendations": (
                    result if isinstance(result, dict) else {"result": result}
                ),
                "workflow": {
                    "pattern": workflow_config.pattern,
                    "agents_used": agents_used,
                    "num_stages": len(workflow_config.flow),
                },
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # 🔍 DIAGNOSTIC: Log final response structure (DEBUG level)
            self.logger.debug(
                "🔍 DIAGNOSTIC - Final response data",
            )

            self.logger.info(
                "✓ Orchestration complete",
            )

            return self._create_success_task(task, synthesized_text, response_data)

        except Exception as e:
            self.logger.error(
                "❌ Orchestration failed",
                exc_info=True,
            )
            return self._create_error_task(task, f"Orchestration failed: {e!s}")

    def _discover_all_agents(self) -> dict[str, dict[str, Any]]:
        """
        Discover ALL available agents via CloudMap and fetch their agent cards.

        Returns:
            Dictionary mapping agent_id -> {base_url, agent_card, service_name}
        """
        try:
            from lib.agents.discover_agent import (
                discover_agent,
                list_available_agents,
            )

            # Get list of all registered agents from CloudMap
            service_names = list_available_agents()

            if not service_names:
                self.logger.warning(
                    "No services found in CloudMap",
                )
                return {}

            self.logger.debug(
                "CloudMap services found",
            )

            # Discover each agent and fetch its card
            discovered = {}
            for service_name in service_names:
                # Skip orchestrator (don't discover self)
                if service_name == "orchestrator":
                    self.logger.debug(
                        "Skipping self-discovery",
                    )
                    continue

                try:
                    agent_info = discover_agent(service_name)
                    agent_card = agent_info["agent_card"]
                    agent_id = agent_card.get("id", service_name)

                    discovered[agent_id] = {
                        "base_url": agent_info["base_url"],
                        "agent_card": agent_card,
                        "service_name": service_name,
                    }

                    self.logger.debug(
                        f"✓ Agent discovered: {agent_id}",
                    )

                except Exception:
                    self.logger.warning(
                        f"✗ Failed to discover agent: {service_name}",
                    )

            return discovered

        except Exception:
            self.logger.error("CloudMap discovery failed", exc_info=True)
            return {}


# ============================================================================
# Standard Entry Points for Agent Launcher
# ============================================================================


def get_agent() -> DynamicADKOrchestrator:
    """
    Create and return DynamicADKOrchestrator instance.

    Called by agent_launcher.py to initialize the agent.

    Returns:
        DynamicADKOrchestrator instance
    """
    agent = DynamicADKOrchestrator()
    agent.initialize()
    return agent


def get_http_app(agent: DynamicADKOrchestrator):
    """
    Create and return FastAPI app for DynamicADKOrchestrator.

    Called by agent_launcher.py to initialize HTTP server.

    Args:
        agent: DynamicADKOrchestrator instance

    Returns:
        FastAPI application instance
    """
    from datetime import datetime
    import json

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Dynamic ADK Orchestrator", version="2.0.0")

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {
            "status": "ok",
            "agent": "adk-orchestrator",
            "version": "2.0.0",
            "features": ["dynamic-workflows", "sequential", "conditional", "parallel"],
            "timestamp": datetime.now(UTC).isoformat(),
        }

    @app.get("/.well-known/agent.json")
    async def agent_card():
        """Agent card endpoint (A2A protocol)"""
        card = agent.get_agent_card()
        return JSONResponse(card)  # card is already a dict with enriched schemas

    @app.get("/agents/available")
    async def list_available_agents_endpoint():
        """
        Return list of available specialist agents.

        Used by MCP Gateway to dynamically build tool descriptions.
        Discovers agents via CloudMap and returns their capabilities.
        """
        try:
            # Discover all agents via CloudMap
            discovered = agent._discover_all_agents()

            # Filter out orchestrators (don't expose self)
            agents = []
            for agent_id, info in discovered.items():
                agent_card = info["agent_card"]
                agent_name = agent_card.get("name", "").lower()

                # Skip orchestrators (prevent recursive loops)
                if "orchestrator" in agent_name or "orchestration" in agent_name:
                    continue

                # Extract agent info from card
                capabilities = []
                skills = agent_card.get("skills", [])

                for skill in skills:
                    if isinstance(skill, dict):
                        capabilities.append(
                            {
                                "id": skill.get("id", ""),
                                "name": skill.get("name", ""),
                                "description": skill.get("description", ""),
                                "tags": skill.get("tags", []),
                            }
                        )
                    else:
                        capabilities.append(
                            {
                                "id": skill.id,
                                "name": skill.name,
                                "description": skill.description,
                                "tags": skill.tags if hasattr(skill, "tags") else [],
                            }
                        )

                agents.append(
                    {
                        "id": agent_id,
                        "name": agent_card.get("name", agent_id),
                        "description": agent_card.get("description", ""),
                        "capabilities": capabilities,
                    }
                )

            return {
                "agents": agents,
                "count": len(agents),
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            import traceback

            traceback.print_exc()
            return {"error": str(e), "agents": [], "count": 0}

    @app.post("/message/send")
    async def handle_task(request: Request):
        """
        A2A message handler endpoint.

        Processes incoming tasks and returns results.
        """
        try:
            body = await request.body()
            body = body.decode("utf-8") if isinstance(body, bytes) else body
            body_json = json.loads(body)

            # A2A envelope unwrapping
            if (
                "method" in body_json
                and "params" in body_json
                and "message" in body_json["params"]
            ):
                task_dict = body_json["params"]["message"]
            else:
                task_dict = body_json

            # Process task
            from a2a.types import Task

            task = Task.model_validate(task_dict)
            result_task = agent.process_task(task)

            return result_task.model_dump(mode="json")

        except Exception as e:
            import traceback

            traceback.print_exc()

            # Create error task
            import uuid

            from a2a.types import Message, Task, TaskState, TaskStatus, TextPart

            error_message = Message(
                role="agent",
                parts=[TextPart(kind="text", text=f"Error: {e!s}", metadata={})],
                message_id=str(uuid.uuid4()),
                kind="message",
                task_id=str(uuid.uuid4()),
            )

            error_task = Task(
                id=str(uuid.uuid4()),
                status=TaskStatus(
                    state=TaskState.failed,
                    message=error_message,
                    timestamp=datetime.now(UTC).isoformat() + "Z",
                ),
                kind="task",
            )

            return error_task.model_dump(mode="json")

    return app


if __name__ == "__main__":
    # For local testing
    logger = get_logger(context={"component": "main"})
    logger.info("🚀 Starting DynamicADKOrchestrator...")

    agent = get_agent()

    logger.info(
        "✓ Agent initialized",
    )

    for cap in agent.capabilities:
        logger.info(f"  Capability: {cap.id}")
