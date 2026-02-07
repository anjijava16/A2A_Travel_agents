#!/usr/bin/env python3
"""
Query Decomposer - LLM-Powered Query Analysis

Uses Claude Sonnet 4 to analyze user queries and match them to agent capabilities
through semantic understanding. This enables domain-agnostic orchestration without
hardcoded keywords or rules.

Key Features:
    - Semantic capability matching using LLM
    - Confidence scoring (0-100) for agent relevance
    - Multi-intent detection (query may need multiple agents)
    - Contextual reasoning (understands implicit requirements)

Example:
    query = "What should I do in Seattle this weekend?"
    agent_cards = [weather_card, events_card, restaurant_card]

    result = decomposer.decompose(query, agent_cards)
    # Returns: [weather-agent: 95, events-agent: 90, restaurant-agent: 75]
"""

from dataclasses import dataclass
import json
from typing import Any

from strands import Agent as StrandsAgent
from strands.models import BedrockModel

from lib.config import config
from lib.logger import get_logger


@dataclass
class AgentSelection:
    """
    Represents a selected agent with relevance score.

    Attributes:
        agent_id: Unique agent identifier
        agent_name: Human-readable agent name
        relevance_score: Confidence score (0-100) indicating how relevant the agent is
        reasoning: LLM's explanation for why this agent was selected
        matched_capabilities: List of capability IDs that matched the query
    """

    agent_id: str
    agent_name: str
    relevance_score: int  # 0-100
    reasoning: str
    matched_capabilities: list[str]


@dataclass
class DecompositionResult:
    """
    Result of query decomposition.

    Attributes:
        query: Original user query
        selected_agents: List of agents to invoke, sorted by relevance score
        total_agents_analyzed: Total number of agents evaluated
        llm_reasoning: Overall LLM reasoning for agent selection strategy
    """

    query: str
    selected_agents: list[AgentSelection]
    total_agents_analyzed: int
    llm_reasoning: str


class QueryDecomposer:
    """
    LLM-powered query decomposition for domain-agnostic agent selection.

    Uses Claude Sonnet 4 to semantically match user queries to agent capabilities
    without any hardcoded domain knowledge or keyword matching.

    Configuration:
        Uses centralized core.config module for all settings.
        Override via environment variables with CORE_ prefix.
        See core.config for full configuration options.
    """

    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
        relevance_threshold: int | None = None,
    ):
        """
        Initialize QueryDecomposer.

        Args:
            model_id: Claude model ID (defaults to config.bedrock_model_id)
            region: AWS region (defaults to config.aws_region)
            relevance_threshold: Min relevance score (defaults to config.query_threshold)
        """
        self.model_id = model_id or config.bedrock_model_id
        self.region = region or config.aws_region
        self.relevance_threshold = relevance_threshold or config.query_threshold

        # Initialize logger with component context
        self.logger = get_logger(context={"component": "QueryDecomposer"})

        # Initialize Bedrock model
        try:
            self.bedrock_model = BedrockModel(
                model_id=self.model_id,
                streaming=False,
                region_name=self.region,
                max_tokens=config.decomposer_max_tokens,
            )

            self.strands_agent = StrandsAgent(
                model=self.bedrock_model,
                system_prompt=self._get_system_prompt(),
            )

            self.logger.info(
                "Initialized QueryDecomposer",
                extra={
                    "model_id": self.model_id,
                    "region": self.region,
                    "relevance_threshold": self.relevance_threshold,
                    "max_tokens": config.decomposer_max_tokens,
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
        Generate system prompt for LLM query decomposition with dependency awareness.

        Returns:
            System prompt instructing LLM on agent selection and dependency detection
        """
        return """You are an expert agent coordinator. Your job is to analyze user queries and determine which specialist agents should handle them.

You will be given:
1. A user query (any domain: travel, finance, healthcare, e-commerce, etc.)
2. A list of available specialist agents with their capabilities

Your task:
- Analyze the query to understand user intent
- Match query requirements to agent capabilities semantically (not just keywords)
- Assign relevance scores (0-100) to each agent
- Provide clear reasoning for your selections

Scoring guidelines:
- 90-100: Agent is ESSENTIAL for answering the query
- 70-89: Agent provides VALUABLE information
- 50-69: Agent MAY be helpful but not critical
- 0-49: Agent is NOT relevant

Output format (JSON):
{
  "reasoning": "Overall strategy for answering the query",
  "agents": [
    {
      "agent_id": "weather-agent",
      "relevance_score": 95,
      "reasoning": "Weather data essential for planning outdoor activities",
      "matched_capabilities": ["get-weather", "get-forecast"]
    },
    {
      "agent_id": "events-agent",
      "relevance_score": 90,
      "reasoning": "Event recommendations crucial for weekend planning",
      "matched_capabilities": ["search-events"]
    }
  ]
}

Important:
- Be precise: Don't select agents that aren't truly needed
- Be inclusive: Select all agents that could provide valuable information
- Think semantically: "weather in Seattle" should match weather agents even without keyword "weather"
- Consider cross-domain intelligence: Weather affects event planning, budget constraints affect recommendations
"""

    def decompose(
        self, user_query: str, agent_cards: dict[str, dict[str, Any]]
    ) -> DecompositionResult:
        """
        Decompose user query and select relevant agents.

        Args:
            user_query: User's question or request
            agent_cards: Dictionary of agent_id -> agent_card data

        Returns:
            DecompositionResult with selected agents and reasoning

        Raises:
            ValueError: If query is empty or no agents provided
            RuntimeError: If LLM invocation fails
        """
        # Validation
        if not user_query or not user_query.strip():
            raise ValueError("Query cannot be empty")

        if not agent_cards:
            raise ValueError("No agent cards provided")

        self.logger.info(
            "Analyzing query",
            extra={
                "query": user_query[:100],  # First 100 chars
                "query_length": len(user_query),
                "available_agents": len(agent_cards),
            },
        )

        # Build agent capability summary for LLM
        agent_summary = self._build_agent_summary(agent_cards)

        # Create prompt for LLM
        prompt = f"""User Query: "{user_query}"

Available Specialist Agents:
{agent_summary}

Analyze this query and select the most relevant agents. Provide your response in JSON format."""

        try:
            # Invoke LLM
            response = str(self.strands_agent(prompt))

            # Parse LLM response
            result = self._parse_llm_response(response, agent_cards, user_query)

            self.logger.info(
                "Agent selection complete",
                extra={
                    "selected_count": len(result.selected_agents),
                    "total_analyzed": result.total_agents_analyzed,
                    "threshold": self.relevance_threshold,
                },
            )

            # Log individual selections at debug level (less verbose)
            for selection in result.selected_agents:
                self.logger.info(
                    "Selected agent",
                    extra={
                        "agent_id": selection.agent_id,
                        "relevance_score": selection.relevance_score,
                        "reasoning": selection.reasoning[:100],  # First 100 chars
                    },
                )

            return result

        except Exception as e:
            self.logger.error(
                "Query decomposition failed",
                extra={"query": user_query[:100], "error": str(e)},
                exc_info=True,
            )
            raise RuntimeError(f"Query decomposition failed: {e}")

    def _build_agent_summary(self, agent_cards: dict[str, dict[str, Any]]) -> str:
        """
        Build human-readable summary of agent capabilities for LLM.

        Args:
            agent_cards: Dictionary of agent_id -> agent_card

        Returns:
            Formatted string describing all agents and their capabilities
        """
        summary_lines = []

        for agent_id, card in agent_cards.items():
            agent_name = card.get("name", agent_id)
            description = card.get("description", "No description")

            # A2A spec uses 'skills' not 'capabilities'
            skills = card.get("skills", [])

            summary_lines.append(f"\n{agent_id} ({agent_name}):")
            summary_lines.append(f"  Description: {description}")

            if skills:
                summary_lines.append("  Capabilities:")
                for skill in skills:
                    # Skills can be dict or AgentSkill objects
                    if isinstance(skill, dict):
                        skill_name = skill.get("name", "Unknown")
                        skill_desc = skill.get("description", "")
                        skill_id = skill.get("id", "")
                    else:
                        # AgentSkill object
                        skill_name = skill.name
                        skill_desc = skill.description
                        skill_id = skill.id

                    summary_lines.append(
                        f"    - {skill_name} ({skill_id}): {skill_desc}"
                    )

        return "\n".join(summary_lines)

    def _parse_llm_response(
        self, llm_response: str, agent_cards: dict[str, dict[str, Any]], user_query: str
    ) -> DecompositionResult:
        """
        Parse LLM JSON response into DecompositionResult.

        Args:
            llm_response: Raw LLM output (should be JSON)
            agent_cards: Original agent cards for validation
            user_query: Original user query

        Returns:
            Parsed DecompositionResult

        Raises:
            RuntimeError: If parsing fails or response is invalid
        """
        try:
            # Extract JSON from response (LLM may include markdown code blocks)
            json_str = llm_response.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]  # Remove ```json
            if json_str.startswith("```"):
                json_str = json_str[3:]  # Remove ```
            if json_str.endswith("```"):
                json_str = json_str[:-3]  # Remove trailing ```
            json_str = json_str.strip()

            # Parse JSON
            data = json.loads(json_str)

            # Extract overall reasoning
            overall_reasoning = data.get("reasoning", "No reasoning provided")

            # Parse agent selections
            selected_agents = []
            agents_data = data.get("agents", [])

            for agent_data in agents_data:
                agent_id = agent_data.get("agent_id")
                relevance_score = agent_data.get("relevance_score", 0)
                reasoning = agent_data.get("reasoning", "No reasoning")
                matched_capabilities = agent_data.get("matched_capabilities", [])

                # Validate agent exists
                if agent_id not in agent_cards:
                    self.logger.warning(
                        "LLM selected unknown agent",
                        extra={
                            "agent_id": agent_id,
                            "available_agents": list(agent_cards.keys()),
                        },
                    )
                    continue

                # Apply relevance threshold
                if relevance_score < self.relevance_threshold:
                    self.logger.info(
                        "Filtered agent below threshold",
                        extra={
                            "agent_id": agent_id,
                            "relevance_score": relevance_score,
                            "threshold": self.relevance_threshold,
                        },
                    )
                    continue

                # Get agent name from card
                agent_card = agent_cards[agent_id]
                agent_name = agent_card.get("name", agent_id)

                # Create selection
                selection = AgentSelection(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    relevance_score=relevance_score,
                    reasoning=reasoning,
                    matched_capabilities=matched_capabilities,
                )

                selected_agents.append(selection)

            # Sort by relevance score (highest first)
            selected_agents.sort(key=lambda x: -x.relevance_score)

            return DecompositionResult(
                query=user_query,
                selected_agents=selected_agents,
                total_agents_analyzed=len(agent_cards),
                llm_reasoning=overall_reasoning,
            )

        except json.JSONDecodeError as e:
            self.logger.error(
                "Failed to parse LLM JSON response",
                extra={
                    "error": str(e),
                    "response_preview": llm_response[:200].replace(chr(10), " "),
                },
                exc_info=True,
            )
            raise RuntimeError(f"Invalid JSON response from LLM: {e}")

        except Exception as e:
            self.logger.error(
                "Failed to parse decomposition result",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise RuntimeError(f"Failed to parse decomposition result: {e}")
