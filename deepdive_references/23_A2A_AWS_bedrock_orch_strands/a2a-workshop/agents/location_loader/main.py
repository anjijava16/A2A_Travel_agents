#!/usr/bin/env python3
"""
Location Loader Agent - Travel Domain

Pure data loading agent that returns complete unfiltered datasets.

Key Learning Objective:
    This agent demonstrates SINGLE RESPONSIBILITY PRINCIPLE.
    It does ONE thing: loads data. No filtering, no refinement, no limits.

    Separation of Concerns:
        - location-loader: LOADS all data
        - geography-agent: FILTERS by proximity
        - events/restaurant agents: REFINE by domain criteria
        - orchestrator: SYNTHESIZES final recommendations

Design Philosophy:
    "Load once, filter multiple ways"

    By separating loading from filtering, we enable:
    - Flexible composition (compose agents differently for different queries)
    - Hard data filtering first (geography filters 2000 → 20, then LLM picks best 10)
    - Backward compatibility (other agents can still load if needed)
    - Domain-agnostic orchestration (works with any domain)

Example Queries:
    "Load all restaurants in Seattle"
    "Get all events for Portland"
    "Load accommodation data for San Francisco"

Mock Data Location:
    data/mock/events/locations.json
    data/mock/restaurants/locations.json
    data/mock/accommodations/locations.json

Educational Value:
    Teaches that loading is distinct from processing.
    Complex behaviors emerge from simple agents working together.
"""

from datetime import UTC, datetime
from typing import Any

from a2a.types import Task

from lib.agents import AgentCapability, BaseAgent
from lib.agents.config_loader import get_agent_config, load_domain_config
from lib.agents.mock_data_factory import MockDataFactory


class LocationLoaderAgent(BaseAgent):
    """
    Pure data loading agent - returns complete unfiltered datasets.

    Single Capability:
        - load-locations: Load ALL locations for a city and category

    Service Type:
        Primary - Provides raw data that feeds filtering/refinement agents

    Data Sources:
        - Mock data: Comprehensive OpenStreetMap datasets
        - Returns complete data (Seattle: 2,587 events, 1,823 restaurants)

    Configuration:
        - NO max_results limit
        - NO filtering logic
        - NO refinement logic
        - Pure data pass-through

    Usage Pattern:
        location-loader → geography-agent → domain-agent → synthesis
        OR
        location-loader → domain-agent → synthesis
        OR
        location-loader → synthesis (if just location data needed)
    """

    def __init__(
        self,
        domain: str = "travel",
        agent_name: str = "location-loader",
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize LocationLoaderAgent.

        Args:
            domain: Domain name (default: "travel")
            agent_name: Agent name (default: "location-loader")
            config: Optional configuration override
        """
        super().__init__(domain, agent_name, config)

        # Load domain configuration
        try:
            domain_config = load_domain_config(domain)
            agent_config = get_agent_config(domain_config, "location_loader")
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

        self.logger.info(
            "Location loader agent initialized: "
            "note='Pure data loader - no filtering, no limits, returns complete datasets'"
        )

    def _define_capabilities(self) -> list[AgentCapability]:
        """
        Define location loader capabilities.

        Returns:
            List of AgentCapability objects
        """
        return [
            AgentCapability(
                id="load-locations",
                name="Load Location Data",
                description="""Data loading agent. I load complete datasets for cities.

I am a PURE DATA LOADER - no filtering, no refinement, no limits.
I return ALL locations for a city and category (complete, unfiltered dataset).

USAGE: Use me when you need raw location data.
My output feeds filtering agents (geography-agent) or refinement agents (events-agent, restaurant-agent).

WORKFLOW:
1. Call me with: location="Seattle", category="restaurants"
2. I return: ALL 1,823 Seattle restaurants (complete, unfiltered)
3. Other agents: filter/refine as needed

WHY SEPARATE ME: Loading is distinct from filtering. Separating concerns allows
flexible composition - load once, filter multiple ways.

EFFICIENCY PATTERN:
Hard data filtering first (objective, fast) → Soft selection second (subjective, thoughtful)
Example: Load 2,000 → Filter to 20 (geography) → Pick best 10 (LLM)
This is more efficient than LLM reasoning about all 2,000 items.""",
                tags=[
                    "data-loading",
                    "raw-data",
                    "complete-dataset",
                    "unfiltered",
                    "primary-agent",
                ],
                examples=[
                    "Load all restaurants in Seattle",
                    "Get all events for Portland",
                    "Load accommodation data for San Francisco",
                    "Give me all Seattle locations",
                    "Load complete restaurant dataset for Chicago",
                ],
                input_schema={
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name (e.g., 'Seattle', 'Portland')",
                        },
                        "category": {
                            "type": "string",
                            "enum": [
                                "accommodations",
                                "entertainment",
                                "events",
                                "outdoor",
                                "restaurants",
                                "shopping",
                            ],
                            "description": "Category of locations to load (all have lat/long for geography filtering)",
                        },
                    },
                    "required": ["location", "category"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "locations": {
                            "type": "array",
                            "description": "Complete unfiltered dataset - ALL locations for city+category with FULL OpenStreetMap fields",
                            "items": {
                                "type": "object",
                                "properties": {
                                    # Core identification
                                    "name": {"type": "string", "description": "Name of the location"},
                                    "type": {"type": "string", "description": "Location type (indoor/outdoor)"},

                                    # Geographic coordinates
                                    "latitude": {"type": "number", "description": "Geographic latitude coordinate"},
                                    "longitude": {"type": "number", "description": "Geographic longitude coordinate"},

                                    # Restaurant-specific fields
                                    "cuisine": {"type": "string", "description": "Cuisine type(s), semicolon-separated"},
                                    "rating": {"type": "number", "description": "Rating out of 5.0"},
                                    "price": {"type": "string", "description": "Price range ($, $$, $$$, $$$$) for restaurants OR number for events"},

                                    # OpenStreetMap operational data
                                    "opening_hours": {"type": "string", "description": "Opening hours in OSM format (e.g., 'Mo-Fr 11:00-21:00; Sa-Su 11:00-20:00')"},
                                    "contact": {
                                        "type": "object",
                                        "description": "Contact information",
                                        "properties": {
                                            "phone": {"type": "string", "description": "Phone number"},
                                            "website": {"type": "string", "description": "Website URL"},
                                        },
                                    },

                                    # Dietary options (restaurants)
                                    "dietary": {
                                        "type": "object",
                                        "description": "Dietary options available",
                                        "properties": {
                                            "vegan": {"type": "boolean"},
                                            "vegetarian": {"type": "boolean"},
                                            "gluten_free": {"type": "boolean"},
                                            "lactose_free": {"type": "boolean"},
                                            "halal": {"type": "boolean"},
                                            "kosher": {"type": "boolean"},
                                            "dairy_free": {"type": "boolean"},
                                            "pescetarian": {"type": "boolean"},
                                        },
                                    },

                                    # Amenities
                                    "outdoor_seating": {"type": "boolean", "description": "Has outdoor seating available"},
                                    "delivery": {"type": "boolean", "description": "Offers delivery service"},
                                    "takeaway": {"type": "boolean", "description": "Offers takeaway/takeout service"},
                                    "accessibility": {"type": "string", "description": "Accessibility information"},

                                    # Event-specific fields
                                    "category": {"type": "string", "description": "Event category (theater, cinema, park, etc.)"},
                                    "description": {"type": "string", "description": "Description of the location"},
                                    "duration": {"type": "string", "description": "Duration of event (optional)"},
                                    "weather_dependent": {"type": "boolean", "description": "Whether event depends on weather (optional)"},
                                },
                                "description": "Location object with ALL available OSM fields preserved for downstream agents",
                            },
                        },
                        "total_count": {
                            "type": "number",
                            "description": "Total number of locations loaded (no limit applied)",
                        },
                        "location": {
                            "type": "string",
                            "description": "City name",
                        },
                        "category": {
                            "type": "string",
                            "description": "Category of locations",
                        },
                    },
                },
                # This is a primary agent that provides data
                service_type="primary",
            ),
        ]

    def _process_task_impl(self, task: Task, user_input: dict[str, Any]) -> Task:
        """
        Process location loading task.

        This agent has a single capability: load-locations.
        It returns complete datasets with no filtering or limits.

        Args:
            task: A2A Task object
            user_input: Extracted user input with location and category

        Returns:
            Updated task with complete location data
        """
        # 📥 INLINE LOGGING - Log what we received
        import json

        user_input_full = json.dumps(user_input, default=str, indent=2)
        self.logger.info(
            f"🔍 LOCATION LOADER DIAGNOSTIC - Full input received: task_id={task.id} user_input={user_input_full}"
        )

        # Extract parameters
        location = user_input.get("location", "Seattle")
        category = user_input.get("category")

        # DIAGNOSTIC: Log extracted values
        self.logger.info(
            f"🔍 LOCATION LOADER DIAGNOSTIC - Extracted params: location={location!r} category={category!r} category_type={type(category).__name__}"
        )

        # Validate required category parameter
        if not category:
            error_msg = (
                "Required parameter 'category' not provided. "
                "Must be 'restaurants', 'events', or 'accommodations'. "
                "This ensures correct data source selection."
            )
            self.logger.error(f"❌ LOCATION LOADER ERROR: {error_msg}")
            return self._create_error_task(task, error_msg)

        # Directly perform data loading (single capability)
        return self._load_locations(task, location, category)

    def _load_locations(self, task: Task, location: str, category: str) -> Task:
        """
        Load ALL locations for a city and category.

        NO FILTERING, NO LIMITS - returns complete dataset.

        Args:
            task: A2A Task
            location: City name
            category: Category (events/restaurants/accommodations)

        Returns:
            Task with complete location data
        """
        try:
            self.logger.debug(
                f"📂 Loading location data: "
                f"operation=load_locations "
                f"location={location} "
                f"category={category} "
                f"note='Loading complete dataset with NO LIMITS'"
            )

            # Load data using MockFactory
            data = self.mock_factory.load_data(category)

            if not isinstance(data, dict):
                return self._create_error_task(
                    task, f"Invalid data structure for category {category}"
                )

            locations = data.get(location, [])

            # Handle nested dict structure (backward compatibility)
            if isinstance(locations, dict):
                self.logger.warning(
                    f"Found nested structure for category={category}, flattening..."
                )
                flattened = []
                for subcategory, items in locations.items():
                    if isinstance(items, list):
                        # Add subcategory as field
                        for item in items:
                            item_copy = item.copy()
                            item_copy['subcategory'] = subcategory
                            flattened.append(item_copy)
                locations = flattened

                self.logger.debug(
                    f"Flattened {len(locations)} items from nested structure"
                )

            if not locations:
                self.logger.warning(
                    f"⚠️ No data found: location={location} category={category}"
                )
                return self._create_error_task(
                    task, f"No {category} data found for {location}"
                )

            total_count = len(locations)

            # CRITICAL: NO max_results limiting!
            # Return ALL data - let other agents filter/refine
            self.logger.info(
                f"✅ LOCATION LOADER OUTPUT - Complete dataset loaded: "
                f"task_id={task.id} "
                f"location={location} "
                f"category={category} "
                f"total_count={total_count} "
                f"note='Returning ALL {total_count} locations (no limits applied)'"
            )

            # Format response
            response_text = (
                f"Complete {category} dataset for {location}:\n\n"
                f"Loaded {total_count} locations (unfiltered, complete dataset)\n\n"
                f"This data can now be:\n"
                f"  • Filtered by geography-agent (proximity-based)\n"
                f"  • Refined by domain agents (events/restaurant criteria)\n"
                f"  • Synthesized by LLM (quality/preference selection)\n\n"
                f"Educational Note: This demonstrates separation of loading from processing."
            )

            # Structure data for other agents
            result_data = {
                "locations": locations,  # Complete dataset!
                "total_count": total_count,
                "location": location,
                "category": category,
                "timestamp": datetime.now(UTC).isoformat(),
                "note": f"Complete unfiltered dataset of {total_count} locations",
            }

            # Sample for logging
            sample_names = [loc.get("name", "N/A") for loc in locations[:3]]
            self.logger.info(
                f"✅ LOCATION LOADER OUTPUT - Data structure: "
                f"result_keys={list(result_data.keys())} "
                f"sample_locations={sample_names} "
                f"total_count={total_count}"
            )

            return self._create_success_task(task, response_text, result_data)

        except Exception as e:
            import traceback

            tb = traceback.format_exc()[:500]
            self.logger.error(
                f"❌ EXCEPTION in _load_locations: {e!s} "
                f"task_id={task.id} "
                f"location={location} "
                f"category={category} "
                f"exception_type={type(e).__name__} "
                f"traceback={tb}",
                exc_info=True,
            )
            return self._create_error_task(task, f"Location loading failed: {e!s}")


# ============================================================================
# Standard Entry Points for Agent Launcher
# ============================================================================


def get_agent() -> LocationLoaderAgent:
    """
    Create and return LocationLoaderAgent instance.

    Called by agent_launcher.py to initialize the agent.

    Returns:
        LocationLoaderAgent instance
    """
    agent = LocationLoaderAgent()
    agent.initialize()
    return agent


def get_http_app(agent: LocationLoaderAgent):
    """
    Create and return FastAPI app for LocationLoaderAgent.

    Called by agent_launcher.py to initialize HTTP server.

    Args:
        agent: LocationLoaderAgent instance

    Returns:
        FastAPI application instance
    """
    from datetime import datetime
    import json

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Location Loader Agent", version="1.0.0")

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {
            "status": "ok",
            "agent": "location-loader",
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
            task = Task.model_validate(task_dict)
            result_task = agent.process_task(task)

            # 🔍 LOGGING - Check task structure before serialization (DEBUG level)
            agent.logger.debug(
                f"🔍 HTTP HANDLER - Task before model_dump: artifacts={len(result_task.artifacts) if result_task.artifacts else 0}"
            )
            if result_task.artifacts:
                for i, artifact in enumerate(result_task.artifacts):
                    agent.logger.debug(
                        f"🔍 HTTP HANDLER - Artifact {i}: parts_count={len(artifact.parts)}"
                    )
                    for j, part in enumerate(artifact.parts):
                        agent.logger.debug(
                            f"🔍 HTTP HANDLER - Part {j}: type={type(part).__name__} has_root={hasattr(part, 'root')} has_kind={hasattr(part, 'kind')}"
                        )

            serialized = result_task.model_dump(mode="json")

            # 🔍 LOGGING - Check serialized structure (DEBUG level)
            if serialized.get("artifacts"):
                agent.logger.debug(
                    f"🔍 HTTP HANDLER - After model_dump: artifacts={len(serialized['artifacts'])} parts_in_first={len(serialized['artifacts'][0].get('parts', []))}"
                )

            return serialized

        except Exception as e:
            import traceback

            traceback.print_exc()

            # Create error task
            import uuid

            from a2a.types import Message, TaskState, TaskStatus, TextPart

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

    logger.info("🚀 Starting LocationLoaderAgent...")
    agent = get_agent()

    logger.info("✓ Agent initialized")

    for cap in agent.capabilities:
        logger.info(f"  Capability: {cap.id}")
