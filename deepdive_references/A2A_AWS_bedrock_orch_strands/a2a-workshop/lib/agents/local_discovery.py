#!/usr/bin/env python3
"""
Local Service Discovery - CloudMap Emulator for Testing

Provides a file-based service discovery mechanism for local development.
Mimics CloudMap API but uses a local JSON file instead.

Usage:
    # In your agent:
    from agents.common.local_discovery import register_local_service, discover_local_agent
from lib.logger import get_logger

    # Register

logger = get_logger()

    register_local_service("weather-agent", "http://localhost:8001")

    # Discover
    info = discover_local_agent("weather-agent")
    # Returns: {'base_url': 'http://localhost:8001', 'agent_card': {...}}
"""

import json
from pathlib import Path

import httpx

# Local registry file
REGISTRY_FILE = Path(__file__).parent.parent.parent / ".local_agents_registry.json"


def _load_registry() -> dict[str, dict]:
    """Load local agent registry from file."""
    if not REGISTRY_FILE.exists():
        return {}

    try:
        with open(REGISTRY_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading registry: {e}")
        return {}


def _save_registry(registry: dict[str, dict]):
    """Save local agent registry to file."""
    try:
        with open(REGISTRY_FILE, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving registry: {e}")


def register_local_service(service_name: str, base_url: str):
    """
    Register a service in the local registry.

    Args:
        service_name: Service name (e.g., "weather-agent")
        base_url: Base URL (e.g., "http://localhost:8001")
    """
    registry = _load_registry()
    registry[service_name] = {"base_url": base_url, "registered_at": str(Path.cwd())}
    _save_registry(registry)
    logger.info(f"[local-discovery] Registered {service_name} at {base_url}")


def list_local_agents() -> list[str]:
    """
    List all registered services in local registry.

    Returns:
        List of service names
    """
    registry = _load_registry()
    return list(registry.keys())


def discover_local_agent(service_name: str) -> dict:
    """
    Discover an agent from local registry.

    Mimics the CloudMap discover_agent API but uses local file.
    Fetches the agent card from the service's /.well-known/agent.json endpoint.

    Args:
        service_name: Service name to discover

    Returns:
        Dict with 'base_url' and 'agent_card'

    Raises:
        Exception if service not found or unreachable
    """
    registry = _load_registry()

    if service_name not in registry:
        raise Exception(
            f"Service '{service_name}' not found in local registry. Available: {list(registry.keys())}"
        )

    base_url = registry[service_name]["base_url"]

    # Fetch agent card
    try:
        client = httpx.Client(timeout=5.0)
        response = client.get(f"{base_url}/.well-known/agent.json")
        response.raise_for_status()
        agent_card = response.json()

        return {"base_url": base_url, "agent_card": agent_card}
    except Exception as e:
        raise Exception(f"Failed to fetch agent card from {base_url}: {e}")


def clear_local_registry():
    """Clear the local registry (useful for testing)."""
    if REGISTRY_FILE.exists():
        REGISTRY_FILE.unlink()
    logger.info("[local-discovery] Registry cleared")
