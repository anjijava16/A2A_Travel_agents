#!/usr/bin/env python3
"""
ADK Primitives - Core Workflow Execution Primitives

Provides the fundamental building blocks for ADK workflows:
    - Router: Distribute work to multiple targets (parallel or sequential)
    - Joiner: Aggregate results from multiple sources
    - Condition: Conditional branching based on runtime data
    - AgentCall: Invoke A2A agents via HTTP

Design Principles:
    - Primitives return executor functions (Callable)
    - Executors take (context, input_data) and return results
    - Thread-based parallelism using ThreadPoolExecutor
    - Safe condition evaluation with restricted builtins
    - Comprehensive error handling and timeouts

Usage:
    # Create a router executor
    executor = ADKPrimitives.router(
        rules=[{"target": "weather-agent"}, {"target": "events-agent"}],
        parallel=True
    )

    # Execute with context and data
    results = executor(context, input_data)
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import json
from typing import Any
import uuid

from a2a.types import DataPart, Message, Role, Task, TaskState, TaskStatus, TextPart
import httpx

from lib.logger import get_logger

from .workflow_models import JoinerStrategy, NodeData, WorkflowContext


class ADKPrimitives:
    """
    Static methods for creating ADK primitive executors.

    All methods return Callable[[WorkflowContext, NodeData], Any] that can be
    executed as part of a workflow.
    """

    @staticmethod
    def router(
        rules: list[dict[str, Any]],
        parallel: bool = False,
        timeout: int | None = None,
    ) -> Callable[[WorkflowContext, NodeData], dict[str, Any]]:
        """
        Create a Router primitive executor.

        Routes work to multiple targets based on rules. Can execute sequentially
        or in parallel.

        Args:
            rules: List of routing rules, each with 'target' (node_id or agent_id)
                   and optional 'condition' for conditional routing
            parallel: If True, execute all routes concurrently
            timeout: Optional timeout per route in seconds (default: 180)

        Returns:
            Executor function that routes work and returns aggregated results

        Example:
            rules = [
                {"target": "weather-agent"},
                {"target": "events-agent"},
                {"target": "restaurant-agent"}
            ]
            executor = ADKPrimitives.router(rules, parallel=True)
            results = executor(context, {"query": "What should I do?", "location": "Seattle"})
            # Returns: {"weather-agent": {...}, "events-agent": {...}, "restaurant-agent": {...}}
        """
        logger = get_logger(context={"component": "ADKRouter"})
        timeout = timeout or 180

        def executor(context: WorkflowContext, input_data: NodeData) -> dict[str, Any]:
            """Execute routing logic"""
            logger.info(
                "Router executing",
            )

            results = {}

            if parallel:
                # Parallel execution using ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=len(rules)) as pool:
                    # Submit all targets
                    future_to_target = {}
                    for rule in rules:
                        target = rule["target"]
                        # Check if there's a condition
                        if "condition" in rule:
                            should_execute = ADKPrimitives._evaluate_condition(
                                rule["condition"], input_data
                            )
                            if not should_execute:
                                logger.info(
                                    f"Skipping target {target} (condition false)"
                                )
                                continue

                        future = pool.submit(
                            ADKPrimitives._execute_target, target, context, input_data
                        )
                        future_to_target[future] = target

                    # Collect results with timeout
                    for future in as_completed(future_to_target, timeout=timeout):
                        target = future_to_target[future]
                        try:
                            result = future.result()
                            results[target] = result
                            logger.info(f"Router: {target} completed successfully")
                        except Exception as e:
                            logger.error(f"Router: {target} failed")
                            results[target] = {"error": str(e)}
            else:
                # Sequential execution
                for rule in rules:
                    target = rule["target"]

                    # Check condition if present
                    if "condition" in rule:
                        should_execute = ADKPrimitives._evaluate_condition(
                            rule["condition"], input_data
                        )
                        if not should_execute:
                            logger.info(f"Skipping target {target} (condition false)")
                            continue

                    try:
                        result = ADKPrimitives._execute_target(
                            target, context, input_data
                        )
                        results[target] = result
                        logger.info(f"Router: {target} completed successfully")
                    except Exception as e:
                        logger.error(f"Router: {target} failed")
                        results[target] = {"error": str(e)}

            logger.info(
                "Router completed",
            )

            return results

        return executor

    @staticmethod
    def joiner(
        strategy: str = "merge",
        wait_for: list[str] | None = None,
        timeout: int | None = None,
    ) -> Callable[[WorkflowContext, NodeData], Any]:
        """
        Create a Joiner primitive executor.

        Aggregates results from multiple sources using specified strategy.

        Args:
            strategy: Joining strategy (merge, concatenate, vote, synthesize)
            wait_for: List of source node IDs to wait for (None = use all input data)
            timeout: Optional timeout for joining in seconds

        Returns:
            Executor function that joins results

        Example:
            # Merge strategy - combine dicts
            executor = ADKPrimitives.joiner(strategy="merge")
            result = executor(context, {
                "weather-agent": {"temp": 72},
                "events-agent": {"events": [...]
            }})
            # Returns: {"temp": 72, "events": [...]}
        """
        logger = get_logger(context={"component": "ADKJoiner"})
        timeout = timeout or 60

        def executor(context: WorkflowContext, input_data: NodeData) -> Any:
            """Execute joining logic"""
            logger.debug("Joiner executing")

            # Filter data if wait_for specified
            if wait_for:
                if isinstance(input_data, dict):
                    filtered_data = {
                        k: v for k, v in input_data.items() if k in wait_for
                    }
                else:
                    logger.warning(
                        f"wait_for specified but input_data is not dict (type={type(input_data).__name__})"
                    )
                    # If input is a string (pre-synthesized), wrap it properly
                    if isinstance(input_data, str):
                        filtered_data = {"pre_synthesized_result": input_data}
                    else:
                        filtered_data = input_data
            else:
                filtered_data = input_data

            # Apply joining strategy
            strategy_enum = (
                JoinerStrategy(strategy) if isinstance(strategy, str) else strategy
            )

            if strategy_enum == JoinerStrategy.MERGE:
                result = ADKPrimitives._join_merge(filtered_data)
            elif strategy_enum == JoinerStrategy.CONCATENATE:
                result = ADKPrimitives._join_concatenate(filtered_data)
            elif strategy_enum == JoinerStrategy.VOTE:
                result = ADKPrimitives._join_vote(filtered_data)
            elif strategy_enum == JoinerStrategy.SYNTHESIZE:
                result = ADKPrimitives._join_synthesize(filtered_data, context)
            else:
                logger.error(f"Unknown join strategy: {strategy}")
                result = filtered_data

            logger.debug("Joiner completed")
            return result

        return executor

    @staticmethod
    def condition(
        expression: str, true_branch: str, false_branch: str | None = None
    ) -> Callable[[WorkflowContext, NodeData], Any]:
        """
        Create a Condition primitive executor.

        Evaluates expression and routes to appropriate branch.

        Args:
            expression: Python expression to evaluate (safe eval)
            true_branch: Node ID to execute if condition is True
            false_branch: Optional node ID if condition is False

        Returns:
            Executor function that evaluates condition and executes branch

        Example:
            # Check weather condition
            executor = ADKPrimitives.condition(
                expression="data.get('weather_data', {}).get('condition') == 'rain'",
                true_branch="indoor_router",
                false_branch="outdoor_router"
            )
            result = executor(context, {"weather_data": {"condition": "rain"}})
            # Executes indoor_router node
        """
        logger = get_logger(context={"component": "ADKCondition"})

        def executor(context: WorkflowContext, input_data: NodeData) -> Any:
            """Execute conditional logic"""
            logger.info(
                "Condition evaluating",
            )

            # Evaluate condition
            try:
                condition_result = ADKPrimitives._evaluate_condition(
                    expression, input_data
                )
                logger.info(f"Condition evaluated to: {condition_result}")
            except Exception as e:
                logger.error(f"Condition evaluation failed: {e}")
                condition_result = False

            # Select branch
            selected_branch = true_branch if condition_result else false_branch

            if selected_branch is None:
                logger.info("Condition false and no false_branch, returning input_data")
                return input_data

            # Execute selected branch
            logger.info(f"Executing branch: {selected_branch}")
            result = ADKPrimitives._execute_target(selected_branch, context, input_data)

            logger.info("Condition completed")
            return result

        return executor

    @staticmethod
    def agent_call(
        agent_id: str,
        tool_name: str | None = None,
        timeout: int | None = None,
        input_mapping: dict[str, str] | None = None,
    ) -> Callable[[WorkflowContext, NodeData], dict[str, Any]]:
        """
        Create an AgentCall primitive executor.

        Calls an A2A agent via HTTP with optional input mapping from previous stages.

        Args:
            agent_id: ID of agent to call
            tool_name: Optional specific tool/capability to invoke
            timeout: Optional timeout for agent call in seconds (default: 180)
            input_mapping: Optional dict mapping agent's required fields to JSONPath expressions
                          (e.g., {"locations": "$.events_call.events"})

        Returns:
            Executor function that calls the agent

        Example without mapping:
            executor = ADKPrimitives.agent_call("weather-agent")
            result = executor(context, {"query": "Weather in Seattle"})

        Example with mapping:
            executor = ADKPrimitives.agent_call(
                "geography-agent",
                input_mapping={"locations": "$.events_call.events", "center_lat": "$.coords.latitude"}
            )
            result = executor(context, stage_results)
        """
        logger = get_logger(context={"component": "ADKAgentCall"})
        timeout = timeout or 180

        def executor(context: WorkflowContext, input_data: NodeData) -> dict[str, Any]:
            """Execute agent call"""
            logger.debug(
                "AgentCall executing",
            )

            # Get discovered agents from context
            discovered_agents = context.get("discovered_agents", {})

            if agent_id not in discovered_agents:
                logger.error(f"Agent {agent_id} not found in discovered agents")
                return {"error": f"Agent {agent_id} not available"}

            agent_info = discovered_agents[agent_id]
            base_url = agent_info["base_url"]
            agent_card = agent_info["agent_card"]

            # Get stage history for data mapping
            stage_history = context.get("stage_history", {})

            # Call agent using A2A protocol
            try:
                result = ADKPrimitives._call_a2a_agent(
                    agent_id=agent_id,
                    base_url=base_url,
                    agent_card=agent_card,
                    input_data=input_data,
                    input_mapping=input_mapping,
                    stage_history=stage_history,
                    timeout=timeout,
                )
                logger.info(f"AgentCall to {agent_id} completed successfully")
                return result

            except Exception as e:
                logger.error(
                    f"AgentCall to {agent_id} failed: {e!s}",
                    exc_info=True,
                    extra={"agent_id": agent_id, "error_type": type(e).__name__},
                )
                return {"error": str(e), "agent_id": agent_id}

        return executor

    # ========================================================================
    # Helper Methods
    # ========================================================================

    @staticmethod
    def _execute_target(
        target: str, context: WorkflowContext, input_data: NodeData
    ) -> Any:
        """
        Execute a target (either a workflow node or an agent).

        Args:
            target: Node ID or agent ID
            context: Workflow context
            input_data: Input data for target

        Returns:
            Result from target execution
        """
        logger = get_logger(context={"component": "ADKPrimitives"})

        # Check if target is a workflow node
        workflow_nodes = context.get("workflow_nodes", {})

        if target in workflow_nodes:
            # It's a workflow node - execute it
            node = workflow_nodes[target]
            if node.execute:
                return node.execute(context, input_data)
            else:
                logger.error(f"Node {target} has no executor")
                return {"error": f"Node {target} cannot be executed"}

        # Check if target is an agent
        discovered_agents = context.get("discovered_agents", {})

        if target in discovered_agents:
            # It's an agent - call it
            agent_info = discovered_agents[target]
            return ADKPrimitives._call_a2a_agent(
                agent_id=target,
                base_url=agent_info["base_url"],
                agent_card=agent_info["agent_card"],
                input_data=input_data,
                timeout=30,
            )

        # Target not found
        logger.error(f"Target {target} not found in nodes or agents")
        return {"error": f"Target {target} not found"}

    @staticmethod
    def _call_a2a_agent(
        agent_id: str,
        base_url: str,
        agent_card: dict[str, Any],
        input_data: NodeData,
        timeout: int = 30,
        input_mapping: dict[str, str] | None = None,
        stage_history: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Call an A2A agent via HTTP.

        Args:
            agent_id: Agent identifier
            base_url: Agent's base URL
            agent_card: Agent's card with capabilities
            input_data: Input data (typically dict with query, etc.)
            timeout: Timeout in seconds
            input_mapping: Optional JSONPath mappings for extracting data from stage_history
            stage_history: Accumulated results from previous workflow stages

        Returns:
            Agent response data
        """
        logger = get_logger(context={"component": "ADKPrimitives"})
        logger.debug(
            f"Calling A2A agent: {agent_id}",
        )

        # Create A2A task
        task_id = str(uuid.uuid4())
        context_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())

        # Build task input data based on input_mapping or fallback to direct pass-through
        # DIAGNOSTIC: Log what we're checking (using f-strings for CloudWatch compatibility)
        logger.info(
            f"🔍 DIAGNOSTIC - Checking input_mapping for {agent_id}: "
            f"has_input_mapping={bool(input_mapping)} input_mapping={input_mapping} "
            f"has_stage_history={bool(stage_history)} stage_history_type={type(stage_history).__name__} "
            f"stage_history={stage_history if stage_history else 'Empty/None'}"
        )

        if input_mapping:
            # Use input_mapping to extract data from stage_history
            from lib.jsonpath_util import build_mapped_input

            # Log the input_mapping structure for debugging (using f-strings for CloudWatch)
            stage_hist_keys = (
                list(stage_history.keys())
                if isinstance(stage_history, dict)
                else "not a dict"
            )
            logger.info(
                f"📋 Building mapped input for {agent_id}: "
                f"input_mapping_keys={list(input_mapping.keys())} input_mapping={input_mapping} "
                f"stage_history_keys={stage_hist_keys}"
            )

            task_input_data = build_mapped_input(
                stage_results=stage_history if stage_history else {},
                input_mapping=input_mapping,
                fallback_data=input_data if isinstance(input_data, dict) else {},
            )

            # Always include query if available
            if isinstance(input_data, dict):
                user_query = input_data.get("query", "")
                if user_query and "query" not in task_input_data:
                    task_input_data["query"] = user_query
            else:
                user_query = str(input_data)

            # 🔍 DIAGNOSTIC: Log complete mapped input data being sent to agent (DEBUG level)
            mapped_data_preview = {}
            for key, value in task_input_data.items():
                if isinstance(value, list):
                    mapped_data_preview[key] = f"<list with {len(value)} items>"
                    # Log first item preview for arrays
                    if len(value) > 0:
                        mapped_data_preview[f"{key}_first_item"] = str(value[0])[:100]
                elif isinstance(value, dict):
                    mapped_data_preview[key] = (
                        f"<dict with {len(value)} keys: {list(value.keys())[:5]}>"
                    )
                else:
                    mapped_data_preview[key] = str(value)[:100]

            logger.info(
                f"📤 Sending mapped input to {agent_id}: "
                f"mapped_data_keys={list(task_input_data.keys())} mapped_data_preview={mapped_data_preview}"
            )
        else:
            # No mapping - pass input_data directly (original behavior)
            logger.info(
                f"⚠️ DIAGNOSTIC - No input_mapping provided for {agent_id}: "
                f"input_data_type={type(input_data).__name__}"
            )
            if isinstance(input_data, dict):
                user_query = input_data.get("query", "")
                task_input_data = dict(input_data)  # Copy to avoid mutation
            else:
                user_query = str(input_data)
                task_input_data = {"query": user_query}

        task_message = Message(
            role=Role.user,
            parts=[
                TextPart(kind="text", text=user_query, metadata={}),  # type: ignore[list-item]  # Pydantic validates at runtime
                DataPart(kind="data", data=task_input_data, metadata={}),  # type: ignore[list-item]  # Pydantic validates at runtime
            ],
            message_id=message_id,
            kind="message",
            context_id=context_id,
            task_id=task_id,
        )

        task = Task(
            id=task_id,
            context_id=context_id,
            kind="task",
            history=[task_message],
            status=TaskStatus(
                state=TaskState.submitted,
                timestamp=datetime.now(UTC).isoformat() + "Z",
            ),
            input=task_input_data,  # type: ignore[call-arg]  # Pydantic accepts extra fields
            artifacts=[],
            metadata={},
        )

        # Call agent using synchronous httpx.Client
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{base_url}/message/send", json=task.model_dump(mode="json")
                )
                response.raise_for_status()
                result = Task.model_validate(response.json())

            # DIAGNOSTIC: Log response structure inline (extra={} doesn't show in CloudWatch)
            has_artifacts = bool(result.artifacts)
            artifacts_count = len(result.artifacts) if result.artifacts else 0
            first_artifact_parts_count = (
                len(result.artifacts[0].parts)
                if result.artifacts and len(result.artifacts) > 0
                else 0
            )
            first_part_type = (
                type(result.artifacts[0].parts[0]).__name__
                if result.artifacts
                and len(result.artifacts) > 0
                and len(result.artifacts[0].parts) > 0
                else "none"
            )
            first_part_has_kind = (
                hasattr(result.artifacts[0].parts[0], "kind")
                if result.artifacts
                and len(result.artifacts) > 0
                and len(result.artifacts[0].parts) > 0
                else False
            )
            first_part_has_data = (
                hasattr(result.artifacts[0].parts[0], "data")
                if result.artifacts
                and len(result.artifacts) > 0
                and len(result.artifacts[0].parts) > 0
                else False
            )
            logger.debug(
                f"🔍 {agent_id} response: artifacts={has_artifacts} count={artifacts_count} parts={first_artifact_parts_count} type={first_part_type} has_kind={first_part_has_kind} has_data={first_part_has_data}"
            )

            # Extract data from result
            if result.artifacts and len(result.artifacts) > 0:
                artifact = result.artifacts[0]
                logger.debug(
                    f"🔍 ORCHESTRATOR - Received artifact with {len(artifact.parts)} parts from {agent_id}"
                )

                for i, part in enumerate(artifact.parts):
                    part_type = type(part).__name__
                    has_root = hasattr(part, "root")
                    has_kind = hasattr(part, "kind")
                    has_data = hasattr(part, "data")

                    logger.debug(
                        f"🔍 ORCHESTRATOR - Part {i}: type={part_type} has_root={has_root} has_kind={has_kind} has_data={has_data}"
                    )

                    # Handle different part structures
                    if hasattr(part, "root"):
                        # New structure: part.root.kind and part.root.data
                        logger.debug(
                            f"🔍 ORCHESTRATOR - Part {i} has root: root_type={type(part.root).__name__}"
                        )
                        if hasattr(part.root, "kind"):
                            logger.debug(
                                f"🔍 ORCHESTRATOR - Part {i}.root.kind={part.root.kind}"
                            )
                        if part.root.kind == "data":
                            logger.debug(
                                f"✅ ORCHESTRATOR - Found data in part.root.data from {agent_id}"
                            )
                            response_data = part.root.data
                            response_data["agent_id"] = agent_id
                            response_data["agent_name"] = agent_card.get(
                                "name", agent_id
                            )
                            return response_data
                    elif hasattr(part, "kind") and part.kind == "data":  # type: ignore[attr-defined]  # Defensive check for old Part structure
                        # Direct structure: part.kind and part.data
                        logger.info(
                            f"✅ ORCHESTRATOR - Found data in part.data from {agent_id}"
                        )
                        response_data = part.data if hasattr(part, "data") else {}  # type: ignore[attr-defined]  # Defensive check for old Part structure
                        response_data["agent_id"] = agent_id
                        response_data["agent_name"] = agent_card.get("name", agent_id)
                        return response_data
                    else:
                        logger.warning(
                            f"⚠️ ORCHESTRATOR - Part {i} has no recognizable structure"
                        )

            logger.warning(
                f"{agent_id} returned no data in expected format",
            )
            return {"error": f"No data returned from {agent_id}"}

        except httpx.TimeoutException:
            logger.error(f"{agent_id} call timed out")
            return {"error": f"Agent call timed out after {timeout}s"}
        except Exception as e:
            logger.error(
                f"{agent_id} call failed: {e!s}",
                exc_info=True,
                extra={"agent_id": agent_id, "error_type": type(e).__name__},
            )
            return {"error": str(e)}

    @staticmethod
    def _evaluate_condition(expression: str, data: Any) -> bool:
        """
        Safely evaluate a condition expression.

        Uses restricted eval with limited builtins to prevent code injection.

        Args:
            expression: Python expression to evaluate
            data: Data context for evaluation (available as 'data' variable)

        Returns:
            Boolean result of evaluation

        Example:
            result = _evaluate_condition(
                "data.get('temp', 0) > 80",
                {"temp": 85}
            )
            # Returns: True
        """
        logger = get_logger(context={"component": "ADKPrimitives"})

        # Safe builtins whitelist
        safe_builtins = {
            "True": True,
            "False": False,
            "None": None,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "dict": dict,
            "list": list,
            "any": any,
            "all": all,
        }

        # Create safe namespace
        namespace = {"__builtins__": safe_builtins, "data": data}

        try:
            result = eval(expression, namespace)
            return bool(result)
        except Exception as e:
            logger.error(
                f"Condition evaluation failed: {e}",
            )
            return False

    @staticmethod
    def _join_merge(data: Any) -> dict[str, Any]:
        """
        Merge strategy: Combine dictionaries into single dict.

        Args:
            data: Dict of results or list of results

        Returns:
            Merged dictionary
        """
        merged = {}

        if isinstance(data, dict):
            # data is dict of agent_id -> result
            for key, value in data.items():
                if isinstance(value, dict) and "error" not in value:
                    merged.update(value)
                else:
                    merged[key] = value
        elif isinstance(data, list):
            # data is list of results
            for item in data:
                if isinstance(item, dict):
                    merged.update(item)

        return merged

    @staticmethod
    def _join_concatenate(data: Any) -> list[Any]:
        """
        Concatenate strategy: Create list of all results.

        Args:
            data: Dict of results or list of results

        Returns:
            List of results
        """
        results = []

        if isinstance(data, dict):
            results = list(data.values())
        elif isinstance(data, list):
            results = data
        else:
            results = [data]

        return results

    @staticmethod
    def _join_vote(data: Any) -> Any:
        """
        Vote strategy: Return most common result.

        Args:
            data: Dict of results or list of results

        Returns:
            Most common result
        """
        results = []

        if isinstance(data, dict):
            results = list(data.values())
        elif isinstance(data, list):
            results = data
        else:
            return data

        # Simple voting: return most common result
        # (works for simple values, not complex dicts)
        if not results:
            return None

        # Convert to JSON strings for comparison
        result_strs = [json.dumps(r, sort_keys=True) for r in results]
        vote_counts = {}

        for rs in result_strs:
            vote_counts[rs] = vote_counts.get(rs, 0) + 1

        # Get most common
        most_common_str = max(vote_counts, key=vote_counts.get)  # type: ignore[arg-type]  # Valid Python idiom for finding key with max value
        return json.loads(most_common_str)

    @staticmethod
    def _join_synthesize(data: Any, context: WorkflowContext) -> str | dict[str, Any]:
        """
        Synthesize strategy: Use LLM to synthesize results.

        Args:
            data: Dict of results or list of results
            context: Workflow context (contains bedrock_model)

        Returns:
            Synthesized response as string or dict (fallback to merge)
        """
        logger = get_logger(context={"component": "ADKPrimitives"})

        # Get GenericSynthesizer from context if available
        synthesizer = context.get("synthesizer")
        query = context.get("query", "")

        if synthesizer:
            try:
                # Use GenericSynthesizer
                if isinstance(data, dict):
                    agent_responses = data
                elif isinstance(data, str):
                    # If data is already a string (pre-synthesized), return it directly
                    # This prevents character-by-character splitting of synthesized strings
                    logger.info(
                        f"Data is already synthesized string ({len(data)} chars), returning as-is"
                    )
                    return data
                else:
                    # Convert list to dict
                    agent_responses = {
                        f"source_{i}": item for i, item in enumerate(data)
                    }

                result = synthesizer.synthesize(
                    user_query=query, agent_responses=agent_responses, agent_metadata={}
                )
                return result
            except Exception as e:
                logger.error(f"LLM synthesis failed: {e}")
                # Fallback to merge
                return ADKPrimitives._join_merge(data)
        else:
            logger.warning("No synthesizer available, falling back to merge")
            return ADKPrimitives._join_merge(data)
