"""
Base Agent Framework

Provides domain-agnostic abstractions for building A2A agents.

Includes both traditional (BaseAgent) and agentic (AgenticBaseAgent) implementations.
"""

from .agent_interface import AgentCapability, BaseAgent
from .agentic_base import AgenticBaseAgent, create_agentic_agent
from .config_loader import DomainConfig, load_domain_config

__all__ = [
    "AgentCapability",
    "BaseAgent",
    "AgenticBaseAgent",
    "create_agentic_agent",
    "DomainConfig",
    "load_domain_config",
]
