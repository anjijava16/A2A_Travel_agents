#!/usr/bin/env python3
"""
Core Module Configuration

Centralized configuration management for the core orchestration module using
Pydantic Settings for type-safe, validated configuration with .env support.

All settings can be overridden via environment variables with the CORE_ prefix
(e.g., CORE_AWS_REGION=us-west-2) or via a .env file in the project root.

Configuration Groups:
    - AWS Configuration: Bedrock model and region settings
    - Agent Discovery: URLs and timeouts for agent card discovery
    - Query Decomposition: LLM parameters for agent selection
    - Response Synthesis: LLM parameters for response combination
    - Agent Communication: HTTP timeouts for agent requests

Example Usage:
    from lib.config import config
from lib.logger import get_logger

    # Access configuration values

logger = get_logger()

    logger.info(config.bedrock_model_id)  # Model ID for LLM calls
    logger.info(config.agent_discovery_urls)  # List of agent card URLs

    # Override via environment variables
    export CORE_AWS_REGION=us-west-2
    export CORE_AGENT_DISCOVERY_URLS='["http://agent1:8000/.well-known/agent.json"]'

    # Override via .env file
    echo "CORE_AWS_REGION=us-west-2" >> .env
    echo "CORE_QUERY_THRESHOLD=80" >> .env
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class CoreConfig(BaseSettings):
    """
    Core module configuration with environment variable support.

    All settings can be overridden via environment variables with the CORE_
    prefix. Settings can also be loaded from a .env file.

    Attributes:
        aws_region: AWS region for Bedrock API calls
        bedrock_model_id: Claude Sonnet 4 model ID for LLM operations

        agent_discovery_urls: List of agent card URLs for discovery
        agent_discovery_timeout: Timeout (seconds) for agent card fetch

        query_threshold: Minimum relevance score for agent selection (0-100)
        decomposer_max_tokens: Max tokens for query decomposition LLM

        synthesizer_max_tokens: Max tokens for response synthesis LLM

        agent_timeout: Timeout (seconds) for agent HTTP requests
    """

    # =================================================================
    # AWS Configuration
    # =================================================================

    aws_region: str = Field(
        default="us-east-1", description="AWS region for Bedrock API calls"
    )

    bedrock_model_id: str = Field(
        default="us.anthropic.claude-sonnet-4-20250514-v1:0",
        description="Claude Sonnet 4 cross-region inference profile for Converse/ConverseStream",
    )

    token_counter_model_id: str = Field(
        default="anthropic.claude-sonnet-4-20250514-v1:0",
        description="Foundation model ID for CountTokens API (without us. prefix)",
    )

    # =================================================================
    # Agent Discovery Configuration
    # =================================================================

    agent_discovery_urls: list[str] = Field(
        default=[
            "http://localhost:8000/.well-known/agent.json",
            "http://localhost:8001/.well-known/agent.json",
        ],
        description="List of agent card URLs to discover agents from",
    )

    agent_discovery_timeout: int = Field(
        default=3,
        ge=1,
        le=30,
        description="Timeout in seconds for fetching agent cards (1-30)",
    )

    # =================================================================
    # Query Decomposition Configuration
    # =================================================================

    query_threshold: int = Field(
        default=70,
        ge=0,
        le=100,
        description="Minimum relevance score (0-100) for agent selection",
    )

    decomposer_max_tokens: int = Field(
        default=1500,
        ge=100,
        le=4096,
        description="Maximum tokens for query decomposition LLM response",
    )

    # =================================================================
    # Response Synthesis Configuration
    # =================================================================

    synthesizer_max_tokens: int = Field(
        default=800,
        ge=100,
        le=4096,
        description="Maximum tokens for response synthesis LLM response",
    )

    # =================================================================
    # Agent Communication Configuration
    # =================================================================

    agent_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout in seconds for agent HTTP requests (1-300)",
    )

    # =================================================================
    # Pydantic Settings Configuration
    # =================================================================

    class Config:
        """Pydantic settings configuration."""

        # Environment variable prefix
        env_prefix = "CORE_"

        # Load from .env file if present
        env_file = ".env"
        env_file_encoding = "utf-8"

        # Allow extra fields (for forward compatibility)
        extra = "ignore"

        # Case sensitive environment variables
        case_sensitive = False

    # =================================================================
    # Validators
    # =================================================================

    @field_validator("agent_discovery_urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        """
        Validate agent discovery URLs.

        Ensures URLs are non-empty strings and start with http:// or https://.

        Args:
            v: List of URLs to validate

        Returns:
            Validated list of URLs

        Raises:
            ValueError: If any URL is invalid
        """
        if not v:
            raise ValueError("agent_discovery_urls cannot be empty")

        for url in v:
            if not url or not isinstance(url, str):
                raise ValueError(f"Invalid URL: {url}")

            if not url.startswith(("http://", "https://")):
                raise ValueError(f"URL must start with http:// or https://: {url}")

        return v

    @field_validator("bedrock_model_id")
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        """
        Validate Bedrock model ID format.

        Args:
            v: Model ID to validate

        Returns:
            Validated model ID

        Raises:
            ValueError: If model ID is invalid
        """
        if not v or not isinstance(v, str):
            raise ValueError("bedrock_model_id must be a non-empty string")

        # Claude model IDs typically contain "anthropic" or "claude"
        if "anthropic" not in v.lower() and "claude" not in v.lower():
            # Warning, but allow (could be valid custom model)
            import warnings

            warnings.warn(
                f"Model ID '{v}' doesn't appear to be a Claude model. "
                "Ensure this is intentional."
            )

        return v


# =================================================================
# Global Configuration Instance
# =================================================================

# Create global config instance that will be imported by other modules
config = CoreConfig()


# =================================================================
# Configuration Utilities
# =================================================================


def get_config() -> CoreConfig:
    """
    Get the global configuration instance.

    Returns:
        Global CoreConfig instance

    Example:
        from lib.config import get_config

        config = get_config()
        logger.info(config.aws_region)
    """
    return config


def reload_config() -> CoreConfig:
    """
    Reload configuration from environment variables and .env file.

    Useful for testing or when environment changes during runtime.

    Returns:
        New CoreConfig instance with reloaded values

    Example:
        from lib.config import reload_config

        # Change environment
        os.environ['CORE_AWS_REGION'] = 'us-west-2'

        # Reload config
        config = reload_config()
        logger.info(config.aws_region)  # us-west-2
    """
    global config
    config = CoreConfig()
    return config


def print_config() -> None:
    """
    Print current configuration in human-readable format.

    Useful for debugging and verifying configuration values.

    Example:
        from lib.config import print_config

        print_config()
    """
    logger.info("=" * 70)
    logger.info("CORE MODULE CONFIGURATION")
    logger.info("=" * 70)

    logger.info("\nAWS Configuration:")
    logger.info(f"  Region:           {config.aws_region}")
    logger.info(f"  Bedrock Model ID: {config.bedrock_model_id}")

    logger.info("\nAgent Discovery:")
    logger.info(f"  URLs:             {len(config.agent_discovery_urls)} configured")
    for i, url in enumerate(config.agent_discovery_urls, 1):
        logger.info(f"    {i}. {url}")
    logger.info(f"  Timeout:          {config.agent_discovery_timeout}s")

    logger.info("\nQuery Decomposition:")
    logger.info(f"  Threshold:        {config.query_threshold}/100")
    logger.info(f"  Max Tokens:       {config.decomposer_max_tokens}")

    logger.info("\nResponse Synthesis:")
    logger.info(f"  Max Tokens:       {config.synthesizer_max_tokens}")

    logger.info("\nAgent Communication:")
    logger.info(f"  Timeout:          {config.agent_timeout}s")

    logger.info("=" * 70)


# =================================================================
# Module-level docstring and exports
# =================================================================

__all__ = [
    "CoreConfig",
    "config",
    "get_config",
    "print_config",
    "reload_config",
]
