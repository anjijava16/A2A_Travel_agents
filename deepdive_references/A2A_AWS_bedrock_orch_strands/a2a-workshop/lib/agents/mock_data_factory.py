#!/usr/bin/env python3
"""
Mock Data Factory

Provides mock data for agents to ensure reliable workshop experience
without external API dependencies.

Design Philosophy:
    - Pedagogically-designed data to demonstrate agent orchestration
    - Weather data shows clear indoor/outdoor activity filtering
    - Events data has mix of weather-dependent and weather-independent options
    - Consistent, predictable responses for learning

Example Usage:
    >>> factory = MockDataFactory("travel")
    >>> weather = factory.get_weather("Seattle")
    >>> print(weather["condition"])
    "Heavy Rain"
"""

from datetime import UTC
import json
from pathlib import Path
from typing import Any

from lib.logger import get_logger

logger = get_logger()


class MockDataFactory:
    """
    Factory for loading mock data from JSON files.

    Supports domain-agnostic data loading with fallback to defaults.
    """

    def __init__(self, domain: str, data_dir: str | None = None):
        """
        Initialize mock data factory.

        Args:
            domain: Domain name (e.g., "travel", "financial")
            data_dir: Optional custom data directory (defaults to data/mock/)
        """
        self.domain = domain

        if data_dir is None:
            project_root = Path(__file__).parent.parent.parent
            self.data_dir = project_root / "data" / "mock"
        else:
            self.data_dir = Path(data_dir)

        self._cache: dict[str, Any] = {}

    def load_data(self, data_type: str, key: str | None = None) -> Any:
        """
        Load mock data from JSON file.

        Args:
            data_type: Type of data (e.g., "weather", "events", "restaurants")
            key: Optional specific key to return from loaded data

        Returns:
            Loaded mock data (dict, list, or specific value if key provided)

        Example:
            >>> factory.load_data("weather", "Seattle")
            {"condition": "Heavy Rain", "temperature": 52, ...}
        """
        # Check cache first
        cache_key = f"{data_type}:{key}" if key else data_type
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Load from file
        data_file = self.data_dir / data_type / "locations.json"

        if not data_file.exists():
            # Return empty default
            return {} if key else []

        with open(data_file) as f:
            data = json.load(f)

        # Cache full data
        self._cache[data_type] = data

        # Return specific key if requested
        if key:
            result = data.get(key, {})
            self._cache[cache_key] = result
            return result

        return data

    def _normalize_weather_dates(self, weather_data: dict[str, Any]) -> dict[str, Any]:
        """
        Replace hardcoded dates with dates relative to today.

        Args:
            weather_data: Weather data with hardcoded dates

        Returns:
            Weather data with current dates
        """
        from datetime import datetime, timedelta

        today = datetime.now(UTC)
        weather_data["date"] = today.strftime("%Y-%m-%d")

        if "forecast" in weather_data:
            for idx, day in enumerate(weather_data["forecast"]):
                forecast_date = today + timedelta(days=idx)
                day["date"] = forecast_date.strftime("%Y-%m-%d")

        return weather_data

    def get_weather(self, location: str = "Seattle") -> dict[str, Any]:
        """
        Get weather mock data for a location with current dates.

        Returns:
            Weather data with condition, temperature, forecast, etc.
        """
        data = self.load_data("weather", location)
        return self._normalize_weather_dates(data)

    def get_events(self, location: str = "Seattle") -> list[dict[str, Any]]:
        """
        Get events mock data for a location.

        Returns:
            Flat list of events with category field from OSM
        """
        return self.load_data("events", location)

    def get_restaurants(self, location: str = "Seattle") -> list[dict[str, Any]]:
        """
        Get restaurant mock data for a location.

        Returns:
            Flat list of restaurants with dietary/amenity fields from OSM
        """
        return self.load_data("restaurants", location)

    def get_budget_data(self, location: str = "Seattle") -> dict[str, Any]:
        """
        Get budget/cost mock data for a location.

        Returns:
            Cost data for accommodations, dining, activities
        """
        return self.load_data("budget", location)

    def get_transportation(self, location: str = "Seattle") -> dict[str, Any]:
        """
        Get transportation options for a location.

        Returns:
            Transportation data including public transit, rideshare, etc.
        """
        return self.load_data("transportation", location)

    def get_accommodations(self, location: str = "Seattle") -> dict[str, Any]:
        """
        Get accommodation options for a location.

        Returns:
            Accommodation data by budget category
        """
        return self.load_data("accommodations", location)

    def get_services(self, location: str = "Seattle") -> dict[str, Any]:
        """
        Get local services for a location.

        Returns:
            Service data including healthcare, banking, emergency
        """
        return self.load_data("services", location)

    def get_entertainment(self, location: str = "Seattle") -> dict[str, Any]:
        """
        Get entertainment venues for a location.

        Returns:
            Entertainment data including theater, music venues, cinema
        """
        return self.load_data("entertainment", location)

    def get_shopping(self, location: str = "Seattle") -> dict[str, Any]:
        """
        Get shopping options for a location.

        Returns:
            Shopping data including malls, markets, specialty stores
        """
        return self.load_data("shopping", location)

    def get_outdoor_activities(self, location: str = "Seattle") -> dict[str, Any]:
        """
        Get outdoor activities for a location.

        Returns:
            Outdoor activity data including parks, trails, water activities
        """
        return self.load_data("outdoor", location)

    def get_food_tours(self, location: str = "Seattle") -> dict[str, Any]:
        """
        Get food tours and culinary experiences for a location.

        Returns:
            Food tour data including tours, cooking classes, brewery tours
        """
        return self.load_data("food_tours", location)

    def get_safety_info(self, location: str = "Seattle") -> dict[str, Any]:
        """
        Get safety and accessibility information for a location.

        Returns:
            Safety data including ratings, concerns, accessibility
        """
        return self.load_data("safety", location)

    def get_seasonal_info(self, location: str = "Seattle") -> dict[str, Any]:
        """
        Get seasonal information for a location.

        Returns:
            Seasonal data including peak seasons, crowd levels, pricing
        """
        return self.load_data("seasonal", location)

    def get_itinerary_templates(self, theme: str | None = None) -> Any:
        """
        Get itinerary templates.

        Args:
            theme: Optional theme filter (e.g., "romantic_weekend", "family_adventure")

        Returns:
            Itinerary template(s)
        """
        data_file = self.data_dir / "itineraries" / "templates.json"

        if not data_file.exists():
            return {}

        with open(data_file) as f:
            data = json.load(f)

        if theme:
            return data.get(theme, {})

        return data

    def get_agent_capabilities(self) -> dict[str, Any]:
        """
        Get agent capabilities matrix for ADK workflows.

        Returns:
            Agent capabilities including keywords, confidence, dependencies
        """
        data_file = self.data_dir / "agent_capabilities" / "matrix.json"

        if not data_file.exists():
            return {}

        with open(data_file) as f:
            return json.load(f)

    def get_workflow_patterns(self) -> dict[str, Any]:
        """
        Get workflow pattern examples for ADK.

        Returns:
            Workflow pattern examples with queries and expected patterns
        """
        data_file = self.data_dir / "workflow_patterns" / "examples.json"

        if not data_file.exists():
            return {}

        with open(data_file) as f:
            return json.load(f)

    def get_user_personas(self, persona: str | None = None) -> Any:
        """
        Get user persona profiles for testing.

        Args:
            persona: Optional persona name (e.g., "budget_traveler")

        Returns:
            Persona profile(s)
        """
        data_file = self.data_dir / "personas" / "profiles.json"

        if not data_file.exists():
            return {}

        with open(data_file) as f:
            data = json.load(f)

        if persona:
            return data.get(persona, {})

        return data


def create_default_mock_data():
    """
    Create default mock data files for workshop.

    This function generates pedagogically-designed mock data that demonstrates
    the key learning objective: weather-aware agent orchestration.
    """
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data" / "mock"

    # Weather data (rainy for Seattle to demonstrate filtering)
    weather_dir = data_dir / "weather"
    weather_dir.mkdir(parents=True, exist_ok=True)

    weather_data = {
        "Seattle": {
            "city": "Seattle",
            "date": "2024-10-15",
            "condition": "Heavy Rain",
            "temperature": 52,
            "precipitation_chance": 95,
            "humidity": 90,
            "description": "Continuous heavy rain expected all day. Not suitable for outdoor activities.",
            "indoor_recommended": True,
            "forecast": [
                {
                    "date": "2024-10-15",
                    "condition": "Heavy Rain",
                    "high": 54,
                    "low": 48,
                    "precipitation_chance": 95,
                },
                {
                    "date": "2024-10-16",
                    "condition": "Rain",
                    "high": 56,
                    "low": 50,
                    "precipitation_chance": 80,
                },
                {
                    "date": "2024-10-17",
                    "condition": "Partly Cloudy",
                    "high": 60,
                    "low": 52,
                    "precipitation_chance": 30,
                },
            ],
        },
        "Portland": {
            "city": "Portland",
            "condition": "Rain",
            "temperature": 55,
            "precipitation_chance": 85,
            "indoor_recommended": True,
        },
        "San Francisco": {
            "city": "San Francisco",
            "condition": "Sunny",
            "temperature": 68,
            "precipitation_chance": 10,
            "indoor_recommended": False,
        },
    }

    with open(weather_dir / "locations.json", "w") as f:
        json.dump(weather_data, f, indent=2)

    # Events data (mix of indoor/outdoor)
    events_dir = data_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)

    events_data = {
        "Seattle": {
            "outdoor_events": [
                {
                    "name": "Pike Place Market Tour",
                    "type": "outdoor",
                    "weather_dependent": True,
                    "description": "Walking tour of historic market",
                    "duration": "2 hours",
                    "price": 25,
                },
                {
                    "name": "Hiking at Discovery Park",
                    "type": "outdoor",
                    "weather_dependent": True,
                    "description": "Scenic trails with Puget Sound views",
                    "duration": "3 hours",
                    "price": 0,
                },
                {
                    "name": "Waterfront Walk",
                    "type": "outdoor",
                    "weather_dependent": True,
                    "description": "Stroll along Seattle's waterfront",
                    "duration": "1.5 hours",
                    "price": 0,
                },
            ],
            "indoor_events": [
                {
                    "name": "Space Needle",
                    "type": "indoor",
                    "weather_dependent": False,
                    "description": "Iconic observation tower with city views",
                    "duration": "1.5 hours",
                    "price": 35,
                },
                {
                    "name": "Chihuly Garden and Glass",
                    "type": "indoor",
                    "weather_dependent": False,
                    "description": "Stunning glass art exhibition",
                    "duration": "2 hours",
                    "price": 30,
                },
                {
                    "name": "Seattle Aquarium",
                    "type": "indoor",
                    "weather_dependent": False,
                    "description": "Marine life exhibits and touch tanks",
                    "duration": "2 hours",
                    "price": 30,
                },
                {
                    "name": "Museum of Pop Culture",
                    "type": "indoor",
                    "weather_dependent": False,
                    "description": "Interactive music and sci-fi museum",
                    "duration": "2.5 hours",
                    "price": 33,
                },
            ],
        }
    }

    with open(events_dir / "locations.json", "w") as f:
        json.dump(events_data, f, indent=2)

    # Restaurant data
    restaurants_dir = data_dir / "restaurants"
    restaurants_dir.mkdir(parents=True, exist_ok=True)

    restaurants_data = {
        "Seattle": {
            "restaurants": [
                {
                    "name": "Pike Place Chowder",
                    "type": "indoor",
                    "cuisine": "seafood",
                    "rating": 4.7,
                    "price": "$$",
                },
                {
                    "name": "Toulouse Petit",
                    "type": "indoor",
                    "cuisine": "cajun",
                    "rating": 4.5,
                    "price": "$$",
                },
                {
                    "name": "The Pink Door",
                    "type": "indoor",
                    "cuisine": "italian",
                    "rating": 4.6,
                    "price": "$$$",
                },
                {
                    "name": "Serious Pie",
                    "type": "indoor",
                    "cuisine": "pizza",
                    "rating": 4.4,
                    "price": "$$",
                },
                {
                    "name": "Local 360",
                    "type": "indoor",
                    "cuisine": "american",
                    "rating": 4.3,
                    "price": "$$",
                },
            ]
        }
    }

    with open(restaurants_dir / "locations.json", "w") as f:
        json.dump(restaurants_data, f, indent=2)

    logger.info("✓ Created default mock data files")
    logger.info(f"  - {weather_dir / 'locations.json'}")
    logger.info(f"  - {events_dir / 'locations.json'}")
    logger.info(f"  - {restaurants_dir / 'locations.json'}")


if __name__ == "__main__":
    # Run this to generate mock data files
    create_default_mock_data()
