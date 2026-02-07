#!/usr/bin/env python3
"""
Workflow Models - Data Structures for ADK Workflows

Provides Pydantic models and dataclasses for representing workflow configurations
and executable workflow nodes.

Key Components:
    - ADKNode: Represents an executable workflow node (router, joiner, condition, agent_call)
    - WorkflowConfig: Complete workflow configuration with nodes and execution flow
    - Workflow execution primitives configuration schemas

Design:
    - Immutable workflow definitions
    - Type-safe configurations
    - JSON serialization support
    - Validation at construction time
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
import json
from typing import Any


class NodeType(str, Enum):
    """Types of ADK workflow nodes"""

    ROUTER = "router"
    JOINER = "joiner"
    CONDITION = "condition"
    AGENT_CALL = "agent_call"


class JoinerStrategy(str, Enum):
    """Strategies for joining multiple results"""

    MERGE = "merge"  # Combine dicts/objects
    CONCATENATE = "concatenate"  # Create list of results
    VOTE = "vote"  # Most common result
    SYNTHESIZE = "synthesize"  # LLM-based synthesis


@dataclass
class ADKNode:
    """
    Represents an executable ADK workflow node.

    A node encapsulates:
        - Configuration (what it should do)
        - Executor function (how to execute it)
        - Type information (router, joiner, condition, agent_call)

    Attributes:
        id: Unique node identifier within workflow
        type: Node type (router, joiner, condition, agent_call)
        config: Node-specific configuration parameters
        execute: Optional callable that executes this node

    Example:
        node = ADKNode(
            id="weather_call",
            type=NodeType.AGENT_CALL,
            config={"agent_id": "weather-agent"},
            execute=lambda ctx, data: call_weather_agent(ctx, data)
        )
    """

    id: str
    type: NodeType
    config: dict[str, Any]
    execute: Callable[[dict[str, Any], Any], Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert node to dictionary (for logging, serialization).

        Note: Execute function is not serialized.

        Returns:
            Dictionary representation of node
        """
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "config": self.config,
            "has_executor": self.execute is not None,
        }


@dataclass
class RouterConfig:
    """
    Configuration for Router nodes.

    Attributes:
        rules: List of routing rules with conditions and targets
        parallel: Execute routes concurrently (True) or sequentially (False)
        timeout: Optional timeout per route in seconds
    """

    rules: list[dict[str, Any]]
    parallel: bool = False
    timeout: int | None = None


@dataclass
class JoinerConfig:
    """
    Configuration for Joiner nodes.

    Attributes:
        strategy: How to join results (merge, concatenate, vote, synthesize)
        wait_for: List of source node IDs to wait for (None = all parents)
        timeout: Optional timeout for joining in seconds
    """

    strategy: JoinerStrategy = JoinerStrategy.MERGE
    wait_for: list[str] | None = None
    timeout: int | None = None


@dataclass
class ConditionConfig:
    """
    Configuration for Condition nodes.

    Attributes:
        expression: Python expression to evaluate (safe eval)
        true_branch: Node ID to execute if condition is True
        false_branch: Optional node ID if condition is False
    """

    expression: str
    true_branch: str
    false_branch: str | None = None


@dataclass
class AgentCallConfig:
    """
    Configuration for AgentCall nodes.

    Attributes:
        agent_id: ID of agent to call
        tool_name: Optional specific tool/capability to invoke
        timeout: Optional timeout for agent call in seconds
    """

    agent_id: str
    tool_name: str | None = None
    timeout: int | None = 30


@dataclass
class WorkflowConfig:
    """
    Complete workflow configuration.

    Represents the LLM-generated or manually-defined workflow that will be executed.

    Attributes:
        pattern: Workflow pattern name (map_reduce, sequential, conditional, error, etc.)
        nodes: List of node configurations (before building executors)
        flow: Execution flow as list of stages (each stage is list of node IDs)
        metadata: Optional metadata (query, timestamp, reasoning, etc.)
        error_info: Optional error information if pattern="error" (missing capabilities)

    Example:
        config = WorkflowConfig(
            pattern="map_reduce",
            nodes=[
                {"id": "weather_call", "type": "agent_call", "agent_id": "weather-agent"},
                {"id": "events_call", "type": "agent_call", "agent_id": "events-agent"},
                {"id": "aggregate", "type": "joiner", "strategy": "merge"}
            ],
            flow=[
                ["weather_call", "events_call"],  # Stage 1: Parallel
                ["aggregate"]                      # Stage 2: Aggregate
            ],
            metadata={"query": "What should I do in Seattle?"}
        )

    Error Example:
        config = WorkflowConfig(
            pattern="error",
            nodes=[],
            flow=[],
            metadata={"error": "missing_capabilities"},
            error_info={
                "missing_agents": ["hotel-agent"],
                "required_capabilities": ["hotel search"],
                "message": "Cannot fulfill query - missing hotel-agent"
            }
        )
    """

    pattern: str
    nodes: list[dict[str, Any]]
    flow: list[list[str]]  # List of stages, each stage is list of node IDs
    metadata: dict[str, Any] = field(default_factory=dict)
    error_info: dict[str, Any] | None = None

    def is_error(self) -> bool:
        """
        Check if this workflow represents an error condition.

        Returns:
            True if pattern is "error" or error_info is present
        """
        return self.pattern == "error" or self.error_info is not None

    def get_error_message(self) -> str | None:
        """
        Get human-readable error message if this is an error workflow.

        Returns:
            Error message string or None if not an error workflow
        """
        if not self.is_error():
            return None

        if self.error_info and "message" in self.error_info:
            return self.error_info["message"]

        # Fallback: construct message from metadata
        reasoning = self.metadata.get("llm_reasoning", "")
        missing_agents = self.metadata.get("missing_agents", [])

        if missing_agents:
            return f"Cannot fulfill query - missing required agents: {', '.join(missing_agents)}. {reasoning}"

        return "Cannot fulfill query due to missing capabilities."

    def to_dict(self) -> dict[str, Any]:
        """
        Convert workflow config to dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        result = {
            "pattern": self.pattern,
            "nodes": self.nodes,
            "flow": self.flow,
            "metadata": self.metadata,
        }
        if self.error_info:
            result["error_info"] = self.error_info
        return result

    def to_json(self) -> str:
        """
        Convert workflow config to JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowConfig":
        """
        Create WorkflowConfig from dictionary.

        Args:
            data: Dictionary with pattern, nodes, flow, metadata

        Returns:
            WorkflowConfig instance
        """
        return cls(
            pattern=data["pattern"],
            nodes=data["nodes"],
            flow=data["flow"],
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "WorkflowConfig":
        """
        Create WorkflowConfig from JSON string.

        Args:
            json_str: JSON string representation

        Returns:
            WorkflowConfig instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def validate(self) -> list[str]:
        """
        Validate workflow configuration.

        Checks:
            - All node IDs are unique
            - Flow references only defined nodes
            - Required fields present in node configs

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check node IDs are unique
        node_ids = [node["id"] for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("Node IDs must be unique")

        # Check all flow references exist
        node_id_set = set(node_ids)
        for stage_idx, stage in enumerate(self.flow):
            for node_id in stage:
                if node_id not in node_id_set:
                    errors.append(
                        f"Flow stage {stage_idx} references unknown node: {node_id}"
                    )

        # Check required fields in nodes
        for node in self.nodes:
            if "id" not in node:
                errors.append("Node missing required field: id")
            if "type" not in node:
                errors.append(
                    f"Node {node.get('id', '?')} missing required field: type"
                )

            # Type-specific validation
            node_type = node.get("type")
            if node_type == "agent_call" and "agent_id" not in node:
                errors.append(f"Agent call node {node['id']} missing agent_id")
            elif node_type == "condition":
                if "expression" not in node:
                    errors.append(f"Condition node {node['id']} missing expression")
                if "true_branch" not in node:
                    errors.append(f"Condition node {node['id']} missing true_branch")

        return errors


@dataclass
class ExecutableWorkflow:
    """
    An executable workflow with built ADK nodes.

    This is the result of building a WorkflowConfig - all nodes have
    their executor functions attached and are ready to run.

    Attributes:
        nodes: Dictionary mapping node_id -> ADKNode (with executors)
        flow: Execution flow (same as WorkflowConfig)
        pattern: Workflow pattern name
        metadata: Workflow metadata
    """

    nodes: dict[str, ADKNode]
    flow: list[list[str]]
    pattern: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_stage_nodes(self, stage_idx: int) -> list[ADKNode]:
        """
        Get all nodes for a given stage.

        Args:
            stage_idx: Stage index (0-based)

        Returns:
            List of ADKNode objects for this stage

        Raises:
            IndexError: If stage_idx is out of range
        """
        if stage_idx >= len(self.flow):
            raise IndexError(
                f"Stage {stage_idx} out of range (total stages: {len(self.flow)})"
            )

        stage_node_ids = self.flow[stage_idx]
        return [self.nodes[node_id] for node_id in stage_node_ids]

    def total_stages(self) -> int:
        """
        Get total number of stages in workflow.

        Returns:
            Number of execution stages
        """
        return len(self.flow)


# Type aliases for clarity
WorkflowContext = dict[str, Any]  # Context passed between workflow stages
NodeData = Any  # Data passed to/from nodes (can be any JSON-serializable type)
