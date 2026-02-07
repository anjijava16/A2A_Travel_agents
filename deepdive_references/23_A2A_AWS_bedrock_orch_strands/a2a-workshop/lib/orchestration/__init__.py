"""
Core Module - Domain-Agnostic Orchestration Infrastructure

Provides reusable components for multi-agent orchestration:
- Configuration management (config.py)
- Structured logging (logger.py)
- Agent discovery (agent_registry.py)
- HTTP communication (agent_http_client.py)
- Query decomposition (query_decomposer.py)
- Response synthesis (generic_synthesizer.py)

See docs/adr/001-http-over-eventbridge.md for architectural decisions.
"""

from lib.agents.agent_http_client import AgentHTTPClient, send_task_async
from lib.agents.agent_registry import discover_agent_cards
from lib.config import config
from lib.logger import get_logger

__all__ = [
    "AgentHTTPClient",
    "config",
    "discover_agent_cards",
    "get_logger",
    "send_task_async",
]
