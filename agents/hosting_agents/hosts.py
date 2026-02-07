import asyncio
import logging
import uuid
import json
import re
from typing import Any, Dict, List, Optional
from collections.abc import AsyncIterable

import httpx
from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    Message,
    Part,
    Role,
    TextPart,
    SendMessageRequest,
    MessageSendParams,
    MessageSendConfiguration,
    Task,
)
from a2a.utils import get_message_text
from google.adk.agents import Agent, LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from google.genai import types

logger = logging.getLogger(__name__)


class LLMRoutedHostAgent:
    """
    LLM-based routing orchestrator using A2A protocol.
    Converts static routing rules to dynamic LLM decisions.
    """

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    # Agent URLs (your 3 agents)
    POLICY_AGENT_URL = "http://localhost:8001"
    RESEARCH_AGENT_URL = "http://localhost:8002"
    PROVIDER_AGENT_URL = "http://localhost:8003"

    def __init__(self) -> None:
        self._agent = self._build_router_agent()
        self._user_id = "host_agent_user"
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
        self._agent_cards: dict[str, AgentCard] = {}

    async def _get_agent_card(self, agent_url: str) -> AgentCard | None:
        """Get and cache agent card."""
        if agent_url not in self._agent_cards:
            try:
                logger.info(f"Fetching agent card from {agent_url}")
                async with httpx.AsyncClient() as hc:
                    response = await hc.get(f"{agent_url}/.well-known/agent.json")
                    response.raise_for_status()
                    
                    agent_card = AgentCard(**response.json())
                    self._agent_cards[agent_url] = agent_card
                    logger.info(f"Cached agent card for {agent_url}: {agent_card.name}")
                    return agent_card
            except Exception as e:
                logger.error(f"Failed to get agent card from {agent_url}: {e}", exc_info=True)
                return None
        return self._agent_cards.get(agent_url)

    async def _call_agent_with_a2a(self, agent_url: str, query: str, context_id: str) -> str:
        """Call an agent using the A2A protocol."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as hc:
                client = await A2AClient.get_client_from_agent_card_url(
                    httpx_client=hc, base_url=agent_url
                )

                message = Message(
                    messageId=str(uuid.uuid4()),
                    contextId=context_id,
                    role=Role.user,
                    parts=[Part(root=TextPart(text=query))],
                )

                request = SendMessageRequest(
                    id=str(uuid.uuid4()),
                    params=MessageSendParams(
                        message=message,
                        configuration=MessageSendConfiguration(
                            acceptedOutputModes=["text/plain", "text"]
                        ),
                    ),
                )

                response = await client.send_message(request)

                if hasattr(response, "root"):
                    result = response.root.result
                else:
                    result = response.result if hasattr(response, "result") else response

                if isinstance(result, Task):
                    if result.artifacts:
                        texts = []
                        for artifact in result.artifacts:
                            for part in artifact.parts:
                                if hasattr(part, "root") and hasattr(part.root, "text"):
                                    texts.append(part.root.text)
                        return "\n".join(texts) if texts else "Task completed with no text response"
                    elif result.status and result.status.message:
                        return get_message_text(result.status.message)
                    else:
                        return f"Task {result.id} status: {result.status.state if result.status else 'unknown'}"
                elif isinstance(result, Message):
                    return get_message_text(result)
                else:
                    logger.warning(f"Unexpected response type: {type(result)}")
                    return "Received response but unable to extract text"

        except Exception as e:
            logger.error(f"Error calling agent at {agent_url}: {e}", exc_info=True)
            return f"Error communicating with agent: {str(e)}"

    # Individual agent call wrappers
    async def call_policy_agent(self, query: str, context_id: str) -> str:
        return await self._call_agent_with_a2a(self.POLICY_AGENT_URL, query, context_id)

    async def call_research_agent(self, query: str, context_id: str) -> str:
        return await self._call_agent_with_a2a(self.RESEARCH_AGENT_URL, query, context_id)

    async def call_provider_agent(self, query: str, context_id: str) -> str:
        return await self._call_agent_with_a2a(self.PROVIDER_AGENT_URL, query, context_id)

    async def call_agents_parallel(
        self, 
        policy_query: Optional[str], 
        research_query: Optional[str],
        provider_query: Optional[str],
        context_id: str
    ) -> dict[str, str]:
        """Call multiple agents in parallel based on LLM routing decision."""
        logger.info("Executing parallel agent calls")
        
        tasks = []
        agent_names = []
        
        if policy_query:
            tasks.append(asyncio.create_task(self.call_policy_agent(policy_query, context_id)))
            agent_names.append("policy")
        if research_query:
            tasks.append(asyncio.create_task(self.call_research_agent(research_query, context_id)))
            agent_names.append("research")
        if provider_query:
            tasks.append(asyncio.create_task(self.call_provider_agent(provider_query, context_id)))
            agent_names.append("provider")
        
        if not tasks:
            return {}
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        responses = {}
        for name, result in zip(agent_names, results):
            if isinstance(result, Exception):
                responses[name] = f"Error from {name} agent: {str(result)}"
            else:
                responses[name] = result
        
        return responses

    async def call_agents_sequential(
        self,
        execution_plan: List[Dict],
        original_query: str,
        context_id: str
    ) -> dict[str, str]:
        """Execute agents in sequence with context passing."""
        logger.info(f"Executing sequential plan: {[step['agent'] for step in execution_plan]}")
        
        responses = {}
        accumulated_context = {}
        
        for step in execution_plan:
            agent_name = step["agent"]
            query_template = step["query"]
            
            # Format query with accumulated context
            query = query_template.format(
                original_query=original_query,
                context=json.dumps(accumulated_context),
                **accumulated_context
            )
            
            logger.info(f"Step: {agent_name} - Query: {query[:100]}...")
            
            if agent_name == "policy":
                response = await self.call_policy_agent(query, context_id)
            elif agent_name == "research":
                response = await self.call_research_agent(query, context_id)
            elif agent_name == "provider":
                response = await self.call_provider_agent(query, context_id)
            else:
                response = f"Unknown agent: {agent_name}"
            
            responses[agent_name] = response
            accumulated_context[f"{agent_name}_result"] = response[:500]  # Truncate for context
            
            # Check for early termination (e.g., policy rejection)
            if step.get("stop_if") and step["stop_if"] in response:
                logger.info(f"Stopping sequence due to condition: {step['stop_if']}")
                break
        
        return responses

    async def get_agent_status(self) -> str:
        """Return online/offline status for remote agents."""
        lines = ["Agent Status:"]

        for name, url in [
            ("Policy Agent", self.POLICY_AGENT_URL),
            ("Research Agent", self.RESEARCH_AGENT_URL),
            ("Provider Agent", self.PROVIDER_AGENT_URL),
        ]:
            card = await self._get_agent_card(url)
            if card:
                lines.append(f"✅ {name}: Online - {card.description}")
            else:
                lines.append(f"❌ {name}: Offline")

        return "\n".join(lines)

    def _build_router_agent(self) -> LlmAgent:
        """
        LLM-based router that replaces static if/else rules.
        Returns structured JSON routing decisions.
        """
        return LlmAgent(
            name="llm_router_agent",
            model="gemini-2.0-flash",
            description="Intelligent router that analyzes queries and determines optimal agent orchestration",
            instruction=
"""
                You are an intelligent healthcare query router. Analyze the user's request and determine the optimal agent execution strategy.
AVAILABLE AGENTS:
1. **PolicyAgent**: Insurance coverage, compliance validation, regulatory checks, prior authorization, network status
2. **ResearchAgent**: Medical research, symptom analysis, treatment options, drug information, clinical guidelines  
3. **ProviderAgent**: Healthcare provider search, appointment scheduling, facility locations, specialist referrals

ROUTING PATTERNS:
- "policy_only": Compliance/insurance questions only
- "research_only": General medical information only
- "provider_only": Provider lookup with known parameters
- "policy_then_provider": Validate coverage then find providers
- "research_then_provider": Get medical info then find specialists
- "research_then_policy": Assess condition then check coverage
- "policy_then_research_then_provider": Full workflow (compliance first)
- "research_then_policy_then_provider": Full workflow (triage first)
- "parallel_policy_research": Check coverage and research simultaneously
- "all_parallel": Call all three agents simultaneously

DECISION GUIDELINES:
- If query mentions "insurance", "coverage", "copay", "deductible" → Include PolicyAgent
- If query mentions "symptoms", "treatment", "medication", "diagnosis" → Include ResearchAgent
- If query mentions "doctor", "appointment", "specialist", "clinic" → Include ProviderAgent
- If query mentions "emergency", "urgent", "chest pain", "severe" → ResearchAgent FIRST for triage
- If query asks about both coverage AND providers → PolicyAgent before ProviderAgent
- If query is ambiguous or complex → Use sequential execution with context passing

OUTPUT FORMAT (JSON only):
```json
{
    "routing_pattern": "pattern_name",
    "execution_mode": "sequential|parallel",
    "agents": ["agent1", "agent2", "agent3"],
    "execution_plan": [
        {
            "agent": "agent_name",
            "query": "specific query with {original_query} and {context} placeholders",
            "stop_if": "optional string that stops sequence if found in response"
        }
    ],
    "parallel_queries": {
        "agent_name": "query for this agent (only if execution_mode is parallel)"
    },
    "synthesis_strategy": "merge|prioritize_research|prioritize_policy|concatenate",
    "reasoning": "brief explanation of routing decision"""
        )
