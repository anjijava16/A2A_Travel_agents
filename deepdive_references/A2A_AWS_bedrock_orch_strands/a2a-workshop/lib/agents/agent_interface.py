#!/usr/bin/env python3
"""
Domain-Agnostic Agent Base Class

Provides abstract interface and common functionality for all agents
across different domains (travel, financial, e-commerce, etc.).

Key Features:
- Standard A2A protocol implementation
- Cloud Map service discovery integration
- Agent card generation (/.well-known/agent.json)
- Capability-based routing
- Domain configuration support

Based on patterns from working-workshop-code/agents/market_analysis/main.py
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
import os
from typing import Any
import uuid

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentProvider,
    AgentSkill,
    Artifact,
    DataPart,
    Message,
    Role,
    Task,
    TaskState,
    TaskStatus,
    TextPart,
)
from pydantic import BaseModel, Field

from lib.agents.schema_validator import validate_agent_capabilities
from lib.logger import OperationLogger, get_logger_for_agent


class AgentCapability(BaseModel):
    """
    Domain-agnostic capability definition.

    Describes what an agent can do without being tied to a specific domain.
    Includes optional dependency metadata for inter-agent coordination.

    Examples:
        Travel Domain (Primary Service):
            AgentCapability(
                id="find-restaurants",
                name="Find Restaurants",
                description="Search for restaurants in a location",
                optional_enhancements=["geography-agent"],  # Can be enhanced
                service_type="primary"
            )

        Travel Domain (Enhancement Service):
            AgentCapability(
                id="filter-by-proximity",
                name="Filter by Proximity",
                description="Filter locations by distance from a point",
                provides_for=["restaurant-agent", "events-agent"],  # Provides for others
                service_type="enhancement"
            )

        Financial Domain:
            AgentCapability(
                id="analyze-market",
                name="Analyze Market",
                description="Analyze market conditions for a sector",
                service_type="primary"
            )
    """

    id: str = Field(..., description="Unique capability identifier (kebab-case)")
    name: str = Field(..., description="Human-readable capability name")
    description: str = Field(
        ..., description="Clear description of what this capability does"
    )
    tags: list[str] = Field(
        default_factory=list, description="Searchable tags for capability discovery"
    )
    examples: list[str] = Field(
        default_factory=list, description="Example queries that trigger this capability"
    )
    input_schema: dict[str, Any] = Field(
        default_factory=dict, description="JSON schema for input validation"
    )
    output_schema: dict[str, Any] = Field(
        default_factory=dict, description="JSON schema for output structure"
    )
    input_modes: list[str] = Field(
        default_factory=lambda: ["text"], description="Supported input modes"
    )
    output_modes: list[str] = Field(
        default_factory=lambda: ["text"], description="Supported output modes"
    )

    # Agent Dependency Metadata (for inter-agent coordination)
    optional_enhancements: list[str] = Field(
        default_factory=list,
        description="Agent IDs that can enhance this capability (e.g., ['geography-agent'] for proximity filtering)",
    )
    provides_for: list[str] = Field(
        default_factory=list,
        description="Agent IDs that this capability provides services for (e.g., ['restaurant-agent', 'events-agent'])",
    )
    service_type: str | None = Field(
        default=None,
        description="Type of service: 'primary' (main capability) or 'enhancement' (supports other agents)",
    )


class BaseAgent(ABC):
    """
    Domain-agnostic agent base class.

    All agents (travel, financial, etc.) inherit from this class.
    Provides standard A2A protocol implementation and AWS service integration.

    Lifecycle:
        1. __init__: Load domain config, initialize capabilities
        2. initialize: Load capabilities
        3. process_task: Handle incoming A2A tasks

    Note:
        CloudMap registration is handled by ECS via CloudFormation's ServiceRegistries.
        No manual registration code is needed in the agent.

    Subclasses must implement:
        - _define_capabilities(): Return list of AgentCapability
        - _process_task_impl(): Handle task processing logic
    """

    def __init__(
        self, domain: str, agent_name: str, config: dict[str, Any] | None = None
    ):
        """
        Initialize base agent.

        Args:
            domain: Domain name (e.g., "travel", "financial")
            agent_name: Agent name (e.g., "weather-agent", "market-analysis")
            config: Optional configuration override (defaults to env vars)
        """
        self.domain = domain
        self.agent_name = agent_name
        self.config = config or {}

        # Initialize structured logger
        self.logger = get_logger_for_agent(agent_name)

        # AWS Configuration
        self.region = os.getenv("AWS_PRIMARY_REGION", "us-east-1")
        self.model_id = os.getenv(
            "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
        )
        self.agent_url = os.getenv("AGENT_URL", "http://localhost:8000")

        # Capabilities defined by subclass
        self.capabilities: list[AgentCapability] = []

        self.logger.debug(
            "🚀 Initializing agent",
        )

    @abstractmethod
    def _define_capabilities(self) -> list[AgentCapability]:
        """
        Define agent capabilities (implemented by subclass).

        Returns:
            List of AgentCapability objects describing what this agent can do

        Example:
            return [
                AgentCapability(
                    id="get-weather",
                    name="Get Weather",
                    description="Retrieve weather forecast for a location",
                    tags=["weather", "forecast"],
                    examples=["What's the weather in Seattle?"]
                )
            ]
        """
        pass

    @abstractmethod
    def _process_task_impl(self, task: Task, user_input: dict[str, Any]) -> Task:
        """
        Process task (implemented by subclass).

        This is where the agent's core logic lives.
        Subclasses implement their domain-specific processing here.

        Args:
            task: A2A Task object with history and context
            user_input: Extracted user input from task history

        Returns:
            Updated Task with status and artifacts

        Example:
            # Weather agent implementation
            location = user_input.get("location", "Seattle")
            forecast = self.get_forecast(location)
            return self._create_success_task(task, forecast)
        """
        pass

    def initialize(self):
        """
        Initialize agent resources.

        Called after __init__ to set up:
        - Capabilities definition
        - Schema validation
        - Bedrock model connection (if needed by subclass)
        - MCP tools (if applicable)

        Note:
            CloudMap registration is automatically handled by ECS via
            CloudFormation's ServiceRegistries configuration. No manual
            registration is needed.
        """
        with OperationLogger(self.logger, "initialization") as op:
            # Define capabilities (subclass implementation)
            self.capabilities = self._define_capabilities()

            self.logger.info(
                "✓ Capabilities defined",
            )

            # Validate capability schemas
            self._validate_capability_schemas()

            self.logger.info(
                "📋 Service discovery configuration",
            )

            op.add_context({"capabilities": len(self.capabilities), "ready": True})

    def _validate_capability_schemas(self):
        """
        Validate agent capability schemas using schema_validator.

        This runs at agent initialization to catch schema issues early.
        Logs validation results and warnings but doesn't fail initialization
        (to maintain backward compatibility).
        """
        if not self.capabilities:
            return

        # Convert capabilities to dict format for validator
        capability_dicts = [cap.model_dump() for cap in self.capabilities]

        # Validate all capabilities
        results = validate_agent_capabilities(
            capability_dicts,
            agent_name=self.agent_name,
            strict=False,  # Don't fail on warnings
        )

        # Log results
        errors_count = sum(1 for r in results.values() if not r.is_valid)
        warnings_count = sum(len(r.warnings) for r in results.values())

        if errors_count > 0 or warnings_count > 0:
            self.logger.warning(
                "Schema validation found issues",
            )

            # Log details for each problematic capability
            for cap_id, result in results.items():
                if not result.is_valid:
                    self.logger.error(
                        f"Schema validation failed for '{cap_id}'",
                    )

                if result.warnings:
                    self.logger.warning(
                        f"Schema warnings for '{cap_id}'",
                    )
        else:
            self.logger.info(
                "✓ Schema validation passed",
            )

    def process_task(self, task: Task) -> Task:
        """
        Process A2A task (standard entry point).

        This method:
        1. Extracts user input from task history
        2. Calls subclass implementation (_process_task_impl)
        3. Handles errors gracefully

        Args:
            task: A2A Task object

        Returns:
            Updated Task with completed or failed status
        """
        task_id = getattr(task, "id", "unknown")

        self.logger.info("📝 Processing task")

        try:
            with OperationLogger(self.logger, "task_processing", log_start=False) as op:
                # Extract user input from task history
                user_input = self._extract_user_input(task)

                # Call subclass implementation
                result_task = self._process_task_impl(task, user_input)

                op.add_context({"task_id": task_id, "status": "completed"})

                return result_task

        except Exception as e:
            self.logger.error(
                "❌ Task processing failed",
                exc_info=True,
            )

            return self._create_error_task(task, str(e))

    def get_agent_card(self) -> dict[str, Any]:
        """
        Generate A2A agent card for service discovery.

        Returns agent metadata in standardized format:
        - Name, description, version
        - Provider information
        - Capabilities (skills) enriched with input_schema/output_schema
        - Supported input/output modes

        Returns:
            Dict containing agent card data (enriched beyond A2A spec)
        """
        # Convert capabilities to AgentSkill objects
        # Note: We enrich skills with input_schema and output_schema even though
        # A2A protocol doesn't formally define these fields. This allows the
        # orchestrator's workflow generator to understand data dependencies.
        skills = []
        for cap in self.capabilities:
            skill = AgentSkill(
                id=cap.id,
                name=cap.name,
                description=cap.description,
                tags=cap.tags,
                examples=cap.examples,
                inputModes=cap.input_modes,
                outputModes=cap.output_modes,
            )
            skills.append(skill)

        # Generate agent card
        card = AgentCard(
            name=self.agent_name,
            description=self.config.get(
                "description", f"{self.agent_name} agent for {self.domain} domain"
            ),
            url=f"{self.agent_url}/message/send",
            provider=AgentProvider(
                organization=self.config.get("organization", "AWS Workshop"),
                url=self.config.get("provider_url", "https://aws.amazon.com/bedrock/"),
            ),
            version=self.config.get("version", "1.0.0"),
            documentationUrl=self.config.get(
                "docs_url", "https://docs.aws.amazon.com/bedrock/"
            ),
            capabilities=AgentCapabilities(
                streaming=False,
                pushNotifications=False,
                stateTransitionHistory=False,
            ),
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
            skills=skills,
            supportsAuthenticatedExtendedCard=False,
        )

        # Enrich card with input_schema and output_schema in skills
        # (A2A protocol doesn't formally support these, but they're essential for
        # workflow generators to understand data dependencies between agents)
        card_dict = card.model_dump(mode="json")
        if card_dict.get("skills"):
            for i, cap in enumerate(self.capabilities):
                if i < len(card_dict["skills"]):
                    # Add input_schema if defined
                    if cap.input_schema:
                        card_dict["skills"][i]["input_schema"] = cap.input_schema
                    # Add output_schema if defined
                    if cap.output_schema:
                        card_dict["skills"][i]["output_schema"] = cap.output_schema

        # Return enriched dict directly (not AgentCard object)
        # Pydantic validation would strip our custom input_schema/output_schema fields
        return card_dict

    # -------------------------------------------------------------------------
    # Helper Methods (Private)
    # -------------------------------------------------------------------------

    def _extract_user_input(self, task: Task) -> dict[str, Any]:
        """
        Extract user input from A2A task history.

        Parses task.history to find the latest user message and extract:
        - Text content (user query)
        - Data parts (structured parameters)

        Args:
            task: A2A Task object

        Returns:
            Dictionary with extracted user input
        """
        user_input = {}

        if not task or not task.history:
            return {"error": "No task or history found"}

        # Find latest user message
        user_messages = [msg for msg in task.history if msg.role.value == "user"]
        if not user_messages:
            return {"error": "No user messages found"}

        latest_message = user_messages[-1]

        # Extract text and data parts
        for part in latest_message.parts:
            if part.root.kind == "text":
                user_input["query"] = part.root.text
            elif part.root.kind == "data" and part.root.data:
                user_input.update(part.root.data)

        return user_input

    def _create_success_task(
        self, task: Task, result_text: str, result_data: dict[str, Any] | None = None
    ) -> Task:
        """
        Create successful task result.

        Args:
            task: Original task
            result_text: Text response to user
            result_data: Optional structured data

        Returns:
            Updated task with completed status
        """
        # 📤 INLINE LOGGING - Log what we're sending (extra={} doesn't show in CloudWatch)
        self.logger.info(
            f"📤 AGENT OUTPUT - Creating response: has_data={result_data is not None} data_keys={list(result_data.keys()) if result_data else []}"
        )
        if result_data:
            # Log first 200 chars of data
            import json

            data_preview = json.dumps(result_data, default=str)[:200]
            self.logger.info(f"📤 AGENT OUTPUT - Data preview: {data_preview}")

        parts = [TextPart(kind="text", text=result_text, metadata={})]
        self.logger.debug(
            f"📤 AGENT OUTPUT - Created TextPart: type={type(parts[0]).__name__} kind={parts[0].kind}"
        )

        if result_data:
            data_part = DataPart(kind="data", data=result_data, metadata={})
            parts.append(data_part)
            self.logger.debug(
                f"📤 AGENT OUTPUT - Created DataPart: type={type(data_part).__name__} kind={data_part.kind} has_data={hasattr(data_part, 'data')}"
            )

        # 🔍 LOGGING - Inspect parts before artifact creation (DEBUG level)
        for i, part in enumerate(parts):
            self.logger.debug(
                f"🔍 BEFORE ARTIFACT - Part {i}: type={type(part).__name__} has_kind={hasattr(part, 'kind')} has_data={hasattr(part, 'data')} has_text={hasattr(part, 'text')}"
            )
            if hasattr(part, "kind"):
                self.logger.debug(f"🔍 BEFORE ARTIFACT - Part {i}.kind={part.kind}")

        artifact = Artifact(
            artifactId=str(uuid.uuid4()),
            parts=parts,
            name=f"{self.agent_name} Result",
            description=f"Result from {self.agent_name}",
        )

        self.logger.debug(
            f"📤 AGENT OUTPUT - Built artifact: parts_count={len(parts)} part_types={[type(p).__name__ for p in parts]}"
        )

        # 🔍 LOGGING - Inspect artifact.parts after artifact creation (DEBUG level)
        for i, part in enumerate(artifact.parts):
            self.logger.debug(
                f"🔍 AFTER ARTIFACT - Part {i}: type={type(part).__name__} has_kind={hasattr(part, 'kind')} has_root={hasattr(part, 'root')}"
            )

        message = Message(
            role=Role.agent,
            parts=[
                TextPart(
                    kind="text",
                    text=f"{self.agent_name} completed successfully.",
                    metadata={},
                )
            ],
            messageId=str(uuid.uuid4()),
            kind="message",
            taskId=task.id,
            contextId=getattr(task, "contextId", None),
        )

        task.status = TaskStatus(
            state=TaskState.completed,
            message=message,
            timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        task.artifacts = [artifact]

        self.logger.info(
            f"📤 AGENT OUTPUT - Task complete: task_id={task.id} artifacts_count={len(task.artifacts)} status={task.status.state}"
        )

        return task

    def _create_error_task(self, task: Task, error_message: str) -> Task:
        """
        Create failed task result.

        Args:
            task: Original task
            error_message: Error description

        Returns:
            Updated task with failed status
        """
        error_parts = [
            TextPart(kind="text", text=f"Error: {error_message}", metadata={})
        ]

        message = Message(
            role=Role.agent,
            parts=error_parts,
            messageId=str(uuid.uuid4()),
            kind="message",
            taskId=getattr(task, "id", str(uuid.uuid4())),
            contextId=getattr(task, "contextId", None),
        )

        artifact = Artifact(
            artifactId=str(uuid.uuid4()),
            parts=error_parts,
            name="Error",
            description=f"Error from {self.agent_name}",
        )

        task.status = TaskStatus(
            state=TaskState.failed,
            message=message,
            timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        task.artifacts = [artifact]

        return task
