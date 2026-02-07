#!/usr/bin/env python3
"""
Agent Registry - Local Agent Discovery for Development

Provides agent discovery via HTTP polling of agent card endpoints. This module
implements the A2A (Agent-to-Agent) agent discovery protocol for local development
environments where agents run on localhost with known ports.

Key Features:
    - Async concurrent fetching of agent cards
    - Graceful failure per agent (one failure doesn't block others)
    - Skill-to-endpoint routing table generation
    - Configurable via environment variables
    - A2A specification compliant

Agent Card Format (A2A Spec):
    Agent cards are JSON documents served at /.well-known/agent.json:
    {
        "name": "Weather Agent",
        "description": "Provides weather forecasts and current conditions",
        "url": "http://localhost:8000/message/send",
        "skills": [
            {
                "id": "get-weather",
                "name": "Get Weather",
                "description": "Get current weather for a location"
            }
        ]
    }

Discovery Process:
    1. Fetch agent cards from configured URLs concurrently
    2. Parse skills from each agent card
    3. Build routing table: skill_id -> agent_url
    4. Return routing table to orchestrator

Configuration:
    All settings are configured via core.config module:

    - agent_discovery_urls: List of agent card URLs
    - agent_discovery_timeout: Timeout per agent (seconds)

    Override via environment variables:
        export CORE_AGENT_DISCOVERY_URLS='["http://agent1:8000/.well-known/agent.json"]'
        export CORE_AGENT_DISCOVERY_TIMEOUT=5

Example Usage:
    Basic discovery:
        >>> import asyncio
        >>> from core import discover_agent_cards
        >>>
        >>> routing_table = asyncio.run(discover_agent_cards())
        >>> print(routing_table)
        {
            'get-weather': 'http://localhost:8000/message/send',
            'search-events': 'http://localhost:8001/message/send',
            'find-restaurants': 'http://localhost:8002/message/send'
        }

    Using routing table:
        >>> skill_id = "get-weather"
        >>> endpoint = routing_table.get(skill_id)
        >>> if endpoint:
        ...     # Send task to agent
        ...     client = AgentHTTPClient()
        ...     response = client.send_task(endpoint, task, skill_id)

    With custom configuration:
        >>> from core import config
        >>> config.agent_discovery_urls = ["http://custom:9000/.well-known/agent.json"]
        >>> routing_table = asyncio.run(discover_agent_cards())

Error Handling:
    - Individual agent failures don't block other agents
    - Network errors are logged but don't raise exceptions
    - Empty routing table returned if all agents fail
    - Timeout per agent prevents hanging on slow/dead agents

Production Considerations:
    This module is designed for LOCAL DEVELOPMENT only. For production:
    - Use service discovery (Consul, etcd, AWS ECS Service Discovery)
    - Implement health checks and circuit breakers
    - Add caching to reduce discovery latency
    - Consider agent card validation and versioning

Limitations:
    - No caching (discovery runs on every call)
    - No health checks (can't detect dead agents without trying)
    - No retry logic (single attempt per agent)
    - No agent versioning or compatibility checks
    - Assumes agents are running when discovery executes

See Also:
    - A2A Specification: Agent discovery protocol
    - core.config: Configuration module
    - agent_http_client.py: Sending tasks to discovered agents
"""

import asyncio

import aiohttp

from lib.config import config
from lib.logger import get_logger

# Initialize logger with component context
logger = get_logger(context={"component": "AgentRegistry"})


async def fetch_agent_card(session: aiohttp.ClientSession, url: str) -> dict:
    """
    Fetch a single agent card from the given URL.

    Async function that fetches an agent card JSON document from an HTTP endpoint.
    Implements graceful failure - exceptions are caught and logged, empty dict
    returned on error.

    Args:
        session: aiohttp ClientSession for connection pooling
        url: Full URL to agent card endpoint (e.g., http://localhost:8000/.well-known/agent.json)

    Returns:
        dict: Agent card JSON document if successful, empty dict on failure
              Expected agent card structure:
              {
                  "name": "Agent Name",
                  "description": "Agent description",
                  "url": "http://agent-endpoint/message/send",
                  "skills": [
                      {
                          "id": "skill-id",
                          "name": "Skill Name",
                          "description": "What the skill does"
                      }
                  ]
              }

    Error Handling:
        - Network errors: Logged, returns {}
        - Timeout errors: Logged, returns {}
        - HTTP errors (4xx, 5xx): Logged, returns {}
        - JSON parse errors: Logged, returns {}
        - Never raises exceptions (graceful failure)

    Timeout:
        Uses config.agent_discovery_timeout (default: 3 seconds)
        Prevents hanging on slow or dead agents

    Examples:
        >>> async with aiohttp.ClientSession() as session:
        ...     card = await fetch_agent_card(session, "http://localhost:8000/.well-known/agent.json")
        ...     if card:
        ...         print(f"Found agent: {card['name']}")
        ...     else:
        ...         print("Agent not available")
    """
    try:
        async with session.get(url, timeout=config.agent_discovery_timeout) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                logger.warning(
                    f"Agent card fetch failed: url={url} status_code={resp.status}"
                )
    except Exception as e:
        logger.warning(f"Failed to fetch agent card: url={url} error={e!s}")
    return {}


async def discover_agent_cards() -> dict[str, str]:
    """
    Discover agents and build skill-to-endpoint routing table.

    Fetches agent cards from all configured URLs concurrently, parses their
    skill definitions, and builds a routing table mapping skill IDs to agent
    endpoints for task delegation.

    Returns:
        Dict[str, str]: Routing table mapping skill_id -> agent_endpoint
                       Example:
                       {
                           'get-weather': 'http://localhost:8000/message/send',
                           'search-events': 'http://localhost:8001/message/send'
                       }

    Discovery URLs:
        Reads from config.agent_discovery_urls (default: localhost:8000, localhost:8001)
        Override via CORE_AGENT_DISCOVERY_URLS environment variable

    Concurrent Execution:
        All agent cards are fetched concurrently using asyncio.gather().
        This minimizes discovery latency when multiple agents are running.

    Failure Handling:
        - Individual agent failures don't block other agents
        - If all agents fail, returns empty routing table {}
        - Duplicate skill IDs: Last agent wins (skill_id overwrites previous)

    Skill Mapping:
        For each agent card, extracts:
        - skills[].id: Unique skill identifier
        - url: Agent's task endpoint (e.g., /message/send)

        Maps skill_id -> agent_url for routing:
            routing_table[skill_id] = agent_url

    Examples:
        Discover all agents:
            >>> import asyncio
            >>> routing_table = asyncio.run(discover_agent_cards())
            >>> print(routing_table)
            {'get-weather': 'http://localhost:8000/message/send'}

        Use routing table for task delegation:
            >>> skill_id = "get-weather"
            >>> if skill_id in routing_table:
            ...     endpoint = routing_table[skill_id]
            ...     client = AgentHTTPClient()
            ...     response = client.send_task(endpoint, task, skill_id)

        With custom URLs:
            >>> from core import config
            >>> config.agent_discovery_urls = ["http://agent1:9000/.well-known/agent.json"]
            >>> routing_table = asyncio.run(discover_agent_cards())

    Performance:
        - Typical discovery time: 50-200ms for 2-5 agents
        - Parallel fetching: O(slowest_agent) not O(sum of all agents)
        - No caching: Runs full discovery on every call

    Limitations:
        - No caching: Repeated calls re-fetch all agent cards
        - No health checks: Can't detect dead agents proactively
        - No versioning: Skill ID conflicts handled by last-agent-wins
        - Local development only: Not suitable for production

    Production Recommendations:
        For production use, consider:
        1. Service discovery (Consul, etcd, K8s Service Discovery)
        2. Agent card caching with TTL
        3. Health check integration
        4. Agent versioning and compatibility checks
        5. Circuit breakers for dead agents

    See Also:
        - fetch_agent_card(): Fetches individual agent cards
        - core.config: Configuration for discovery URLs and timeouts
        - agent_http_client.py: Sending tasks to discovered agents
    """
    routing_table = {}

    async with aiohttp.ClientSession() as session:
        # Create fetch tasks for all agent URLs concurrently
        tasks = []
        for url in config.agent_discovery_urls:
            tasks.append(fetch_agent_card(session, url))

        # Fetch all agent cards in parallel (non-blocking)
        results = await asyncio.gather(*tasks)

        # Build routing table from agent cards
        for card in results:
            if card and "skills" in card and "url" in card:
                # Map each skill ID to agent endpoint
                for skill in card["skills"]:
                    skill_id = skill.get("id")
                    if skill_id:
                        # Note: If duplicate skill_id, last agent wins
                        routing_table[skill_id] = card["url"]

    return routing_table


__all__ = ["discover_agent_cards", "fetch_agent_card"]
