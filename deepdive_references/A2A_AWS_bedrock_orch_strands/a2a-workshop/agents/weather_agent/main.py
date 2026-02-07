#!/usr/bin/env python3
"""
Weather Agent - Travel Domain

Provides weather forecasts and indoor/outdoor activity recommendations.

Key Learning Objective:
    This agent demonstrates how adding weather context changes orchestration behavior.

    Module 2 (Baseline): No WeatherAgent → Mix of indoor/outdoor suggestions
    Module 3 (With Weather): WeatherAgent deployed → Indoor-only for rainy days

Design:
    - Uses mock data by default (rainy Seattle for demonstration)
    - Optional integration with OpenWeatherMap API
    - Returns indoor/outdoor recommendation flag
    - Includes 3-day forecast

Example Query:
    "What's the weather in Seattle?"
    "Is it good weather for outdoor activities in Seattle?"

Mock Data Location:
    data/mock/weather/locations.json
"""

from datetime import UTC, datetime
from typing import Any

from a2a.types import Task

from lib.agents import AgentCapability, BaseAgent
from lib.agents.config_loader import get_agent_config, load_domain_config
from lib.agents.mock_data_factory import MockDataFactory


class WeatherAgent(BaseAgent):
    """
    Weather forecasting agent with indoor/outdoor recommendations.

    Single Capability:
        - get-weather: Weather forecast including today and upcoming days

    Service Type:
        Primary - Returns weather data with indoor/outdoor recommendations

    Data Sources:
        - Mock data (default): Pedagogically-designed data for workshops
        - OpenWeatherMap API (optional): Real weather data via API key

    Configuration:
        Environment Variables:
            - OPENWEATHER_API_KEY: API key for OpenWeatherMap (optional)
            - WEATHER_DATA_SOURCE: "mock" or "openweathermap" (default: mock)
    """

    def __init__(
        self,
        domain: str = "travel",
        agent_name: str = "weather-agent",
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize WeatherAgent.

        Args:
            domain: Domain name (default: "travel")
            agent_name: Agent name (default: "weather-agent")
            config: Optional configuration override
        """
        super().__init__(domain, agent_name, config)

        # Load domain configuration
        try:
            domain_config = load_domain_config(domain)
            agent_config = get_agent_config(domain_config, "weather")
            self.agent_config = agent_config.config
            self.data_sources = agent_config.data_sources
        except Exception as e:
            self.logger.warning(
                f"Could not load domain config: error={e!s} fallback='Using default configuration'"
            )
            self.agent_config = {}
            self.data_sources = []

        # Initialize mock data factory
        self.mock_factory = MockDataFactory(domain)

        # Configuration
        self.forecast_days = self.agent_config.get("forecast_days", 3)
        self.include_indoor_recommendation = self.agent_config.get(
            "include_indoor_recommendation", True
        )

        self.logger.info(
            f"Weather agent configured: "
            f"forecast_days={self.forecast_days} "
            f"note='Using mock data for workshop demonstration'"
        )

    def _define_capabilities(self) -> list[AgentCapability]:
        """
        Define weather agent capabilities.

        Returns:
            List of AgentCapability objects
        """
        return [
            AgentCapability(
                id="get-weather",
                name="Get Weather",
                description="Get weather forecast for a location including today and upcoming days. Returns forecast array with indoor/outdoor recommendations.",
                tags=[
                    "weather",
                    "forecast",
                    "temperature",
                    "conditions",
                    "travel",
                    "planning",
                ],
                examples=[
                    "What's the weather in Seattle?",
                    "Is it raining in Portland?",
                    "What's the forecast for San Francisco?",
                    "What will the weather be like this weekend?",
                ],
                input_schema={
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"},
                        "days": {
                            "type": "number",
                            "description": "Number of forecast days (default: 3)",
                            "default": 3,
                        },
                    },
                    "required": ["location"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "forecast": {
                            "type": "array",
                            "description": "Weather forecast including today",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "date": {
                                        "type": "string",
                                        "description": "Date of forecast",
                                    },
                                    "condition": {
                                        "type": "string",
                                        "description": "Weather condition",
                                    },
                                    "high": {
                                        "type": "number",
                                        "description": "High temperature (°F)",
                                    },
                                    "low": {
                                        "type": "number",
                                        "description": "Low temperature (°F)",
                                    },
                                    "precipitation_chance": {
                                        "type": "number",
                                        "description": "Chance of precipitation (%)",
                                    },
                                    "indoor_recommended": {
                                        "type": "boolean",
                                        "description": "Whether indoor activities are recommended",
                                    },
                                },
                            },
                        },
                        "location": {"type": "string", "description": "City name"},
                    },
                },
            ),
        ]

    def _process_task_impl(self, task: Task, user_input: dict[str, Any]) -> Task:
        """
        Process weather task - returns weather forecast including today.

        This agent has a single capability: get-weather.
        It returns a forecast array including today and upcoming days with indoor/outdoor recommendations.

        Args:
            task: A2A Task object
            user_input: Extracted user input with location and query

        Returns:
            Updated task with weather forecast data
        """
        # 📥 INLINE LOGGING - Log what we received (extra={} doesn't show in CloudWatch)
        import json

        user_input_preview = json.dumps(user_input, default=str)[:300]
        self.logger.info(
            f"📥 WEATHER INPUT - Received: task_id={task.id} input_keys={list(user_input.keys())} preview={user_input_preview}"
        )

        # Extract parameters
        location = user_input.get("location", "Seattle")
        days = int(user_input.get("days", self.forecast_days))  # Convert to int
        user_query = user_input.get("query", "")

        self.logger.info(
            f"📥 WEATHER INPUT - Extracted: location={location} days={days} user_query={user_query[:100]}"
        )

        # Directly perform weather forecast retrieval (single capability)
        return self._get_weather(task, location, days)

    def _get_weather(self, task: Task, location: str, days: int = 3) -> Task:
        """
        Get weather forecast including today for a location.

        Args:
            task: A2A Task
            location: City name
            days: Number of forecast days (default: 3)

        Returns:
            Task with weather forecast data
        """
        try:
            self.logger.info(
                f"🌤️ Getting weather forecast: "
                f"operation=get_weather "
                f"location={location} "
                f"days={days} "
                f"note='Fetching forecast including today with indoor/outdoor recommendations'"
            )

            # Get weather data
            weather_data = self._fetch_weather_data(location)

            if not weather_data:
                return self._create_error_task(
                    task, f"Weather data not available for {location}"
                )

            # Get forecast data
            forecast = weather_data.get("forecast", [])

            # Limit to requested days
            forecast = forecast[:days]

            # Ensure each forecast item has indoor_recommended flag
            for day in forecast:
                if "indoor_recommended" not in day:
                    # Calculate based on precipitation chance
                    precip = day.get("precipitation_chance", 0)
                    day["indoor_recommended"] = precip > 60

            # Format response
            response_text = f"Weather Forecast for {location}:\n\n"

            for idx, day in enumerate(forecast):
                date = day.get("date", "Unknown")
                condition = day.get("condition", "Unknown")
                high = day.get("high", 0)
                low = day.get("low", 0)
                precip = day.get("precipitation_chance", 0)
                indoor_rec = day.get("indoor_recommended", False)

                day_label = "Today" if idx == 0 else date

                response_text += (
                    f"📅 {day_label}\n"
                    f"   {condition} | High: {high}°F, Low: {low}°F | Rain: {precip}%\n"
                )

                if indoor_rec:
                    response_text += "   💧 Indoor activities recommended\n"
                else:
                    response_text += "   ☀️ Good for outdoor activities\n"

                response_text += "\n"

            # Add overall recommendation
            avg_precip = (
                sum(day.get("precipitation_chance", 0) for day in forecast)
                / len(forecast)
                if forecast
                else 0
            )
            if avg_precip > 60:
                response_text += (
                    "💧 Overall: Plan for indoor activities due to likely rain."
                )
            else:
                response_text += (
                    "☀️ Overall: Generally good weather for outdoor activities!"
                )

            # Structure data for other agents
            result_data = {
                "location": location,
                "forecast": forecast,
                "average_precipitation": avg_precip,
                "indoor_recommended": avg_precip > 60,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            self.logger.info(
                f"✅ WEATHER OUTPUT - Weather forecast retrieved: "
                f"task_id={task.id} "
                f"location={location} "
                f"forecast_days={len(forecast)} "
                f"avg_precipitation={avg_precip} "
                f"indoor_recommended={avg_precip > 60} "
                f"result_keys={list(result_data.keys())}"
            )

            return self._create_success_task(task, response_text, result_data)

        except Exception as e:
            return self._create_error_task(task, f"Weather lookup failed: {e!s}")

    def _fetch_weather_data(self, location: str) -> dict[str, Any]:
        """
        Fetch weather data from configured source.

        Args:
            location: City name

        Returns:
            Weather data dictionary
        """
        self.logger.info(
            f"📊 Fetching weather data: "
            f"operation=fetch_weather_data "
            f"location={location} "
            f"note='Using mock data for workshop demonstration'"
        )

        # Always use mock data for workshop
        data = self.mock_factory.get_weather(location)
        has_forecast = "forecast" in data if data else False
        self.logger.info(
            f"✓ Mock weather data loaded: "
            f"location={location} "
            f"has_forecast={has_forecast} "
            f"note='Mock data includes pedagogically-designed rainy Seattle scenario'"
        )
        return data


# ============================================================================
# Standard Entry Points for Agent Launcher
# ============================================================================


def get_agent() -> WeatherAgent:
    """
    Create and return WeatherAgent instance.

    Called by agent_launcher.py to initialize the agent.

    Returns:
        WeatherAgent instance
    """
    agent = WeatherAgent()
    agent.initialize()
    return agent


def get_http_app(agent: WeatherAgent):
    """
    Create and return FastAPI app for WeatherAgent.

    Called by agent_launcher.py to initialize HTTP server.

    Args:
        agent: WeatherAgent instance

    Returns:
        FastAPI application instance
    """
    from datetime import datetime
    import json

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Weather Agent", version="1.0.0")

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {
            "status": "ok",
            "agent": "weather-agent",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    @app.get("/.well-known/agent.json")
    async def agent_card():
        """Agent card endpoint (A2A protocol)"""
        card = agent.get_agent_card()
        return JSONResponse(card)  # card is already a dict with enriched schemas

    @app.post("/message/send")
    async def handle_task(request: Request):
        """
        A2A message handler endpoint.

        Processes incoming tasks and returns results.
        """
        try:
            body = await request.body()
            body = body.decode("utf-8") if isinstance(body, bytes) else body
            body_json = json.loads(body)

            # A2A envelope unwrapping
            if (
                "method" in body_json
                and "params" in body_json
                and "message" in body_json["params"]
            ):
                task_dict = body_json["params"]["message"]
            else:
                task_dict = body_json

            # Process task
            from a2a.types import Task

            task = Task.model_validate(task_dict)
            result_task = agent.process_task(task)

            return result_task.model_dump(mode="json")

        except Exception as e:
            import traceback

            traceback.print_exc()

            # Create error task
            import uuid

            from a2a.types import (
                Message,
                Task,
                TaskState,
                TaskStatus,
                TextPart,
            )

            error_message = Message(
                role="agent",
                parts=[TextPart(kind="text", text=f"Error: {e!s}", metadata={})],
                message_id=str(uuid.uuid4()),
                kind="message",
                task_id=str(uuid.uuid4()),
            )

            error_task = Task(
                id=str(uuid.uuid4()),
                status=TaskStatus(
                    state=TaskState.failed,
                    message=error_message,
                    timestamp=datetime.now(UTC).isoformat() + "Z",
                ),
                kind="task",
            )

            return error_task.model_dump(mode="json")

    return app


if __name__ == "__main__":
    # For local testing
    from lib.logger import get_logger

    logger = get_logger(context={"component": "main"})

    logger.info("🚀 Starting WeatherAgent...")
    agent = get_agent()

    logger.info(
        "✓ Agent initialized",
    )

    for cap in agent.capabilities:
        logger.info(f"  Capability: {cap.id}")
