#!/usr/bin/env python3
"""
Domain Configuration Loader

Loads and parses domain-specific configuration from YAML files.
Enables domain-agnostic agent framework to work with different domains
(travel, financial, e-commerce, etc.) without code changes.

Configuration Structure:
    config/domains/
        ├── travel.yaml      # Travel domain config
        ├── financial.yaml   # Financial domain config
        └── ecommerce.yaml   # E-commerce domain config

Example YAML:
    domain:
      name: travel
      description: Travel planning and recommendations

    agents:
      weather:
        class: WeatherAgent
        capabilities:
          - get_weather
          - get_forecast
        data_sources:
          - type: mock  # or "openweathermap"
            config:
              api_key: ${OPENWEATHER_API_KEY}
"""

import os
from typing import Any

from pydantic import BaseModel, Field
import yaml


class DataSourceConfig(BaseModel):
    """Configuration for external data sources (APIs, mock data, etc.)"""

    type: str = Field(..., description="Data source type (mock, api, database)")
    config: dict[str, Any] = Field(
        default_factory=dict, description="Source-specific configuration"
    )


class AgentConfig(BaseModel):
    """Configuration for a single agent within a domain"""

    class_name: str = Field(..., description="Python class name for the agent")
    description: str | None = Field(None, description="Agent description")
    capabilities: list[str] = Field(
        default_factory=list, description="List of capability IDs"
    )
    data_sources: list[DataSourceConfig] = Field(
        default_factory=list, description="External data sources"
    )
    config: dict[str, Any] = Field(
        default_factory=dict, description="Agent-specific configuration"
    )


class DomainConfig(BaseModel):
    """Top-level domain configuration"""

    name: str = Field(..., description="Domain name (e.g., travel, financial)")
    description: str = Field(..., description="Domain description")
    agents: dict[str, AgentConfig] = Field(
        default_factory=dict, description="Agent configurations"
    )
    shared_config: dict[str, Any] = Field(
        default_factory=dict, description="Shared configuration across all agents"
    )


def load_domain_config(domain_name: str, config_dir: str | None = None) -> DomainConfig:
    """
    Load domain configuration from YAML file.

    Args:
        domain_name: Name of the domain (e.g., "travel", "financial")
        config_dir: Optional custom config directory (defaults to config/domains/)

    Returns:
        DomainConfig object with parsed configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
        ValueError: If config structure is invalid

    Example:
        >>> config = load_domain_config("travel")
        >>> print(config.agents["weather"].capabilities)
        ['get_weather', 'get_forecast']
    """
    if config_dir is None:
        # Default to config/domains/ relative to project root
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        config_dir = os.path.join(project_root, "config", "domains")

    config_file = os.path.join(config_dir, f"{domain_name}.yaml")

    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Domain config not found: {config_file}")

    # Load YAML file
    with open(config_file) as f:
        raw_config = yaml.safe_load(f)

    # Environment variable substitution
    raw_config = _substitute_env_vars(raw_config)

    # Parse into DomainConfig model
    try:
        config = DomainConfig(**raw_config)
        return config
    except Exception as e:
        raise ValueError(f"Invalid domain config structure in {config_file}: {e}")


def _substitute_env_vars(obj: Any) -> Any:
    """
    Recursively substitute environment variables in config.

    Replaces ${VAR_NAME} with os.getenv("VAR_NAME", "").

    Args:
        obj: Config object (dict, list, or scalar)

    Returns:
        Object with environment variables substituted
    """
    if isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    elif isinstance(obj, str):
        # Replace ${VAR_NAME} with environment variable value
        import re

        def replacer(match):
            var_name = match.group(1)
            return os.getenv(var_name, "")

        return re.sub(r"\$\{([A-Za-z0-9_]+)\}", replacer, obj)
    else:
        return obj


def get_agent_config(domain_config: DomainConfig, agent_name: str) -> AgentConfig:
    """
    Get configuration for a specific agent.

    Args:
        domain_config: Domain configuration
        agent_name: Agent name (e.g., "weather", "events")

    Returns:
        AgentConfig for the specified agent

    Raises:
        KeyError: If agent not found in domain config
    """
    if agent_name not in domain_config.agents:
        available = ", ".join(domain_config.agents.keys())
        raise KeyError(
            f"Agent '{agent_name}' not found in domain '{domain_config.name}'. Available: {available}"
        )

    return domain_config.agents[agent_name]


def list_available_domains(config_dir: str | None = None) -> list[str]:
    """
    List all available domain configurations.

    Args:
        config_dir: Optional custom config directory

    Returns:
        List of domain names (e.g., ["travel", "financial"])
    """
    if config_dir is None:
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        config_dir = os.path.join(project_root, "config", "domains")

    if not os.path.exists(config_dir):
        return []

    domains = []
    for filename in os.listdir(config_dir):
        if filename.endswith(".yaml"):
            domain_name = filename[:-5]  # Remove .yaml extension
            domains.append(domain_name)

    return sorted(domains)
