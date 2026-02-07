#!/usr/bin/env python3
"""
Geography Agent - Travel Domain Enhancement Service

A pure enhancement service that filters locations by proximity to a center point.

Key Learning Objective:
    This agent demonstrates the ENHANCEMENT SERVICE pattern with a single, focused capability.

    - Acts as a supporting service for other agents (not user-facing)
    - Enables proximity-based filtering ("near", "nearby", "within X km")
    - Shows how agents can provide specialized cross-cutting concerns
    - Single Responsibility: proximity filtering only

Design:
    - Service Type: Enhancement (pure supporting service)
    - Single Capability: filter-by-proximity
    - Provides For: restaurant-agent, events-agent, accommodation-agent
    - Uses haversine formula for distance calculation
    - Returns filtered locations enriched with distance data

Example Usage (via orchestrator workflows):
    1. Events agent returns events with coordinates
    2. Geography agent filters events within 2km of Space Needle
    3. Orchestrator synthesizes filtered results

Architecture Pattern:
    User Query → Orchestrator → [Events Agent] → [Geography Agent] → Synthesis

    The orchestrator:
    - Calls events/restaurant agent to get locations with coordinates
    - Calls geography agent to filter by proximity to landmark
    - Geography agent uses LANDMARKS dict internally (not exposed as capability)

Mock Data:
    Events/restaurants already include latitude/longitude in their mock data.
    Geography agent doesn't need to look up coordinates - just filters.
"""

from datetime import UTC, datetime
import json
import math
import os
from typing import Any

from a2a.types import Task

from lib.agents import AgentCapability, BaseAgent
from lib.agents.config_loader import get_agent_config, load_domain_config
from lib.agents.mock_data_factory import MockDataFactory


class GeographyAgent(BaseAgent):
    """
    Pure enhancement service for proximity filtering.

    Single Capability:
        - filter-by-proximity: Filter locations within radius of a center point

    Service Type:
        Enhancement - Pure supporting service that enhances other agents' data.
        Does NOT directly answer user queries. Works as part of workflows where:
        1. Primary agent (events/restaurants) returns locations with coordinates
        2. Geography agent filters those locations by proximity
        3. Orchestrator synthesizes the filtered results

    Design Philosophy:
        Single Responsibility - This agent ONLY filters locations by distance.
        It does not look up coordinates or calculate arbitrary distances.
        The orchestrator embeds landmark coordinates directly in workflows.

    Configuration:
        Environment Variables:
            - DEFAULT_RADIUS_KM: Default search radius in km (default: 2.0)
            - MAX_RADIUS_KM: Maximum allowed radius in km (default: 50.0)
    """

    # Landmark resolution now happens dynamically by searching data files
    # No hardcoded LANDMARKS dict needed - searches events, restaurants, accommodations

    def __init__(
        self,
        domain: str = "travel",
        agent_name: str = "geography-agent",
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize GeographyAgent.

        Args:
            domain: Domain name (default: "travel")
            agent_name: Agent name (default: "geography-agent")
            config: Optional configuration override
        """
        super().__init__(domain, agent_name, config)

        # Load domain configuration
        try:
            domain_config = load_domain_config(domain)
            agent_config = get_agent_config(domain_config, "geography")
            self.agent_config = agent_config.config
        except Exception as e:
            self.logger.warning(
                f"Could not load domain config: error={e!s} fallback='Using default configuration'"
            )
            self.agent_config = {}

        # Initialize mock data factory
        self.mock_factory = MockDataFactory(domain)

        # Configuration
        self.default_radius_km = float(os.getenv("DEFAULT_RADIUS_KM", "2.0"))
        self.max_radius_km = float(os.getenv("MAX_RADIUS_KM", "50.0"))

        provides_for_list = ["restaurant-agent", "events-agent", "accommodation-agent"]
        self.logger.info(
            f"Geography agent configured: "
            f"default_radius_km={self.default_radius_km} "
            f"max_radius_km={self.max_radius_km} "
            f"landmark_resolution=dynamic "
            f"service_type=enhancement "
            f"provides_for={provides_for_list}"
        )

    def _define_capabilities(self) -> list[AgentCapability]:
        """
        Define geography agent capabilities.

        Returns:
            List of AgentCapability objects (single capability: proximity filtering)
        """
        return [
            AgentCapability(
                id="filter-by-proximity",
                name="Filter by Proximity",
                description="""Spatial filtering agent. I filter locations by proximity to landmarks.

I apply OBJECTIVE SPATIAL FILTERING using coordinate-based distance calculation.
Use me after location loading to reduce datasets by geographic relevance.

USAGE: Use me after location-loader to filter by distance.
I do objective filtering (hard data: coordinates + haversine distance).

WORKFLOW:
1. Receive: locations array from location-loader
2. Resolve: landmark coordinates (e.g., "Pike Place Market" → lat/lon) dynamically via _resolve_landmark_dynamically
3. Filter: calculate distance using haversine, keep only within radius
4. Return: filtered_locations (spatially-filtered subset, sorted by distance)

EFFICIENCY NOTE:
Filter 2,000 locations → 20 relevant ones (me, objective/fast),
then select best 10 (LLM, subjective/thoughtful).
This is more efficient than LLM reasoning about all 2,000.

WHY OBJECTIVE FIRST:
Distance calculation is deterministic and fast. Apply objective filters before
subjective selection to reduce cognitive load on LLM synthesis.""",
                tags=[
                    "geography",
                    "proximity",
                    "nearby",
                    "location",
                    "filtering",
                    "enhancement",
                    "spatial-filter",
                    "objective-filter",
                    "hard-data",
                ],
                examples=[
                    "Find restaurants near Pike Place Market",
                    "What's within 2km of downtown?",
                    "Show me events close to my location",
                    "Filter events within walking distance",
                ],
                input_schema={
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "Center point latitude",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "Center point longitude",
                        },
                        "radius_km": {
                            "type": "number",
                            "description": "Search radius in kilometers",
                            "default": 2.0,
                        },
                        "locations": {
                            "type": "array",
                            "description": "Array of locations with lat/lon to filter",
                            "items": {"type": "object"},
                        },
                        "location_name": {
                            "type": "string",
                            "description": "The specific place, landmark, or neighborhood mentioned in the user's query for proximity filtering (e.g., what comes after 'near' or 'close to'). Required if latitude/longitude not provided.",
                        },
                    },
                    "required": ["locations"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "filtered_locations": {
                            "type": "array",
                            "description": "Locations within radius, enriched with distance",
                        },
                        "center_point": {"type": "object"},
                        "radius_km": {"type": "number"},
                        "total_found": {"type": "number"},
                    },
                },
                service_type="enhancement",
                provides_for=[
                    "restaurant-agent",
                    "events-agent",
                    "accommodation-agent",
                ],
            ),
        ]

    def _resolve_landmark_dynamically(
        self, landmark_name: str
    ) -> tuple[float, float] | None:
        """
        Search for landmark coordinates across all data files dynamically.

        Instead of maintaining a hardcoded LANDMARKS dict, this method searches
        through events, restaurants, and accommodations data files for venues
        matching the landmark name.

        Args:
            landmark_name: Name of landmark (e.g., "Pike Place Market", "Space Needle")

        Returns:
            (latitude, longitude) tuple if found, else None
        """
        landmark_lower = landmark_name.lower()
        self.logger.debug(
            f"🔍 Dynamic landmark search: searching for '{landmark_name}' across data files"
        )

        # Search across all category data files
        for category in ["events", "restaurants", "accommodations"]:
            try:
                # Load all data for this category (all cities)
                data = self.mock_factory.load_data(category)

                if not data:
                    continue

                # Search through all cities in this category
                for city_name, city_data in data.items():
                    if not city_data:
                        continue

                    # Handle different data structures
                    venues = []
                    if isinstance(city_data, list):
                        venues = city_data
                    elif isinstance(city_data, dict):
                        # Old nested structure - flatten all venue lists
                        for key, value in city_data.items():
                            if isinstance(value, list):
                                venues.extend(value)

                    # Search venues for matching name
                    for venue in venues:
                        if not isinstance(venue, dict):
                            continue

                        venue_name = venue.get("name", "").lower()
                        if landmark_lower in venue_name or venue_name in landmark_lower:
                            lat = venue.get("latitude")
                            lon = venue.get("longitude")

                            if lat is not None and lon is not None:
                                self.logger.info(
                                    f"✅ Dynamic landmark resolved: '{landmark_name}' → '{venue.get('name')}' "
                                    f"(lat={lat}, lon={lon}, city={city_name}, category={category})"
                                )
                                return (float(lat), float(lon))

            except Exception as e:
                self.logger.debug(
                    f"⚠️ Error searching {category} data: {e}", exc_info=True
                )
                continue

        self.logger.warning(
            f"❌ Landmark not found: '{landmark_name}' not found in any data files"
        )
        return None

    def _process_task_impl(self, task: Task, user_input: dict[str, Any]) -> Task:
        """
        Process geography task - performs proximity filtering only.

        This agent has a single capability: filter-by-proximity.
        It takes a list of locations and filters them by distance from a center point.

        Args:
            task: A2A Task object
            user_input: Extracted user input with latitude, longitude, locations, etc.

        Returns:
            Updated task with filtered locations
        """
        # Log task input with FULL details

        self.logger.info(
            f"📥 GEOGRAPHY INPUT - user_input keys: {list(user_input.keys())}"
        )
        self.logger.debug(
            f"📥 GEOGRAPHY INPUT - FULL DATA: {json.dumps(user_input, indent=2)[:100]}..."
        )

        # Directly perform proximity filtering (single capability)
        return self._filter_by_proximity_task(task, user_input)

    def _filter_by_proximity_task(self, task: Task, user_input: dict[str, Any]) -> Task:
        """
        Filter locations by proximity to a center point.

        This is the agent's single capability. It receives:
        - latitude/longitude: Center point coordinates
        - locations: Array of locations with lat/lon to filter
        - radius_km: Optional search radius (default: 2.0km)

        Returns filtered locations enriched with distance information.
        """
        try:
            # Extract parameters (using latitude/longitude to match get-coordinates output)
            center_lat = (
                float(user_input.get("latitude"))
                if user_input.get("latitude")
                else None
            )
            center_lon = (
                float(user_input.get("longitude"))
                if user_input.get("longitude")
                else None
            )
            radius_km = float(
                user_input.get("radius_km", self.default_radius_km)
            )  # Convert to float
            locations = user_input.get("locations", [])

            self.logger.debug(
                f"📍 Proximity filtering - received inputs: "
                f"has_center_lat={center_lat is not None} "
                f"has_center_lon={center_lon is not None} "
                f"locations_count={len(locations)} "
                f"user_input_keys={list(user_input.keys())}"
            )

            # 📚 EDUCATIONAL: Explain enhancement agent role
            self.logger.debug(
                f"💡 Strategy: Acting as enhancement agent to filter {len(locations)} locations "
                f"by proximity using radius={radius_km}km"
            )

            # Try to resolve place name to coordinates if no coordinates given
            if not center_lat or not center_lon:
                place_name = user_input.get("location_name", "")

                self.logger.debug(
                    f"🔍 No coordinates provided, attempting place name resolution. explicit_place_name={place_name or 'none'}, user_input_keys={list(user_input.keys())}"
                )

                # If no explicit place_name, extract from query
                if not place_name:
                    user_query = user_input.get("query", "")

                    self.logger.debug(
                        f"🔍 Extracting place name from query: user_query={user_query[:100] if user_query else 'none'}"
                    )

                    # Try common proximity keywords
                    proximity_keywords = ["near", "close to", "around", "by", "at"]
                    for keyword in proximity_keywords:
                        if keyword in user_query.lower():
                            # Extract text after keyword
                            parts = user_query.lower().split(keyword, 1)
                            if len(parts) > 1:
                                # Get next 3-5 words as potential place name
                                words = parts[1].strip().split()[:5]
                                place_name = " ".join(words).rstrip(".,?!")
                                self.logger.debug(
                                    f"✓ Extracted place name from '{keyword}': {place_name}"
                                )
                                break

                if place_name:
                    self.logger.debug(
                        f"🔍 Attempting dynamic resolution for: '{place_name}'"
                    )

                    # Use dynamic landmark resolution
                    coords = self._resolve_landmark_dynamically(place_name)

                    if coords:
                        center_lat, center_lon = coords
                        self.logger.debug(
                            f"✅ Resolved place name '{place_name}' to coordinates: lat={center_lat}, lon={center_lon}"
                        )
                    else:
                        self.logger.error(
                            f"❌ Unknown place: '{place_name}' not found in data files"
                        )
                        return self._create_error_task(
                            task,
                            f"Unknown place: {place_name}. Could not find coordinates in available data.",
                        )
                else:
                    self.logger.error("❌ Could not identify location from query")
                    return self._create_error_task(
                        task,
                        "Could not identify location from query. Please specify a known landmark or venue.",
                    )

            center_lat = float(center_lat)
            center_lon = float(center_lon)
            radius_km = min(float(radius_km), self.max_radius_km)

            locations_sample = locations[:2] if locations else []
            self.logger.debug(
                f"🔍 Starting proximity filtering: "
                f"center_lat={center_lat} "
                f"center_lon={center_lon} "
                f"radius_km={radius_km} "
                f"locations_count={len(locations)} "
                f"locations_sample={locations_sample}"
            )

            # Filter locations by proximity
            filtered = []
            for loc in locations:
                if "latitude" not in loc or "longitude" not in loc:
                    self.logger.debug(
                        f"Skipping location without coordinates: {loc.get('name', 'unknown')}"
                    )
                    continue

                distance_km = self._haversine_distance(
                    center_lat,
                    center_lon,
                    float(loc["latitude"]),
                    float(loc["longitude"]),
                )

                self.logger.debug(
                    f"Distance to {loc.get('name', 'unknown')}: {distance_km:.2f} km"
                )

                if distance_km <= radius_km:
                    # Enrich with distance information
                    enriched_loc = {**loc}
                    enriched_loc["distance_km"] = round(distance_km, 2)
                    enriched_loc["distance_miles"] = round(distance_km * 0.621371, 2)
                    filtered.append(enriched_loc)

            # Sort by distance (closest first)
            filtered.sort(key=lambda x: x["distance_km"])

            result_data = {
                "filtered_locations": filtered,
                "center_point": {"latitude": center_lat, "longitude": center_lon},
                "radius_km": radius_km,
                "total_found": len(filtered),
                "original_count": len(locations),
            }

            response_text = (
                f"Found {len(filtered)} locations within {radius_km} km. "
                f"Closest: {filtered[0]['name']} ({filtered[0]['distance_km']} km)"
                if filtered
                else f"No locations found within {radius_km} km"
            )

            top_3 = [loc.get("name", "N/A") for loc in filtered[:3]]
            self.logger.info(
                f"✅ GEOGRAPHY OUTPUT - Proximity filtering completed: "
                f"task_id={task.id} "
                f"filtered_count={len(filtered)} "
                f"original_count={len(locations)} "
                f"radius_km={radius_km} "
                f"center_lat={center_lat} "
                f"center_lon={center_lon} "
                f"result_keys={list(result_data.keys())} "
                f"response={response_text[:200].replace(chr(10), ' | ')} "
                f"top_3={top_3}"
            )

            return self._create_success_task(task, response_text, result_data)

        except Exception as e:
            self.logger.error(f"Proximity filtering failed: error={e!s}", exc_info=True)
            return self._create_error_task(task, f"Proximity filtering failed: {e!s}")

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate the great circle distance between two points on Earth.

        Uses the Haversine formula.

        Args:
            lat1, lon1: Coordinates of first point (degrees)
            lat2, lon2: Coordinates of second point (degrees)

        Returns:
            Distance in kilometers
        """
        # Earth's radius in kilometers
        R = 6371.0

        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Differences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        # Haversine formula
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance


# ============================================================================
# Standard Entry Points for Agent Launcher
# ============================================================================


def get_agent() -> GeographyAgent:
    """
    Create and return GeographyAgent instance.

    Called by agent_launcher.py to initialize the agent.

    Returns:
        GeographyAgent instance
    """
    agent = GeographyAgent()
    agent.initialize()
    return agent


def get_http_app(agent: GeographyAgent):
    """
    Create and return FastAPI app for GeographyAgent.

    Called by agent_launcher.py to initialize HTTP server.

    Args:
        agent: GeographyAgent instance

    Returns:
        FastAPI application instance
    """
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Geography Agent", version="1.0.0")

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {
            "status": "ok",
            "agent": "geography-agent",
            "version": "1.0.0",
            "service_type": "enhancement",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    @app.get("/.well-known/agent.json")
    async def agent_card():
        """Agent card endpoint (A2A protocol)"""
        card = agent.get_agent_card()  # Returns dict with enriched schemas
        return JSONResponse(card)

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

            from a2a.types import Message, Task, TaskState, TaskStatus, TextPart

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
    logger.info("🚀 Starting GeographyAgent...")

    agent = get_agent()

    logger.info(
        "✓ Agent initialized",
    )

    for cap in agent.capabilities:
        logger.info(
            f"  Capability: {cap.id}",
        )
