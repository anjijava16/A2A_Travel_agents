#!/usr/bin/env python3
"""
Agentic Base Agent - Foundation for Truly Intelligent Agents

This module provides a base class for creating agentic agents that use
Strands Agent framework for LLM-powered reasoning.

Key Features:
- Strands Agent integration with BedrockModel
- Tool definition framework with validation
- System prompt generation
- A2A protocol compatibility
- Structured data extraction from LLM responses

Usage:
    class MyAgenticAgent(AgenticBaseAgent):
        def _define_agent_tools(self):
            @tool(name="my_tool", description="Does something useful")
            def my_tool(param: str) -> dict:
                return {"result": param}

            return [my_tool]

        def _get_agent_system_prompt(self) -> str:
            return "You are an intelligent agent..."

        def _extract_result_data(self, response, **kwargs) -> dict:
            # Extract structured data from LLM response
            return {"data": "extracted"}

Tool Definition Guidelines:
==========================

Tools are the primary way your agent interacts with data and services.
Each tool is a Python function decorated with @tool that the LLM can discover
and invoke based on the user's query.

1. Tool Decorator Pattern:
   -----------------------
   Use the @tool decorator from Strands to define tools:

   @tool(
       name="tool_name",
       description="Clear description of what this tool does and when to use it"
   )
   def tool_function(param1: str, param2: int = 10) -> dict:
       '''Detailed docstring explaining the tool.'''
       # Implementation
       return {"result": "data"}

2. Tool Naming:
   ------------
   - Use descriptive, action-oriented names (get_weather, search_restaurants)
   - Use snake_case for function names
   - Keep names concise but clear (prefer "get_forecast" over "get_weather_forecast_data")

3. Tool Descriptions:
   ------------------
   - Write clear, concise descriptions (1-2 sentences)
   - Explain WHAT the tool does and WHEN to use it
   - Include key parameters in the description
   - Example: "Get weather forecast for a location. Use when user asks about weather conditions."

4. Parameter Types:
   ----------------
   - Always use type hints for all parameters
   - Support common types: str, int, float, bool, list, dict
   - Provide default values for optional parameters
   - Example: def search(query: str, limit: int = 10, include_details: bool = False)

5. Return Values:
   --------------
   - Always return structured data (dict or list)
   - Never return primitives (str, int, bool) directly
   - Include metadata in returns (timestamp, status, etc.)
   - Example return: {"results": [...], "count": 5, "timestamp": "2024-01-01T00:00:00Z"}

6. Error Handling:
   ---------------
   - Handle errors gracefully within tools
   - Return error information in the result dict
   - Don't raise exceptions unless critical
   - Example:
     try:
         result = perform_operation()
         return {"success": True, "result": result}
     except Exception as e:
         return {"success": False, "error": str(e)}

7. Accessing Agent Resources:
   ---------------------------
   - Tools have access to 'self' (the agent instance)
   - Use self.logger for logging
   - Use self.config for configuration
   - Use self.mock_factory or other agent resources
   - Example:
     def my_tool(self, query: str) -> dict:
         self.logger.debug(f"Tool called with query: {query}")
         data = self.mock_factory.get_data(query)
         return {"data": data}

8. Tool Design Best Practices:
   ---------------------------
   - Single Responsibility: Each tool does ONE thing well
   - Keep tools focused and composable
   - Avoid tools that do too much (split into multiple tools)
   - Make tools reusable across different queries
   - Document expected behavior in docstrings

9. Common Tool Patterns:
   ---------------------

   a) Data Retrieval Tool:
      @tool(name="get_data", description="Retrieve data by ID")
      def get_data(self, data_id: str) -> dict:
          '''Get data from the data source.'''
          data = self.data_source.get(data_id)
          return {
              "data": data,
              "timestamp": datetime.now(UTC).isoformat()
          }

   b) Search Tool:
      @tool(name="search", description="Search for items matching query")
      def search(self, query: str, limit: int = 10) -> dict:
          '''Search for items.'''
          results = self.data_source.search(query, limit)
          return {
              "results": results,
              "count": len(results),
              "query": query
          }

   c) Analysis Tool:
      @tool(name="analyze", description="Analyze data and provide insights")
      def analyze(self, data: dict) -> dict:
          '''Analyze data and return insights.'''
          insights = self._perform_analysis(data)
          return {
              "insights": insights,
              "confidence": 0.95,
              "analyzed_at": datetime.now(UTC).isoformat()
          }

   d) Filter Tool:
      @tool(name="filter_items", description="Filter items by criteria")
      def filter_items(self, items: list, criteria: str) -> dict:
          '''Filter items based on criteria.'''
          filtered = [item for item in items if self._matches(item, criteria)]
          return {
              "filtered_items": filtered,
              "original_count": len(items),
              "filtered_count": len(filtered)
          }

10. Tool Validation:
    ----------------
    The framework automatically validates:
    - Tool list is actually a list
    - Each tool is callable
    - Tool has required attributes (name, description)
    - Tool parameters have type hints
    - Tool return type is specified

    Validation errors are logged and will prevent agent initialization.

11. Tool Registration and Invocation Logging:
    -----------------------------------------
    The framework automatically logs:
    - Number of tools registered during initialization
    - Tool names and descriptions
    - Tool calls made by the LLM during execution
    - Tool execution results and errors
    - Tool execution time (for performance monitoring)

Example Complete Tool Definition:
=================================

from strands import tool
from datetime import datetime, UTC

class MyAgenticAgent(AgenticBaseAgent):
    def _define_agent_tools(self):
        @tool(
            name="get_weather_forecast",
            description="Get weather forecast for a location. Use when user asks about weather."
        )
        def get_weather_forecast(location: str, days: int = 3) -> dict:
            '''
            Get weather forecast for the specified location.

            Args:
                location: City name or location identifier
                days: Number of days to forecast (1-7)

            Returns:
                Dictionary with forecast data including temperature, conditions, etc.
            '''
            try:
                # Access agent resources
                self.logger.debug(f"Getting forecast for {location}, {days} days")

                # Get data
                forecast_data = self.mock_factory.get_weather(location)

                # Return structured data
                return {
                    "success": True,
                    "location": location,
                    "forecast": forecast_data[:days],
                    "timestamp": datetime.now(UTC).isoformat()
                }
            except Exception as e:
                self.logger.error(f"Forecast failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "location": location
                }

        @tool(
            name="analyze_weather_for_activities",
            description="Analyze weather to recommend indoor/outdoor activities"
        )
        def analyze_weather_for_activities(
            precipitation_chance: float,
            condition: str
        ) -> dict:
            '''
            Analyze weather conditions to recommend activities.

            Args:
                precipitation_chance: Chance of precipitation (0-100)
                condition: Weather condition (sunny, cloudy, rainy, etc.)

            Returns:
                Dictionary with activity recommendations
            '''
            indoor_recommended = precipitation_chance > 60 or condition == "rainy"

            return {
                "indoor_recommended": indoor_recommended,
                "outdoor_recommended": not indoor_recommended,
                "reasoning": f"With {precipitation_chance}% precipitation and {condition} conditions",
                "activity_suggestions": [
                    "Visit museums" if indoor_recommended else "Go hiking",
                    "Indoor dining" if indoor_recommended else "Outdoor dining"
                ]
            }

        return [get_weather_forecast, analyze_weather_for_activities]
"""

from abc import abstractmethod
from datetime import UTC, datetime
from typing import Any

from a2a.types import Task
from strands import Agent as StrandsAgent
from strands.models import BedrockModel

from .agent_interface import BaseAgent

# ============================================================================
# System Prompt Template
# ============================================================================

SYSTEM_PROMPT_TEMPLATE = """# {agent_name} - {primary_purpose}

You are a {role} agent specializing in {domain}. Your job is to {purpose}.

## Your Capabilities

You have access to these tools:

{tools_section}

## How to Handle Queries

{query_handling}

## Response Format

Structure your responses like this:
{response_format}

## Examples

{examples}

## Important Guidelines

{guidelines}
"""


def create_system_prompt_from_template(
    agent_name: str,
    primary_purpose: str,
    role: str,
    domain: str,
    purpose: str,
    tools_descriptions: list[dict[str, str]],
    query_handling: str,
    response_format: str,
    examples: list[dict[str, str]],
    guidelines: list[str],
) -> str:
    """
        Create a system prompt from the standard template.

        This helper function makes it easy to create well-structured system prompts
        that follow best practices.

        Args:
            agent_name: Name of the agent (e.g., "Weather Agent")
            primary_purpose: One-line description of primary purpose
            role: Agent's role (e.g., "weather information")
            domain: Domain of expertise (e.g., "weather forecasting")
            purpose: Detailed purpose description
            tools_descriptions: List of dicts with 'name', 'description', 'use_when', 'parameters', 'returns'
            query_handling: Multi-line string describing how to handle different query types
            response_format: Multi-line string describing response structure
            examples: List of dicts with 'query' and 'approach'
            guidelines: List of guideline strings

        Returns:
            Formatted system prompt string

        Example:
            prompt = create_system_prompt_from_template(
                agent_name="Weather Agent",
                primary_purpose="Weather Information and Activity Recommendations",
                role="weather information",
                domain="weather forecasting and activity planning",
                purpose="help users plan their activities based on weather conditions",
                tools_descriptions=[
                    {
                        "name": "get_weather_forecast",
                        "description": "Get weather forecast for a location",
                        "use_when": "User asks about weather, temperature, or conditions",
                        "parameters": "location (str), days (int, default 3)",
                        "returns": "Forecast data with temperature, conditions, precipitation"
                    }
                ],
                query_handling=\"\"\"
    When a user asks about weather:
    1. Call get_weather_forecast with their location
    2. Extract key information
    3. Provide a clear summary
                \"\"\",
                response_format=\"\"\"
    - Weather Summary: Current conditions and forecast
    - Activity Recommendations: Specific suggestions
                \"\"\",
                examples=[
                    {
                        "query": "What's the weather in Seattle?",
                        "approach": "Call get_weather_forecast('Seattle', 3) and summarize"
                    }
                ],
                guidelines=[
                    "Always provide specific, actionable information",
                    "Never make up weather data - only use tool results"
                ]
            )
    """
    # Format tools section
    tools_lines = []
    for i, tool in enumerate(tools_descriptions, 1):
        tool_text = f"{i}. **{tool['name']}**: {tool['description']}"
        if "use_when" in tool:
            tool_text += f"\n   - Use when: {tool['use_when']}"
        if "parameters" in tool:
            tool_text += f"\n   - Parameters: {tool['parameters']}"
        if "returns" in tool:
            tool_text += f"\n   - Returns: {tool['returns']}"
        tools_lines.append(tool_text)

    tools_section = "\n\n".join(tools_lines)

    # Format examples section
    examples_lines = []
    for example in examples:
        example_text = (
            f"Query: \"{example['query']}\"\nApproach:\n{example['approach']}"
        )
        examples_lines.append(example_text)

    examples_section = "\n\n".join(examples_lines)

    # Format guidelines section
    guidelines_section = "\n".join(f"- {guideline}" for guideline in guidelines)

    # Fill template
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_name=agent_name,
        primary_purpose=primary_purpose,
        role=role,
        domain=domain,
        purpose=purpose,
        tools_section=tools_section,
        query_handling=query_handling.strip(),
        response_format=response_format.strip(),
        examples=examples_section,
        guidelines=guidelines_section,
    )


class AgenticBaseAgent(BaseAgent):
    """
    Base class for agentic agents using Strands Agent.

    Provides common functionality for agents that use LLM reasoning:
    - Bedrock model initialization
    - Strands Agent setup
    - Tool management
    - System prompt handling
    - Response processing

    Subclasses must implement:
    - _define_agent_tools(): Return list of tools for the agent
    - _get_agent_system_prompt(): Return system prompt string
    - _extract_result_data(): Extract structured data from LLM response
    """

    def __init__(
        self,
        domain: str,
        agent_name: str,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize AgenticBaseAgent.

        Args:
            domain: Domain name (e.g., "travel", "financial")
            agent_name: Agent name (e.g., "weather-agent")
            config: Optional configuration override
        """
        super().__init__(domain, agent_name, config)

        # Load configuration with priority: env vars > config param > domain config > defaults
        self._load_configuration()

        # Validate configuration
        self._validate_configuration()

        # Log final configuration
        self._log_configuration()

        # Initialize Bedrock model with validated configuration
        self._initialize_bedrock_model()

        # Define agent-specific tools (implemented by subclass)
        try:
            self.tools = self._define_agent_tools()
            if not isinstance(self.tools, list):
                raise TypeError(
                    f"_define_agent_tools() must return a list, got {type(self.tools)}"
                )

            # Validate tools
            self._validate_tools(self.tools)

            # Log tool registration
            self._log_tool_registration(self.tools)

            self.logger.info(f"✅ Registered {len(self.tools)} agent tools")
        except Exception as e:
            self.logger.error(f"Failed to define agent tools: {e}", exc_info=True)
            raise

        # Get agent-specific system prompt (implemented by subclass)
        try:
            self.system_prompt = self._get_agent_system_prompt()
            if not isinstance(self.system_prompt, str):
                raise TypeError(
                    f"_get_agent_system_prompt() must return a string, got {type(self.system_prompt)}"
                )

            # Validate system prompt structure and quality
            self._validate_system_prompt(self.system_prompt)

            self.logger.debug(
                f"System prompt length: {len(self.system_prompt)} characters"
            )
        except Exception as e:
            self.logger.error(f"Failed to get system prompt: {e}", exc_info=True)
            raise

        # Create Strands Agent with tools and system prompt
        try:
            self.logger.debug(
                "Initializing Strands Agent...",
                extra={
                    "tool_count": len(self.tools),
                    "system_prompt_length": len(self.system_prompt),
                    "model_id": self.model_id,
                },
            )

            self.strands_agent = StrandsAgent(
                model=self.bedrock_model,
                system_prompt=self.system_prompt,
                tools=self.tools,
            )

            self.logger.info(
                f"✅ Initialized Strands Agent with {len(self.tools)} tools"
            )

        except TypeError as e:
            # Invalid parameter types
            self.logger.error(
                "❌ Failed to initialize Strands Agent: Invalid parameter types",
                extra={
                    "error_type": "TypeError",
                    "error": str(e),
                    "tool_count": len(self.tools),
                    "system_prompt_length": len(self.system_prompt),
                    "model_type": type(self.bedrock_model).__name__,
                },
                exc_info=True,
            )
            raise RuntimeError(
                f"Failed to initialize Strands Agent: Invalid parameter types. "
                f"Ensure model is BedrockModel, system_prompt is str, and tools is list. Error: {e}"
            ) from e

        except ValueError as e:
            # Invalid configuration or tool definitions
            self.logger.error(
                "❌ Failed to initialize Strands Agent: Invalid configuration",
                extra={
                    "error_type": "ValueError",
                    "error": str(e),
                    "tool_count": len(self.tools),
                    "system_prompt_length": len(self.system_prompt),
                },
                exc_info=True,
            )
            raise RuntimeError(
                f"Failed to initialize Strands Agent: Invalid configuration. "
                f"Check tool definitions and system prompt. Error: {e}"
            ) from e

        except Exception as e:
            # Generic initialization error
            self.logger.error(
                f"❌ Failed to initialize Strands Agent: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "tool_count": len(self.tools),
                    "system_prompt_length": len(self.system_prompt),
                    "model_id": self.model_id,
                },
                exc_info=True,
            )
            raise RuntimeError(
                f"Failed to initialize Strands Agent: {e}. "
                f"Tools: {len(self.tools)}, Prompt length: {len(self.system_prompt)} chars"
            ) from e

    def _load_configuration(self) -> None:
        """
        Load configuration from multiple sources with priority order.

        Priority (highest to lowest):
        1. Environment variables (AGENTIC_MODEL_ID, AGENTIC_MAX_TOKENS, etc.)
        2. Constructor config parameter
        3. Domain configuration file (config/domains/{domain}.yaml)
        4. Default values

        Configuration Parameters:
        - model_id: Bedrock model ID (default: from BaseAgent or "anthropic.claude-3-haiku-20240307-v1:0")
        - region: AWS region (default: from BaseAgent or "us-east-1")
        - max_tokens: Maximum tokens in response (default: 1000)
        - temperature: LLM temperature 0.0-1.0 (default: 0.0 for determinism)

        Environment Variables:
        - AGENTIC_MODEL_ID: Override model_id
        - AGENTIC_REGION or AWS_PRIMARY_REGION: Override region
        - AGENTIC_MAX_TOKENS: Override max_tokens
        - AGENTIC_TEMPERATURE: Override temperature
        """
        import os

        # Start with defaults
        defaults = {
            "model_id": "us.anthropic.claude-sonnet-4-20250514-v1:0",
            "region": "us-east-1",
            "max_tokens": 8096,
            "temperature": 0.0,
        }

        # Layer 1: Start with defaults
        config = defaults.copy()

        # Layer 2: Load from domain configuration if available
        # The domain config is already loaded in self.config by BaseAgent
        if hasattr(self, "config") and self.config:
            # Check for agentic-specific config section
            if "agentic" in self.config:
                agentic_config = self.config["agentic"]
                if isinstance(agentic_config, dict):
                    for key in ["model_id", "region", "max_tokens", "temperature"]:
                        if key in agentic_config:
                            config[key] = agentic_config[key]
                            self.logger.debug(
                                f"Loaded {key} from domain config: {agentic_config[key]}"
                            )

            # Also check top-level config keys
            for key in ["model_id", "region", "max_tokens", "temperature"]:
                if key in self.config:
                    config[key] = self.config[key]
                    self.logger.debug(
                        f"Loaded {key} from agent config: {self.config[key]}"
                    )

        # Layer 3: Override with BaseAgent's model_id and region if set
        # (these come from environment variables in BaseAgent.__init__)
        if hasattr(self, "model_id") and self.model_id:
            config["model_id"] = self.model_id
        if hasattr(self, "region") and self.region:
            config["region"] = self.region

        # Layer 4: Override with environment variables (highest priority)
        env_overrides = {
            "model_id": os.getenv("AGENTIC_MODEL_ID"),
            "region": os.getenv("AGENTIC_REGION") or os.getenv("AWS_PRIMARY_REGION"),
            "max_tokens": os.getenv("AGENTIC_MAX_TOKENS"),
            "temperature": os.getenv("AGENTIC_TEMPERATURE"),
        }

        for key, value in env_overrides.items():
            if value is not None:
                # Convert string values to appropriate types
                if key == "max_tokens":
                    try:
                        config[key] = int(value)
                        self.logger.debug(f"Loaded {key} from environment: {value}")
                    except ValueError:
                        self.logger.warning(
                            f"Invalid environment variable AGENTIC_MAX_TOKENS={value}, ignoring"
                        )
                elif key == "temperature":
                    try:
                        config[key] = float(value)
                        self.logger.debug(f"Loaded {key} from environment: {value}")
                    except ValueError:
                        self.logger.warning(
                            f"Invalid environment variable AGENTIC_TEMPERATURE={value}, ignoring"
                        )
                else:
                    config[key] = value
                    self.logger.debug(f"Loaded {key} from environment: {value}")

        # Store final configuration
        self.model_id = config["model_id"]
        self.region = config["region"]
        self.max_tokens = config["max_tokens"]
        self.temperature = config["temperature"]

    def _validate_configuration(self) -> None:
        """
        Validate configuration values and apply corrections if needed.

        Validates:
        - model_id is not empty
        - region is not empty
        - max_tokens is positive integer
        - temperature is between 0.0 and 1.0

        Logs warnings for invalid values and applies defaults.
        Raises ValueError for critical configuration errors.
        """
        # Validate model_id (critical)
        if not self.model_id or not isinstance(self.model_id, str):
            raise ValueError(
                "model_id is required but not configured. "
                "Set AGENTIC_MODEL_ID environment variable or configure in domain YAML."
            )

        # Validate region (critical)
        if not self.region or not isinstance(self.region, str):
            raise ValueError(
                "region is required but not configured. "
                "Set AGENTIC_REGION or AWS_PRIMARY_REGION environment variable or configure in domain YAML."
            )

        # Validate max_tokens (non-critical, can use default)
        if not isinstance(self.max_tokens, int | float) or self.max_tokens <= 0:
            self.logger.warning(
                f"Invalid max_tokens={self.max_tokens} (must be positive number). "
                f"Using default: 1000"
            )
            self.max_tokens = 1000
        else:
            # Convert to int if it's a float
            self.max_tokens = int(self.max_tokens)

            # Warn if value seems unusual
            if self.max_tokens < 100:
                self.logger.warning(
                    f"max_tokens={self.max_tokens} is very low. "
                    f"Responses may be truncated. Recommended minimum: 100"
                )
            elif self.max_tokens > 4000:
                self.logger.warning(
                    f"max_tokens={self.max_tokens} is very high. "
                    f"This will increase latency and cost. Recommended maximum: 4000"
                )

        # Validate temperature (non-critical, can use default)
        if not isinstance(self.temperature, int | float) or not (
            0.0 <= self.temperature <= 1.0
        ):
            self.logger.warning(
                f"Invalid temperature={self.temperature} (must be between 0.0 and 1.0). "
                f"Using default: 0.0"
            )
            self.temperature = 0.0
        else:
            # Convert to float
            self.temperature = float(self.temperature)

            # Provide guidance on temperature values
            if self.temperature == 0.0:
                self.logger.debug(
                    "temperature=0.0 (deterministic mode). "
                    "Same query will produce consistent responses."
                )
            elif self.temperature < 0.3:
                self.logger.debug(
                    f"temperature={self.temperature} (low randomness). "
                    f"Responses will be fairly consistent."
                )
            elif self.temperature > 0.7:
                self.logger.info(
                    f"temperature={self.temperature} (high randomness). "
                    f"Responses will be more creative but less predictable."
                )

    def _log_configuration(self) -> None:
        """
        Log final configuration for debugging and monitoring.

        Logs:
        - All configuration parameters
        - Configuration sources
        - Validation status
        - Performance/cost implications
        """
        self.logger.info(
            "🔧 Agentic Agent Configuration:",
            extra={
                "model_id": self.model_id,
                "region": self.region,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
        )

        # Log model selection guidance
        if "haiku" in self.model_id.lower():
            self.logger.info(
                "📊 Using Haiku model: Fast responses (~1-2s), lower cost, good for simple queries"
            )
        elif "sonnet" in self.model_id.lower():
            self.logger.info(
                "📊 Using Sonnet model: Balanced performance (~2-4s), moderate cost, good for complex queries"
            )
        elif "opus" in self.model_id.lower():
            self.logger.info(
                "📊 Using Opus model: Best quality (~5-10s), higher cost, use for critical tasks"
            )

        # Log cost/performance implications
        estimated_cost_per_1k_requests = self._estimate_cost_per_1k_requests()
        if estimated_cost_per_1k_requests:
            self.logger.debug(
                f"💰 Estimated cost: ~${estimated_cost_per_1k_requests:.2f} per 1,000 requests "
                f"(based on model and max_tokens)"
            )

        # Log configuration validation status
        self.logger.debug(
            "✅ Configuration validated successfully",
            extra={
                "max_tokens_valid": isinstance(self.max_tokens, int)
                and self.max_tokens > 0,
                "temperature_valid": isinstance(self.temperature, float)
                and 0.0 <= self.temperature <= 1.0,
                "model_id_valid": bool(self.model_id),
                "region_valid": bool(self.region),
            },
        )

    def _estimate_cost_per_1k_requests(self) -> float | None:
        """
        Estimate cost per 1,000 requests based on model and max_tokens.

        This is a rough estimate based on Bedrock pricing as of 2024.
        Actual costs may vary based on:
        - Input token count (varies by query)
        - Output token count (varies by response, capped by max_tokens)
        - Bedrock pricing changes

        Returns:
            Estimated cost in USD per 1,000 requests, or None if model unknown
        """
        # Approximate pricing per 1M tokens (input/output) as of 2024
        # These are rough estimates and should be updated based on actual pricing
        pricing = {
            "haiku": {"input": 0.25, "output": 1.25},  # per 1M tokens
            "sonnet": {"input": 3.0, "output": 15.0},
            "opus": {"input": 15.0, "output": 75.0},
        }

        # Determine model type
        model_type = None
        for key in pricing:
            if key in self.model_id.lower():
                model_type = key
                break

        if not model_type:
            return None

        # Estimate tokens per request
        # Assume average input: 200 tokens (query + system prompt)
        # Assume average output: max_tokens (worst case)
        avg_input_tokens = 200
        avg_output_tokens = self.max_tokens

        # Calculate cost per request
        input_cost_per_request = (avg_input_tokens / 1_000_000) * pricing[model_type][
            "input"
        ]
        output_cost_per_request = (avg_output_tokens / 1_000_000) * pricing[model_type][
            "output"
        ]
        cost_per_request = input_cost_per_request + output_cost_per_request

        # Return cost per 1,000 requests
        return cost_per_request * 1000

    def _initialize_bedrock_model(self) -> None:
        """
        Initialize Bedrock model with validated configuration.

        This is called after configuration loading and validation.
        Separated into its own method for clarity and testability.

        Error Handling:
        - Catches and logs initialization failures with full context
        - Provides specific error messages for common failure modes
        - Re-raises exception to prevent agent from running with invalid model

        Raises:
            Exception: If Bedrock model initialization fails
        """
        try:
            self.logger.debug(
                "Initializing Bedrock model...",
                extra={
                    "model_id": self.model_id,
                    "region": self.region,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                },
            )

            self.bedrock_model = BedrockModel(
                model_id=self.model_id,
                streaming=False,
                region_name=self.region,
                max_tokens=self.max_tokens,
            )

            self.logger.info(
                f"✅ Initialized Bedrock model: "
                f"model_id={self.model_id} "
                f"region={self.region} "
                f"max_tokens={self.max_tokens}"
            )

        except ImportError as e:
            # Strands or boto3 not installed
            self.logger.error(
                "❌ Failed to initialize Bedrock model: Missing dependencies",
                extra={
                    "error_type": "ImportError",
                    "error": str(e),
                    "model_id": self.model_id,
                    "region": self.region,
                },
                exc_info=True,
            )
            raise RuntimeError(
                f"Failed to initialize Bedrock model: Missing required dependencies. "
                f"Ensure 'strands' and 'boto3' are installed. Error: {e}"
            ) from e

        except ValueError as e:
            # Invalid model_id or configuration
            self.logger.error(
                "❌ Failed to initialize Bedrock model: Invalid configuration",
                extra={
                    "error_type": "ValueError",
                    "error": str(e),
                    "model_id": self.model_id,
                    "region": self.region,
                    "max_tokens": self.max_tokens,
                },
                exc_info=True,
            )
            raise RuntimeError(
                f"Failed to initialize Bedrock model: Invalid configuration. "
                f"Check model_id='{self.model_id}' and region='{self.region}'. Error: {e}"
            ) from e

        except Exception as e:
            # Generic error (AWS credentials, network, etc.)
            error_msg = str(e)

            # Provide helpful hints for common errors
            hints = []
            if "credentials" in error_msg.lower() or "access" in error_msg.lower():
                hints.append(
                    "Check AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)"
                )
                hints.append("Verify IAM permissions for Bedrock access")
            if "region" in error_msg.lower():
                hints.append(f"Verify region '{self.region}' supports Bedrock")
                hints.append(
                    "Check AWS_REGION or AWS_DEFAULT_REGION environment variables"
                )
            if "model" in error_msg.lower():
                hints.append(
                    f"Verify model '{self.model_id}' is available in region '{self.region}'"
                )
                hints.append("Check Bedrock model access in AWS console")

            self.logger.error(
                f"❌ Failed to initialize Bedrock model: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "model_id": self.model_id,
                    "region": self.region,
                    "max_tokens": self.max_tokens,
                    "troubleshooting_hints": hints,
                },
                exc_info=True,
            )

            # Build helpful error message
            error_parts = [
                f"Failed to initialize Bedrock model: {e}",
                f"Model: {self.model_id}",
                f"Region: {self.region}",
            ]
            if hints:
                error_parts.append("Troubleshooting:")
                error_parts.extend(f"  - {hint}" for hint in hints)

            raise RuntimeError("\n".join(error_parts)) from e

    def _validate_tools(self, tools: list) -> None:
        """
        Validate tool definitions to ensure they meet requirements.

        Validates:
        - Each tool is callable
        - Tool has name attribute
        - Tool has description attribute
        - Tool parameters have type hints
        - Tool has return type annotation

        Args:
            tools: List of tool functions to validate

        Raises:
            ValueError: If validation fails
        """
        if not tools:
            self.logger.warning(
                "No tools defined for agent. Agent will have limited capabilities."
            )
            return

        for i, tool in enumerate(tools, 1):
            # Check if callable
            if not callable(tool):
                raise ValueError(f"Tool {i} is not callable: {type(tool)}")

            # Get tool name (Strands tools store name in different ways)
            tool_name = getattr(tool, "name", None) or getattr(
                tool, "__name__", f"tool_{i}"
            )

            # Check for description attribute
            tool_description = getattr(tool, "description", None)
            if not tool_description:
                self.logger.warning(
                    f"Tool {i} ({tool_name}) missing 'description'. "
                    "Add description parameter to @tool decorator for better LLM understanding."
                )
            elif len(tool_description.strip()) < 10:
                self.logger.warning(
                    f"Tool {i} ({tool_name}) has very short description. "
                    "Provide a clear description for better LLM understanding."
                )

            # Check for type hints on parameters
            if hasattr(tool, "__annotations__"):
                annotations = tool.__annotations__
                if not annotations:
                    self.logger.warning(
                        f"Tool {i} ({getattr(tool, 'name', tool.__name__)}) has no type hints. "
                        "Add type hints to parameters for better LLM understanding."
                    )
                elif "return" not in annotations:
                    self.logger.warning(
                        f"Tool {i} ({getattr(tool, 'name', tool.__name__)}) missing return type hint. "
                        "Add return type hint (-> dict or -> list) for clarity."
                    )
            else:
                self.logger.warning(
                    f"Tool {i} ({getattr(tool, 'name', tool.__name__)}) has no __annotations__. "
                    "Add type hints to parameters."
                )

        self.logger.debug(f"Tool validation completed: {len(tools)} tools validated")

    def _log_tool_registration(self, tools: list) -> None:
        """
        Log detailed information about registered tools.

        Logs:
        - Tool name and description
        - Tool parameters and types
        - Tool return type

        Args:
            tools: List of registered tools
        """
        if not tools:
            return

        self.logger.info(f"📋 Registering {len(tools)} tool(s):")

        for i, tool in enumerate(tools, 1):
            tool_name = getattr(tool, "name", None) or getattr(
                tool, "__name__", f"tool_{i}"
            )
            tool_desc = getattr(tool, "description", "No description")

            # Log basic info
            self.logger.info(f"  {i}. {tool_name}")
            self.logger.debug(f"     Description: {tool_desc}")

            # Log parameters if available
            if hasattr(tool, "__annotations__"):
                annotations = tool.__annotations__.copy()
                return_type = annotations.pop("return", "Any")

                if annotations:
                    params_str = ", ".join(
                        f"{name}: {typ.__name__ if hasattr(typ, '__name__') else str(typ)}"
                        for name, typ in annotations.items()
                    )
                    self.logger.debug(f"     Parameters: {params_str}")
                    self.logger.debug(
                        f"     Returns: {return_type.__name__ if hasattr(return_type, '__name__') else str(return_type)}"
                    )
                else:
                    self.logger.debug("     Parameters: none")

            # Log if tool has docstring
            if tool.__doc__:
                doc_preview = tool.__doc__.strip().split("\n")[0][:80]
                self.logger.debug(f"     Doc: {doc_preview}...")

    def _validate_system_prompt(self, prompt: str) -> None:
        """
        Validate system prompt structure and quality.

        Checks for:
        - Appropriate length (100-2000 characters recommended)
        - Presence of recommended sections
        - Quality indicators

        Logs warnings for issues but doesn't fail initialization,
        allowing agents to work with suboptimal prompts.

        Args:
            prompt: System prompt string to validate
        """
        prompt_length = len(prompt)

        # Length validation
        if prompt_length < 100:
            self.logger.warning(
                f"⚠️  System prompt is very short ({prompt_length} chars). "
                "Recommended minimum: 100 characters. "
                "Short prompts may not provide enough guidance for the LLM."
            )
        elif prompt_length > 2000:
            self.logger.warning(
                f"⚠️  System prompt is very long ({prompt_length} chars). "
                "Recommended maximum: 2000 characters. "
                "Long prompts increase latency and cost."
            )
        else:
            self.logger.info(
                f"✅ System prompt length: {prompt_length} chars (within recommended range)"
            )

        # Check for empty prompt
        if not prompt.strip():
            self.logger.error(
                "❌ System prompt is empty or whitespace only. "
                "Agent will have no guidance."
            )
            raise ValueError("System prompt cannot be empty")

        # Section presence checks (case-insensitive)
        prompt_lower = prompt.lower()

        # Check for role definition indicators
        has_role = any(
            indicator in prompt_lower
            for indicator in [
                "you are",
                "your role",
                "your job",
                "you help",
                "you assist",
                "agent specializing",
                "agent for",
                "agent that",
            ]
        )

        if not has_role:
            self.logger.warning(
                "⚠️  System prompt may be missing role definition. "
                "Consider starting with 'You are a [role] agent...' "
                "to clearly define the agent's purpose."
            )

        # Check for capabilities/tools section
        has_capabilities = any(
            indicator in prompt_lower
            for indicator in [
                "capabilities",
                "tools",
                "you have access",
                "you can",
                "available tools",
                "your tools",
            ]
        )

        if not has_capabilities:
            self.logger.warning(
                "⚠️  System prompt may be missing capabilities section. "
                "Consider adding a section describing available tools and when to use them."
            )

        # Check for examples
        has_examples = any(
            indicator in prompt_lower
            for indicator in [
                "example",
                "for instance",
                "such as",
                "query:",
                "when a user asks",
            ]
        )

        if not has_examples:
            self.logger.info(
                "💡 System prompt could benefit from examples. "
                "Consider adding sample queries and how to handle them."
            )

        # Check for guidelines
        has_guidelines = any(
            indicator in prompt_lower
            for indicator in [
                "guideline",
                "always",
                "never",
                "important",
                "remember",
                "do not",
                "make sure",
                "ensure",
            ]
        )

        if not has_guidelines:
            self.logger.info(
                "💡 System prompt could benefit from guidelines. "
                "Consider adding dos and don'ts for the agent."
            )

        # Check for response format guidance
        has_format = any(
            indicator in prompt_lower
            for indicator in [
                "response format",
                "structure your response",
                "format:",
                "provide",
                "include",
                "your response should",
            ]
        )

        if not has_format:
            self.logger.info(
                "💡 System prompt could benefit from response format guidance. "
                "Consider specifying how responses should be structured."
            )

        # Quality indicators
        quality_score = sum(
            [
                has_role,
                has_capabilities,
                has_examples,
                has_guidelines,
                has_format,
                100 <= prompt_length <= 2000,
            ]
        )

        if quality_score >= 5:
            self.logger.info(
                f"✅ System prompt quality: Excellent ({quality_score}/6 indicators present)"
            )
        elif quality_score >= 3:
            self.logger.info(
                f"✅ System prompt quality: Good ({quality_score}/6 indicators present)"
            )
        else:
            self.logger.warning(
                f"⚠️  System prompt quality: Needs improvement ({quality_score}/6 indicators present). "
                "Consider adding missing sections for better agent performance."
            )

        # Check for overly generic prompts
        generic_phrases = [
            "helpful assistant",
            "i'm here to help",
            "how can i assist",
            "happy to help",
        ]

        if any(phrase in prompt_lower for phrase in generic_phrases):
            self.logger.warning(
                "⚠️  System prompt contains generic assistant language. "
                "Be more specific about the agent's domain and capabilities."
            )

    @abstractmethod
    def _define_agent_tools(self) -> list:
        """
        Define agent-specific tools (implemented by subclass).

        Tools are functions decorated with @tool that the LLM can call.
        Each tool should:
        - Have a clear name and description
        - Take typed parameters
        - Return structured data (dict or list)
        - Handle errors gracefully

        Returns:
            List of tool functions

        Example:
            @tool(name="search_data", description="Search for data")
            def search_data(query: str, limit: int = 10) -> dict:
                results = self.data_source.search(query, limit)
                return {"results": results, "count": len(results)}

            return [search_data]
        """
        pass

    @abstractmethod
    def _get_agent_system_prompt(self) -> str:
        """
                Get agent-specific system prompt (implemented by subclass).

                The system prompt guides the LLM's behavior and is critical for agent quality.
                A well-structured prompt ensures the agent understands its role, uses tools
                correctly, and provides helpful responses.

                System Prompt Structure:
                =======================

                A good system prompt should include these sections:

                1. ROLE DEFINITION (Required)
                   - Who the agent is
                   - What domain it operates in
                   - Its primary purpose

                2. CAPABILITIES (Required)
                   - List of available tools
                   - When to use each tool
                   - Tool parameters and expected outputs

                3. EXAMPLES (Recommended)
                   - Sample queries and how to handle them
                   - Expected tool usage patterns
                   - Good response examples

                4. GUIDELINES (Recommended)
                   - Response format expectations
                   - Dos and don'ts
                   - Domain-specific rules
                   - Error handling approach

                Best Practices:
                ==============

                ✅ DO:
                - Be specific about the agent's role and domain
                - Clearly explain when to use each tool
                - Provide concrete examples of good responses
                - Set clear expectations for response format
                - Include domain-specific knowledge
                - Keep language clear and direct
                - Use structured formatting (headers, lists, etc.)

                ❌ DON'T:
                - Be too generic ("You are a helpful assistant")
                - Omit tool descriptions or usage guidance
                - Make the prompt too long (>2000 chars is excessive)
                - Use vague language ("sometimes", "maybe", "try to")
                - Contradict tool descriptions
                - Include outdated or incorrect information

                Length Guidelines:
                =================
                - Minimum: 100 characters (too short = poor guidance)
                - Recommended: 300-1000 characters (good balance)
                - Maximum: 2000 characters (longer = slower, more expensive)

                Template:
                ========

                ```
                # [Agent Name] - [Primary Purpose]

                You are a [role] agent specializing in [domain]. Your job is to [purpose].

                ## Your Capabilities

                You have access to these tools:

                1. **[tool_name]**: [Description of what it does]
                   - Use when: [condition]
                   - Parameters: [param descriptions]
                   - Returns: [output description]

                2. **[tool_name]**: [Description]
                   - Use when: [condition]
                   - Parameters: [param descriptions]
                   - Returns: [output description]

                ## How to Handle Queries

                When a user asks about [topic]:
                1. [Step 1 - usually involves calling a tool]
                2. [Step 2 - analyze results]
                3. [Step 3 - provide response]

                When a user asks about [another topic]:
                1. [Different approach]
                2. [Different steps]

                ## Response Format

                Structure your responses like this:
                - [Section 1]: [What to include]
                - [Section 2]: [What to include]
                - [Section 3]: [What to include]

                ## Examples

                Query: "[example query]"
                Approach:
                - Call [tool]([params])
                - Analyze [specific aspect]
                - Respond with [format]

                Query: "[another example]"
                Approach:
                - [Different approach]

                ## Important Guidelines

                - Always [guideline 1]
                - Never [anti-pattern 1]
                - Consider [context factor]
                - If [condition], then [action]
                ```

                Returns:
                    System prompt string (100-2000 characters recommended)

                Example Implementation:
                ======================

                ```python
                def _get_agent_system_prompt(self) -> str:
                    return '''# Weather Agent - Weather Information and Activity Recommendations

        You are a weather agent specializing in providing weather forecasts and
        activity recommendations. Your job is to help users plan their activities
        based on weather conditions.

        ## Your Capabilities

        You have access to these tools:

        1. **get_weather_forecast**: Get weather forecast for a location
           - Use when: User asks about weather, temperature, or conditions
           - Parameters: location (str), days (int, default 3)
           - Returns: Forecast data with temperature, conditions, precipitation

        2. **analyze_weather_for_activities**: Recommend indoor/outdoor activities
           - Use when: User asks what to do or needs activity suggestions
           - Parameters: precipitation_chance (float), condition (str)
           - Returns: Activity recommendations with reasoning

        ## How to Handle Queries

        When a user asks about weather:
        1. Call get_weather_forecast with their location
        2. Extract key information (temperature, conditions, precipitation)
        3. Provide a clear, conversational summary

        When a user asks about activities:
        1. First get the weather forecast
        2. Call analyze_weather_for_activities with the forecast data
        3. Provide specific activity recommendations with reasoning

        ## Response Format

        Structure your responses like this:
        - Weather Summary: Current conditions and forecast
        - Activity Recommendations: Specific suggestions based on weather
        - Additional Tips: Relevant advice (clothing, timing, etc.)

        ## Examples

        Query: "What's the weather in Seattle?"
        Approach:
        - Call get_weather_forecast("Seattle", 3)
        - Summarize temperature, conditions, and precipitation
        - Mention any notable weather patterns

        Query: "What should I do in Portland this weekend?"
        Approach:
        - Call get_weather_forecast("Portland", 3)
        - Call analyze_weather_for_activities with forecast data
        - Provide specific indoor/outdoor recommendations
        - Explain reasoning based on weather

        ## Important Guidelines

        - Always provide specific, actionable information
        - Never make up weather data - only use tool results
        - Consider both current conditions and forecast trends
        - If weather is uncertain, mention multiple scenarios
        - Be conversational and helpful, not robotic
        '''
                ```

                Validation:
                ==========

                The framework automatically validates:
                - Prompt is a string
                - Prompt length is reasonable (warns if <100 or >2000 chars)
                - Prompt is not empty

                Additional validation in _validate_system_prompt() checks for:
                - Presence of recommended sections
                - Appropriate length
                - Quality indicators
        """
        pass

    @abstractmethod
    def _extract_result_data(self, response, **kwargs) -> dict:
        """
        Extract structured data from Strands Agent response (implemented by subclass).

        The LLM generates natural language, but we need structured data
        for other agents to consume. This method extracts that data from
        the tool calls the agent made.

        Args:
            response: Strands Agent response object
            **kwargs: Additional context (e.g., location, query)

        Returns:
            Structured data dictionary

        Example:
            result_data = {"timestamp": datetime.now(UTC).isoformat()}

            if hasattr(response, 'tool_results'):
                for tool_result in response.tool_results:
                    if tool_result.tool_name == "search_data":
                        result_data["results"] = tool_result.result

            return result_data
        """
        pass

    def _process_task_impl(self, task: Task, user_input: dict[str, Any]) -> Task:
        """
        Process task using Strands Agent (standard implementation).

        This method:
        1. Extracts query from user input
        2. Enhances query with context
        3. Invokes Strands Agent for reasoning
        4. Extracts response text and structured data
        5. Returns success or error task

        Subclasses can override this if they need custom processing,
        but most agents can use this default implementation.

        Args:
            task: A2A Task object
            user_input: Extracted user input

        Returns:
            Updated task with results
        """
        import time

        # Track processing time for performance monitoring
        start_time = time.time()

        # Extract query
        query = user_input.get("query", "")
        if not query:
            # Try to construct query from other fields
            try:
                query = self._construct_query_from_input(user_input)
                self.logger.debug(f"Constructed query from input: '{query}'")
            except Exception as e:
                self.logger.error(
                    "❌ Failed to construct query from input",
                    extra={
                        "error": str(e),
                        "user_input_keys": list(user_input.keys()),
                        "task_id": task.id,
                    },
                    exc_info=True,
                )
                return self._create_error_task(
                    task, f"Invalid input: could not construct query. Error: {e}"
                )

        if not query:
            self.logger.warning(
                "Empty query after construction",
                extra={
                    "user_input": user_input,
                    "task_id": task.id,
                },
            )
            return self._create_error_task(task, "No query provided in user input")

        self.logger.info(
            "🤖 Agentic processing started",
            extra={
                "query": query,
                "query_length": len(query),
                "user_input_keys": list(user_input.keys()),
                "task_id": task.id,
            },
        )

        try:
            # Let Strands Agent reason and use tools
            self.logger.debug(
                "Invoking Strands Agent...",
                extra={
                    "query": query,
                    "model_id": self.model_id,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                },
            )

            llm_start_time = time.time()

            try:
                response = self.strands_agent(query)
            except Exception as llm_error:
                llm_elapsed = time.time() - llm_start_time

                # Categorize LLM errors for better troubleshooting
                error_type = type(llm_error).__name__
                error_msg = str(llm_error)

                # Provide specific guidance based on error type
                hints = []
                if "throttl" in error_msg.lower() or "rate" in error_msg.lower():
                    hints.append(
                        "Bedrock rate limit exceeded - implement retry with backoff"
                    )
                    hints.append(
                        "Consider reducing request frequency or increasing quotas"
                    )
                elif "timeout" in error_msg.lower():
                    hints.append("LLM invocation timed out - query may be too complex")
                    hints.append(
                        "Consider reducing max_tokens or simplifying system prompt"
                    )
                elif "token" in error_msg.lower() and "limit" in error_msg.lower():
                    hints.append(
                        "Token limit exceeded - reduce system prompt or max_tokens"
                    )
                    hints.append(f"Current max_tokens: {self.max_tokens}")
                elif (
                    "credentials" in error_msg.lower()
                    or "unauthorized" in error_msg.lower()
                ):
                    hints.append("AWS credentials issue - check IAM permissions")
                    hints.append("Verify Bedrock model access in AWS console")
                elif "model" in error_msg.lower():
                    hints.append(f"Model '{self.model_id}' may not be available")
                    hints.append(f"Verify model access in region '{self.region}'")

                self.logger.error(
                    f"❌ LLM invocation failed: {error_type}",
                    extra={
                        "error_type": error_type,
                        "error": error_msg,
                        "query": query,
                        "query_length": len(query),
                        "model_id": self.model_id,
                        "region": self.region,
                        "max_tokens": self.max_tokens,
                        "elapsed_seconds": round(llm_elapsed, 2),
                        "troubleshooting_hints": hints,
                        "task_id": task.id,
                    },
                    exc_info=True,
                )

                # Build helpful error message
                error_parts = [
                    f"LLM invocation failed: {error_msg}",
                    (
                        f"Query: {query[:100]}..."
                        if len(query) > 100
                        else f"Query: {query}"
                    ),
                ]
                if hints:
                    error_parts.append("Troubleshooting:")
                    error_parts.extend(f"  - {hint}" for hint in hints)

                return self._create_error_task(task, "\n".join(error_parts))

            llm_elapsed = time.time() - llm_start_time

            self.logger.info(
                "✅ LLM invocation completed",
                extra={
                    "elapsed_seconds": round(llm_elapsed, 2),
                    "model_id": self.model_id,
                    "task_id": task.id,
                },
            )

            # Log tool calls for debugging and monitoring
            self._log_tool_calls(response)

            # Log detailed LLM reasoning if debug enabled
            self._log_llm_reasoning(response, query)

            # Extract response text
            response_text = (
                response.text if hasattr(response, "text") else str(response)
            )

            if not response_text:
                self.logger.warning(
                    "Empty response text from Strands Agent",
                    extra={
                        "query": query,
                        "has_tool_results": hasattr(response, "tool_results")
                        and bool(response.tool_results),
                        "task_id": task.id,
                    },
                )
                response_text = "Agent completed processing but returned no text."

            self.logger.info(
                "✅ Strands Agent completed",
                extra={
                    "response_length": len(response_text),
                    "query_length": len(query),
                    "task_id": task.id,
                },
            )

            # Extract structured data (subclass implementation)
            try:
                self.logger.debug("Extracting structured data from response...")

                result_data = self._extract_result_data(response, **user_input)

                if not isinstance(result_data, dict):
                    self.logger.warning(
                        f"_extract_result_data() returned {type(result_data)}, expected dict. Wrapping in dict.",
                        extra={
                            "result_type": type(result_data).__name__,
                            "task_id": task.id,
                        },
                    )
                    result_data = {"result": result_data}

                self.logger.debug(
                    "Extracted structured data",
                    extra={
                        "data_keys": list(result_data.keys()),
                        "data_size": len(str(result_data)),
                        "task_id": task.id,
                    },
                )

            except NotImplementedError:
                # Subclass didn't implement _extract_result_data
                self.logger.warning(
                    "_extract_result_data() not implemented by subclass. Using empty result data.",
                    extra={"task_id": task.id},
                )
                result_data = {
                    "timestamp": datetime.now(UTC).isoformat(),
                }

            except Exception as e:
                self.logger.error(
                    "❌ Failed to extract result data",
                    extra={
                        "error_type": type(e).__name__,
                        "error": str(e),
                        "query": query,
                        "has_tool_results": hasattr(response, "tool_results")
                        and bool(response.tool_results),
                        "task_id": task.id,
                    },
                    exc_info=True,
                )
                # Continue with minimal result data rather than failing
                result_data = {
                    "error": "Failed to extract structured data",
                    "error_details": str(e),
                    "timestamp": datetime.now(UTC).isoformat(),
                }

            # Calculate total processing time
            total_elapsed = time.time() - start_time

            self.logger.info(
                "✅ Task processing completed successfully",
                extra={
                    "total_elapsed_seconds": round(total_elapsed, 2),
                    "llm_elapsed_seconds": round(llm_elapsed, 2),
                    "response_length": len(response_text),
                    "data_keys": list(result_data.keys()),
                    "task_id": task.id,
                },
            )

            return self._create_success_task(task, response_text, result_data)

        except Exception as e:
            # Catch-all for unexpected errors
            total_elapsed = time.time() - start_time

            self.logger.error(
                "❌ Agentic agent failed with unexpected error",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "query": query,
                    "elapsed_seconds": round(total_elapsed, 2),
                    "task_id": task.id,
                },
                exc_info=True,
            )

            return self._create_error_task(
                task, f"Agent failed with unexpected error: {type(e).__name__}: {e}"
            )

    def _construct_query_from_input(self, user_input: dict[str, Any]) -> str:
        """
        Construct query from user input fields.

        If no explicit query is provided, try to build one from other fields.
        Subclasses can override this for domain-specific query construction.

        Args:
            user_input: User input dictionary

        Returns:
            Constructed query string
        """
        # Default: just use the first non-empty string value
        for _key, value in user_input.items():
            if isinstance(value, str) and value:
                return value

        return "Process this request"

    def _log_tool_calls(self, response):
        """
        Log tool calls made by Strands Agent (for debugging and monitoring).

        Logs:
        - Number of tool calls made
        - Tool name and result type for each call
        - Tool execution errors
        - Result preview for debugging
        - Success/failure status
        - Tool execution time (if available)
        - Tool parameters (in debug mode)

        Args:
            response: Strands Agent response object
        """
        if not hasattr(response, "tool_results"):
            self.logger.debug(
                "Response has no tool_results attribute",
                extra={"response_type": type(response).__name__},
            )
            return

        if not response.tool_results:
            self.logger.info(
                "🔧 Agent made no tool calls (direct response)",
                extra={"response_has_text": hasattr(response, "text")},
            )
            return

        tool_count = len(response.tool_results)
        self.logger.info(
            f"🔧 Agent made {tool_count} tool call(s):",
            extra={"tool_count": tool_count},
        )

        successful_calls = 0
        failed_calls = 0
        tool_summary = []

        for i, tool_result in enumerate(response.tool_results, 1):
            tool_name = getattr(tool_result, "tool_name", "unknown")
            result_type = (
                type(tool_result.result).__name__
                if hasattr(tool_result, "result")
                else "unknown"
            )

            # Check for errors at multiple levels
            has_error = hasattr(tool_result, "error") and tool_result.error
            result_has_error = False

            # Build tool info for structured logging
            tool_info = {
                "tool_name": tool_name,
                "result_type": result_type,
                "call_index": i,
            }

            # Log tool parameters if available (debug mode)
            if hasattr(tool_result, "parameters"):
                self.logger.debug(
                    f"     Parameters: {tool_result.parameters}",
                    extra={
                        "tool_name": tool_name,
                        "parameters": tool_result.parameters,
                    },
                )
                tool_info["parameters"] = tool_result.parameters

            # Log tool execution time if available
            if hasattr(tool_result, "execution_time"):
                self.logger.debug(
                    f"     Execution time: {tool_result.execution_time:.3f}s",
                    extra={
                        "tool_name": tool_name,
                        "execution_time": tool_result.execution_time,
                    },
                )
                tool_info["execution_time"] = tool_result.execution_time

            if has_error:
                failed_calls += 1
                error_msg = str(tool_result.error)
                self.logger.warning(
                    f"  {i}. ❌ {tool_name} -> ERROR",
                    extra={**tool_info, "error": error_msg},
                )
                self.logger.warning(f"     Error: {error_msg}")
                tool_summary.append(f"{tool_name}: ERROR")
            else:
                successful_calls += 1
                self.logger.info(
                    f"  {i}. ✅ {tool_name} -> {result_type}", extra=tool_info
                )
                tool_summary.append(f"{tool_name}: {result_type}")

            # Log result preview for debugging
            if hasattr(tool_result, "result") and not has_error:
                result = tool_result.result

                if isinstance(result, dict):
                    keys = list(result.keys())[:5]  # First 5 keys
                    self.logger.debug(
                        f"     Result keys: {keys}",
                        extra={"tool_name": tool_name, "result_keys": keys},
                    )

                    # Log success/error status if present in result
                    if "success" in result:
                        is_success = result["success"]
                        status = "✅ Success" if is_success else "❌ Failed"
                        self.logger.debug(
                            f"     Status: {status}",
                            extra={"tool_name": tool_name, "success": is_success},
                        )

                        if not is_success:
                            result_has_error = True

                    # Log error from result dict if present
                    if result.get("error"):
                        error_msg = result["error"]
                        self.logger.warning(
                            f"     Result error: {error_msg}",
                            extra={"tool_name": tool_name, "result_error": error_msg},
                        )
                        result_has_error = True

                    # Log data size for large results
                    result_size = len(str(result))
                    if result_size > 1000:
                        self.logger.debug(
                            f"     Result size: {result_size} bytes",
                            extra={"tool_name": tool_name, "result_size": result_size},
                        )

                elif isinstance(result, list):
                    list_length = len(result)
                    self.logger.debug(
                        f"     Result length: {list_length} items",
                        extra={"tool_name": tool_name, "result_length": list_length},
                    )

                    # Log first item preview if available
                    if list_length > 0 and self.logger.isEnabledFor(10):  # DEBUG level
                        first_item = result[0]
                        if isinstance(first_item, dict):
                            self.logger.debug(
                                f"     First item keys: {list(first_item.keys())[:5]}",
                                extra={"tool_name": tool_name},
                            )

                elif isinstance(result, str):
                    preview = result[:100] + "..." if len(result) > 100 else result
                    self.logger.debug(
                        f"     Result preview: {preview}",
                        extra={"tool_name": tool_name, "result_length": len(result)},
                    )
                else:
                    self.logger.debug(
                        f"     Result: {result}",
                        extra={"tool_name": tool_name, "result": result},
                    )

                # Update counts if result indicates failure
                if result_has_error:
                    failed_calls += 1
                    successful_calls -= 1

        # Summary with structured logging
        summary_extra = {
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "total_calls": tool_count,
            "tool_summary": tool_summary,
        }

        if failed_calls > 0:
            self.logger.warning(
                f"🔧 Tool execution summary: {successful_calls} succeeded, {failed_calls} failed",
                extra=summary_extra,
            )
        else:
            self.logger.info(
                f"🔧 Tool execution summary: {successful_calls} succeeded",
                extra=summary_extra,
            )

    def _log_llm_reasoning(self, response, query: str):
        """
        Log detailed LLM reasoning for debugging (only in debug mode).

        This provides insight into how the LLM understood the query,
        which tools it decided to use, and why.

        Logs:
        - Query understanding
        - Tool selection reasoning
        - Response generation approach
        - Internal thoughts (if available)

        Args:
            response: Strands Agent response object
            query: Original user query
        """
        # Only log detailed reasoning in debug mode
        if not self.logger.isEnabledFor(10):  # DEBUG level = 10
            return

        self.logger.debug("=" * 60)
        self.logger.debug("LLM REASONING DETAILS")
        self.logger.debug("=" * 60)

        # Log query
        self.logger.debug(f"Query: {query}")
        self.logger.debug(f"Query length: {len(query)} characters")

        # Log tool selection
        if hasattr(response, "tool_results") and response.tool_results:
            tool_names = [
                getattr(tr, "tool_name", "unknown") for tr in response.tool_results
            ]
            self.logger.debug(f"Tools selected: {tool_names}")
            self.logger.debug(f"Tool call count: {len(tool_names)}")
        else:
            self.logger.debug("Tools selected: None (direct response)")

        # Log response structure
        if hasattr(response, "text"):
            response_length = len(response.text)
            self.logger.debug(f"Response length: {response_length} characters")

            # Log response preview
            if response_length > 0:
                preview_length = min(200, response_length)
                preview = response.text[:preview_length]
                if response_length > preview_length:
                    preview += "..."
                self.logger.debug(f"Response preview: {preview}")

        # Log internal thoughts if available (some LLM frameworks expose this)
        if hasattr(response, "thoughts"):
            self.logger.debug(f"Internal thoughts: {response.thoughts}")

        # Log reasoning steps if available
        if hasattr(response, "reasoning_steps"):
            self.logger.debug("Reasoning steps:")
            for i, step in enumerate(response.reasoning_steps, 1):
                self.logger.debug(f"  {i}. {step}")

        # Log token usage if available
        if hasattr(response, "usage"):
            usage = response.usage
            if isinstance(usage, dict):
                self.logger.debug(f"Token usage: {usage}")
                if "input_tokens" in usage and "output_tokens" in usage:
                    total = usage["input_tokens"] + usage["output_tokens"]
                    self.logger.debug(
                        f"  Input: {usage['input_tokens']}, "
                        f"Output: {usage['output_tokens']}, "
                        f"Total: {total}"
                    )

        # Log model information
        self.logger.debug(f"Model: {self.model_id}")
        self.logger.debug(f"Max tokens: {self.max_tokens}")
        self.logger.debug(f"Temperature: {self.temperature}")

        self.logger.debug("=" * 60)


# ============================================================================
# Helper Functions
# ============================================================================


def create_agentic_agent(
    domain: str,
    agent_name: str,
    tools: list,
    system_prompt: str,
    capabilities: list | None = None,
    config: dict[str, Any] | None = None,
) -> AgenticBaseAgent:
    """
    Factory function to create an agentic agent with minimal boilerplate.

    This is useful for quick prototyping or simple agents that don't need
    a full subclass.

    Args:
        domain: Domain name
        agent_name: Agent name
        tools: List of tool functions
        system_prompt: System prompt string
        capabilities: Optional list of AgentCapability objects (auto-generated if not provided)
        config: Optional configuration

    Returns:
        AgenticBaseAgent instance

    Example:
        @tool(name="search")
        def search(query: str) -> dict:
            return {"results": [...]}

        agent = create_agentic_agent(
            domain="travel",
            agent_name="search-agent",
            tools=[search],
            system_prompt="You are a search agent...",
        )
    """
    from .agent_interface import AgentCapability

    class DynamicAgenticAgent(AgenticBaseAgent):
        def _define_agent_tools(self):
            return tools

        def _get_agent_system_prompt(self):
            return system_prompt

        def _extract_result_data(self, response, **kwargs):
            # Default extraction: collect all tool results
            result_data = {"timestamp": datetime.now(UTC).isoformat()}

            if hasattr(response, "tool_results") and response.tool_results:
                for tool_result in response.tool_results:
                    result_data[tool_result.tool_name] = tool_result.result

            return result_data

        def _define_capabilities(self):
            # If capabilities provided, use them
            if capabilities:
                return capabilities

            # Otherwise, auto-generate basic capability
            return [
                AgentCapability(
                    id=f"{agent_name}-capability",
                    name=f"{agent_name.replace('-', ' ').title()} Capability",
                    description=f"Agentic capability for {agent_name}",
                    tags=["agentic", agent_name],
                    examples=[],
                )
            ]

    return DynamicAgenticAgent(domain, agent_name, config)


__all__ = [
    "AgenticBaseAgent",
    "create_agentic_agent",
    "SYSTEM_PROMPT_TEMPLATE",
    "create_system_prompt_from_template",
]
