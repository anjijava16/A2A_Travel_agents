#!/usr/bin/env python3
"""
Generic Synthesizer - Domain-Agnostic Response Synthesis

Uses Claude Sonnet 4 to synthesize agent responses into coherent narratives
across ANY domain without hardcoded templates or domain-specific logic.

Key Features:
    - Works with any JSON response structure
    - Dynamic structure detection (arrays, objects, primitives)
    - Context-aware narrative generation
    - Cross-agent intelligence synthesis

Example:
    Travel: weather + events + restaurants → "Due to rain, I recommend indoor activities..."
    Finance: market + portfolio + risk → "Based on current volatility, consider..."
    Healthcare: symptoms + treatment + drugs → "Given your symptoms, treatment options include..."
"""

import json
from typing import Any

from strands import Agent as StrandsAgent
from strands.agent.conversation_manager.null_conversation_manager import (
    NullConversationManager,
)
from strands.models import BedrockModel

from lib.config import config
from lib.logger import get_logger
from lib.orchestration.token_budget_manager import TokenBudgetManager


class GenericSynthesizer:
    """
    Domain-agnostic response synthesizer using Claude Sonnet 4.

    Synthesizes multiple agent responses into coherent, user-friendly narratives
    without any hardcoded domain knowledge or templates.

    Configuration:
        Uses centralized core.config module for all settings.
        Override via environment variables with CORE_ prefix.
        See core.config for full configuration options.
    """

    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
        max_tokens: int | None = None,
    ):
        """
        Initialize GenericSynthesizer.

        Args:
            model_id: Claude model ID (defaults to config.bedrock_model_id)
            region: AWS region (defaults to config.aws_region)
            max_tokens: Max tokens for synthesis (defaults to config.synthesizer_max_tokens)
        """
        self.model_id = model_id or config.bedrock_model_id
        self.region = region or config.aws_region
        self.max_tokens = max_tokens or config.synthesizer_max_tokens

        # Initialize logger with component context
        self.logger = get_logger(context={"component": "GenericSynthesizer"})

        # Track invocation count to detect state accumulation
        self.invocation_count = 0

        # Initialize token budget manager
        # Uses separate model IDs for inference vs token counting
        self.token_manager = TokenBudgetManager(
            model_id=self.model_id,  # Cross-region profile for inference
            token_counter_model_id=config.token_counter_model_id,  # Foundation model for counting
            region=self.region,
            budget=180_000,  # 180K token budget (10% safety margin from 200K model limit)
        )

        # Initialize Bedrock model
        try:
            self.bedrock_model = BedrockModel(
                model_id=self.model_id,
                streaming=False,
                region_name=self.region,
                max_tokens=self.max_tokens,
            )

            self.strands_agent = StrandsAgent(
                model=self.bedrock_model,
                system_prompt=self._get_system_prompt(),
                conversation_manager=NullConversationManager(),  # No history accumulation for stateless synthesis
            )

            self.logger.info(
                "Initialized GenericSynthesizer",
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
        Generate system prompt for LLM synthesis.

        Returns:
            System prompt instructing LLM on synthesis task
        """
        return """You are an expert information synthesizer. Your job is to combine information from multiple specialist agents into clear, actionable responses.

You will be given:
1. A user's original query
2. Responses from multiple specialist agents (any domain)
3. Agent metadata (names, reasoning for selection)

Your task:
- Synthesize ALL agent responses into a coherent narrative
- Identify cross-agent patterns and relationships
- Provide clear, actionable recommendations
- Maintain accuracy (don't invent information)
- Structure your response logically

Guidelines:
- Start with a direct answer to the user's query
- Integrate information naturally (don't just list agent responses)
- Highlight important connections between agent insights
- Use natural language (avoid technical jargon unless domain-appropriate)
- Be concise (2-4 paragraphs typically sufficient)

Example patterns:
- "Based on [Agent A's] analysis and [Agent B's] data, I recommend..."
- "The [Agent A] indicates X, which aligns with [Agent B's] finding that Y..."
- "Considering both [Agent A's] forecast and [Agent B's] suggestions..."

Important:
- Work with ANY domain (travel, finance, healthcare, etc.)
- No assumptions about response structure
- Extract key information dynamically
- Synthesize intelligently, not mechanically

Critical Thinking & Data Relationships:
Your synthesis must go beyond simple concatenation - apply logical reasoning to ALL data:

1. **Examine the complete data landscape**: Look at ALL fields, properties, and attributes provided by agents. Each piece of information exists for a reason.

2. **Identify logical relationships**: Consider how different data points relate to each other. Do certain attributes suggest compatibility or incompatibility? Do some data points constrain or influence others?

3. **Reason about consistency**: When multiple agents provide information, reason about which recommendations are logically consistent with ALL the data, not just some of it.

4. **Use contextual signals**: Agents may provide attributes, flags, or metadata that carry semantic meaning. Use your understanding to interpret what these signals mean for the user's query.

5. **Explain your reasoning**: When data influenced your recommendations, explain WHY to the user. Make your logical connections explicit.

Examples of critical thinking (domain-agnostic):
- If data suggests constraint X, prioritize options compatible with X
- If attributes indicate property Y, consider Y when recommending items
- If multiple data points suggest pattern Z, make Z explicit in your synthesis
- When data contains compatibility signals, use them to filter/rank recommendations

Your goal: Provide recommendations that reflect thoughtful analysis of ALL available information, not just mechanical aggregation.
"""

    def synthesize(
        self,
        user_query: str,
        agent_responses: dict[str, Any],
        agent_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        """
        Synthesize agent responses into coherent narrative.

        Args:
            user_query: Original user question or request
            agent_responses: Dictionary of agent_id -> response data
            agent_metadata: Optional metadata about agents (names, reasoning, scores)

        Returns:
            Synthesized response as natural language text

        Raises:
            ValueError: If query is empty or no agent responses provided
            RuntimeError: If LLM invocation fails
        """
        # Validation
        if not user_query or not user_query.strip():
            raise ValueError("Query cannot be empty")

        if not agent_responses:
            raise ValueError("No agent responses to synthesize")

        # Increment invocation counter
        self.invocation_count += 1

        self.logger.info(
            f"🔄 SYNTHESIS INVOCATION #{self.invocation_count} - Starting response synthesis",
            extra={
                "invocation_count": self.invocation_count,
                "agent_count": len(agent_responses),
                "query_length": len(user_query),
            },
        )

        # Iterative truncation with ValidationException handling
        # Strategy: Catch CountTokens failures, truncate aggressively (25%), retry
        max_attempts = 10
        reduction_per_attempt = 0.25  # 25% reduction each iteration
        current_responses = agent_responses

        # Account for system prompt in budget (measure once)
        system_prompt = self._get_system_prompt()
        try:
            system_tokens = self.token_manager.count_tokens(system_prompt)
            effective_budget = self.token_manager.budget - system_tokens
            self.logger.debug(
                f"System prompt: {system_tokens} tokens, effective budget: {effective_budget}"
            )
        except Exception:
            # If system prompt fails to count, use full budget (conservative)
            effective_budget = self.token_manager.budget
            self.logger.warning(
                "Could not count system prompt tokens, using full budget"
            )

        for attempt in range(1, max_attempts + 1):
            # Build context with current responses
            context = self._build_synthesis_context(
                current_responses, agent_metadata or {}
            )

            # 🔍 DIAGNOSTIC: Log context size and structure
            context_size = len(context)
            self.logger.info(
                f"🔍 SYNTHESIS CONTEXT - Attempt {attempt}: "
                f"context_chars={context_size} "
                f"context_preview={context[:500]}... "
                f"agent_count={len(current_responses)} "
                f"agent_ids={list(current_responses.keys())}"
            )

            # Create prompt
            prompt = f"""User Query: "{user_query}"

Agent Responses:
{context}

Synthesize these agent responses into a clear, actionable answer to the user's query."""

            # Try to count tokens
            try:
                from botocore.exceptions import ClientError

                # Call count_tokens directly to catch ValidationException
                messages = [{"role": "user", "content": [{"text": prompt}]}]
                response = self.token_manager.bedrock_runtime.count_tokens(
                    modelId=self.token_manager.token_counter_model_id,
                    input={"converse": {"messages": messages}},
                )
                token_count = response["inputTokens"]

                # Successfully counted - check if within budget
                if token_count <= effective_budget:
                    # Calculate total tokens and budget utilization
                    sys_tokens = system_tokens if 'system_tokens' in locals() else 0
                    total_tokens = token_count + sys_tokens
                    utilization_pct = (total_tokens / self.token_manager.budget) * 100

                    if attempt == 1:
                        # No truncation needed - data fits naturally
                        self.logger.info(
                            f"✓ Data fits within budget: {token_count:,} user + {sys_tokens} system = {total_tokens:,} tokens "
                            f"({utilization_pct:.1f}% of {self.token_manager.budget:,} budget, no truncation needed)"
                        )
                    else:
                        # Truncation occurred
                        self.logger.info(
                            f"✓ Truncation successful after {attempt} attempts: {token_count:,} user + {sys_tokens} system = {total_tokens:,} tokens "
                            f"({utilization_pct:.1f}% of {self.token_manager.budget:,} budget)"
                        )
                    break
                else:
                    self.logger.info(
                        f"Attempt {attempt}: {token_count} tokens exceeds budget "
                        f"({effective_budget}), applying {reduction_per_attempt*100}% truncation"
                    )

            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "ValidationException" and "too long" in str(e):
                    self.logger.warning(
                        f"Attempt {attempt}: Input too large to count "
                        f"(~{len(prompt)//4:,} estimated tokens), applying {reduction_per_attempt*100}% truncation"
                    )
                else:
                    # Different error - use estimate
                    self.logger.error(f"Token counting failed: {e}")
                    token_count = len(prompt) // 4
                    if token_count <= effective_budget:
                        break

            except Exception as e:
                # Unexpected error - use estimate
                self.logger.error(f"Unexpected error counting tokens: {e}")
                token_count = len(prompt) // 4
                if token_count <= effective_budget:
                    break

            # Apply truncation for next iteration
            current_responses = self.token_manager.apply_proportional_truncation(
                current_responses, reduction_per_attempt
            )
        else:
            # Max attempts reached
            self.logger.error(
                f"Failed to reduce context below budget after {max_attempts} attempts, "
                f"proceeding with best effort"
            )

        try:
            # 🔍 DIAGNOSTIC: Log what we're about to send to Bedrock
            self.logger.info(
                f"📤 BEDROCK REQUEST - Invocation #{self.invocation_count}: "
                f"prompt_chars={len(prompt)} "
                f"final_token_count={token_count if 'token_count' in locals() else 'unknown'} "
                f"prompt_preview={prompt[:1000]}..."
            )

            # Check conversation manager state (if accessible)
            if hasattr(self.strands_agent, 'conversation_manager'):
                conv_mgr = self.strands_agent.conversation_manager
                conv_mgr_type = type(conv_mgr).__name__
                has_history = hasattr(conv_mgr, 'conversation_history')
                history_len = len(conv_mgr.conversation_history) if has_history else 0
                self.logger.info(
                    f"🔍 CONVERSATION STATE - Invocation #{self.invocation_count}: "
                    f"manager_type={conv_mgr_type} "
                    f"has_history={has_history} "
                    f"history_length={history_len}"
                )

            # Invoke LLM (NullConversationManager ensures no history accumulation)
            response = str(self.strands_agent(prompt))

            self.logger.info(
                "Synthesis complete",
                extra={
                    "response_length": len(response),
                    "agent_count": len(agent_responses),
                },
            )

            return response

        except Exception as e:
            self.logger.error(
                "LLM synthesis failed, using fallback",
                extra={"error": str(e), "agent_count": len(agent_responses)},
                exc_info=True,
            )

            # Fallback: Simple concatenation
            return self._fallback_synthesis(user_query, agent_responses)

    def _build_synthesis_context(
        self, agent_responses: dict[str, Any], agent_metadata: dict[str, dict[str, Any]]
    ) -> str:
        """
        Build human-readable context from agent responses for LLM.

        Dynamically detects response structure and extracts key information.

        Args:
            agent_responses: Dictionary of agent_id -> response data
            agent_metadata: Metadata about agents (names, reasoning, etc.)

        Returns:
            Formatted string describing all agent responses
        """
        context_lines = []

        for agent_id, response_data in agent_responses.items():
            # Get agent metadata if available
            metadata = agent_metadata.get(agent_id, {})
            agent_name = metadata.get("agent_name", agent_id)
            reasoning = metadata.get("reasoning", "")

            context_lines.append(f"\n--- {agent_name} (ID: {agent_id}) ---")

            if reasoning:
                context_lines.append(f"Selection Reasoning: {reasoning}")

            # Check for errors - ensure response_data is a dict first
            if isinstance(response_data, dict) and "error" in response_data:
                context_lines.append(f"ERROR: {response_data['error']}")
                continue
            elif not isinstance(response_data, dict):
                # Handle non-dict responses (int, str, list, None, etc.)
                context_lines.append(f"Response: {response_data}")
                continue

            # Dynamically extract information from response
            # This works with ANY JSON structure - no domain assumptions
            info = self._extract_response_info(response_data)

            for line in info:
                context_lines.append(f"  {line}")

        return "\n".join(context_lines)

    def _extract_response_info(self, data: Any, prefix: str = "") -> list:
        """
        Recursively extract information from any JSON structure.

        Handles arrays, objects, primitives dynamically without domain knowledge.

        Args:
            data: Response data (any JSON-serializable structure)
            prefix: Prefix for nested keys

        Returns:
            List of formatted strings describing the data
        """
        info_lines = []

        if isinstance(data, dict):
            for key, value in data.items():
                # Skip metadata fields that don't add value
                if key in ["agent_id", "agent_name", "timestamp"]:
                    continue

                if isinstance(value, (dict, list)):
                    # Nested structure - recurse
                    nested_info = self._extract_response_info(value, f"{prefix}{key}.")
                    info_lines.extend(nested_info)
                else:
                    # Primitive value - format nicely
                    info_lines.append(f"{prefix}{key}: {value}")

        elif isinstance(data, list):
            if not data:
                info_lines.append(f"{prefix}(empty list)")
            else:
                # Show all items - no truncation
                # Synthesis LLM needs complete data to use fields like opening_hours
                info_lines.append(f"{prefix}({len(data)} items)")
                for i, item in enumerate(data):
                    nested_info = self._extract_response_info(item, f"{prefix}[{i}].")
                    info_lines.extend(nested_info)

        else:
            # Primitive value at root
            info_lines.append(f"{prefix}{data}")

        return info_lines

    def _fallback_synthesis(
        self, user_query: str, agent_responses: dict[str, Any]
    ) -> str:
        """
        Fallback synthesis when LLM is unavailable.

        Simple concatenation of agent responses without intelligence.

        Args:
            user_query: User's query
            agent_responses: Agent responses

        Returns:
            Basic synthesized response
        """
        lines = [
            f"Response to: {user_query}",
            "",
            "Information from specialist agents:",
            "",
        ]

        for agent_id, response_data in agent_responses.items():
            lines.append(f"• {agent_id}:")

            # Handle non-dict responses (could be float, string, None, etc.)
            if not isinstance(response_data, dict):
                lines.append(f"  {response_data!s}")
            elif "error" in response_data:
                lines.append(f"  ERROR: {response_data['error']}")
            else:
                # Try to extract main content
                content_str = json.dumps(response_data, indent=2)[:500]
                lines.append(f"  {content_str}")

            lines.append("")

        return "\n".join(lines)
