#!/usr/bin/env python3
"""
Cloud Map Agent Discovery Module
Discovers A2A agents via AWS Cloud Map and fetches their agent cards
"""

import os

import boto3
import requests

from lib.logger import get_logger

logger = get_logger()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
CLOUDMAP_NAMESPACE = os.getenv("CLOUDMAP_NAMESPACE", "a2a-agents.local")


def discover_agent(service_name: str, namespace: str | None = None) -> dict:
    """
    Discover an agent by service name using AWS Cloud Map.

    Args:
        service_name: Name of the service to discover (e.g., 'market-analysis')
        namespace: Cloud Map namespace (defaults to CLOUDMAP_NAMESPACE env var)

    Returns:
        Dictionary containing:
        - base_url: Agent's base URL (http://IP:PORT)
        - agent_card: Parsed agent card from /.well-known/agent.json

    Raises:
        Exception: If agent cannot be discovered or contacted
    """
    namespace = namespace or CLOUDMAP_NAMESPACE

    logger.debug(f"Discovering agent '{service_name}' in namespace '{namespace}'...")

    try:
        # Create Cloud Map client
        servicediscovery = boto3.client("servicediscovery", region_name=AWS_REGION)

        # Discover instances
        response = servicediscovery.discover_instances(
            NamespaceName=namespace,
            ServiceName=service_name,
            MaxResults=1,
            HealthStatus="HEALTHY",
        )

        instances = response.get("Instances", [])
        if not instances:
            raise Exception(f"No healthy instances found for service '{service_name}'")

        # Get first instance attributes
        instance = instances[0]
        attributes = instance.get("Attributes", {})

        ip = attributes.get("AWS_INSTANCE_IPV4")
        port = attributes.get("AWS_INSTANCE_PORT", "8000")

        if not ip:
            raise Exception(f"No IP address found for service '{service_name}'")

        # Construct base URL
        base_url = f"http://{ip}:{port}"
        logger.debug(f"  Found instance at {base_url}")

        # Fetch agent card
        agent_card_url = f"{base_url}/.well-known/agent.json"
        logger.debug(f"  Fetching agent card from {agent_card_url}")

        card_response = requests.get(agent_card_url, timeout=5)
        card_response.raise_for_status()
        agent_card = card_response.json()

        logger.debug(f"  ✓ Agent discovered: {agent_card.get('name', 'Unknown')}")

        return {
            "base_url": base_url,
            "agent_card": agent_card,
            "instance_id": instance.get("InstanceId"),
            "namespace": namespace,
            "service_name": service_name,
        }

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch agent card from {base_url}: {e}")
    except Exception as e:
        raise Exception(f"Failed to discover agent '{service_name}': {e}")


def list_available_agents(namespace: str | None = None) -> list:
    """
    List all available agents in the Cloud Map namespace.

    Args:
        namespace: Cloud Map namespace (defaults to CLOUDMAP_NAMESPACE env var)

    Returns:
        List of service names available in the namespace
    """
    namespace = namespace or CLOUDMAP_NAMESPACE

    try:
        servicediscovery = boto3.client("servicediscovery", region_name=AWS_REGION)

        # Get namespace ID
        namespaces = servicediscovery.list_namespaces()
        namespace_id = None
        for ns in namespaces.get("Namespaces", []):
            if ns["Name"] == namespace:
                namespace_id = ns["Id"]
                break

        if not namespace_id:
            return []

        # List services in namespace
        services = servicediscovery.list_services(
            Filters=[
                {"Name": "NAMESPACE_ID", "Values": [namespace_id], "Condition": "EQ"}
            ]
        )

        return [s["Name"] for s in services.get("Services", [])]

    except Exception as e:
        logger.error(f"Warning: Failed to list agents: {e}")
        return []


if __name__ == "__main__":
    """Test discovery by discovering all available agents"""
    import sys

    logger.info("Available agents in namespace:")
    agents = list_available_agents()

    if not agents:
        logger.info("  No agents found")
        sys.exit(1)

    for agent_name in agents:
        logger.info(f"\n{agent_name}:")
        try:
            result = discover_agent(agent_name)
            logger.info(f"  Base URL: {result['base_url']}")
            logger.info(f"  Agent Name: {result['agent_card'].get('name')}")
            logger.info(
                f"  Capabilities: {len(result['agent_card'].get('capabilities', []))} tools"
            )
        except Exception as e:
            logger.error(f"  Error: {e}")
