#!/usr/bin/env python3
"""
Events Agent - Travel Domain

Provides local events, activities, and attraction recommendations.

Key Learning Objective:
    This agent provides BOTH indoor and outdoor events.
    The orchestrator uses weather data to filter appropriately.

    Without Weather Agent: Returns all events (indoor + outdoor)
    With Weather Agent: Orchestrator filters based on weather conditions

Design:
    - Events categorized as "indoor" or "outdoor"
    - Weather-dependent flag for activities affected by rain
    - Mock data includes diverse activity types
    - Optional integration with Ticketmaster/Eventbrite APIs

Example Queries:
    "What events are happening in Seattle?"
    "Find things to do in Seattle this weekend"
    "What activities are available in Seattle?"

Mock Data Location:
    data/mock/events/locations.json

Event Types:
    Indoor:
        - Museums (Space Needle, Chihuly Garden, MoPOP)
        - Aquariums
        - Indoor markets
        - Entertainment venues

    Outdoor:
        - Hiking
        - Walking tours
        - Outdoor markets
        - Parks and gardens
"""

from datetime import UTC, datetime
from typing import Any

from a2a.types import Task

from lib.agents import AgentCapability, BaseAgent
from lib.agents.config_loader import get_agent_config, load_domain_config
from lib.agents.mock_data_factory import MockDataFactory


class EventsAgent(BaseAgent):
    """
    Events and activities recommendation agent.

    Single Capability:
        - find-events: Search for events and activities in a location

    Service Type:
        Primary - Returns events with coordinates that can be enhanced by geography-agent

    Data Sources:
        - Mock data (default): Curated list of Seattle events
        - Ticketmaster API (optional): Real event data
        - Eventbrite API (optional): Real event data

    Configuration:
        Environment Variables:
            - EVENTS_DATA_SOURCE: "mock" or "ticketmaster" or "eventbrite" (default: mock)
            - TICKETMASTER_API_KEY: API key for Ticketmaster (optional)
            - EVENTBRITE_API_KEY: API key for Eventbrite (optional)
    """

    def __init__(
        self,
        domain: str = "travel",
        agent_name: str = "events-agent",
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize EventsAgent.

        Args:
            domain: Domain name (default: "travel")
            agent_name: Agent name (default: "events-agent")
            config: Optional configuration override
        """
        super().__init__(domain, agent_name, config)

        # Load domain configuration
        try:
            domain_config = load_domain_config(domain)
            agent_config = get_agent_config(domain_config, "events")
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
        self.max_results = self.agent_config.get("max_results", 10)
        self.include_outdoor = self.agent_config.get("include_outdoor", True)
        self.include_indoor = self.agent_config.get("include_indoor", True)

        self.logger.info(
            f"Events agent configured: "
            f"max_results={self.max_results} "
            f"include_outdoor={self.include_outdoor} "
            f"include_indoor={self.include_indoor} "
            f"note='Using mock data for workshop demonstration'"
        )

    def _define_capabilities(self) -> list[AgentCapability]:
        """
        Define events agent capabilities.

        Returns:
            List of AgentCapability objects
        """
        return [
            AgentCapability(
                id="refine-events",
                name="Refine Events",
                description="""Events refinement agent. I refine event/attraction lists by domain-specific criteria.

USAGE: Use me after loading or filtering to apply event-specific refinement.
I work with pre-filtered data OR can load myself if no pre-filtered data provided.

WORKFLOW:
1. Receive: locations array (from loader or geography filter) - PREFERRED
   OR load data myself if no locations provided
2. Refine: by category, type (indoor/outdoor), price, accessibility
3. Return: refined events/attractions

REFINEMENT CRITERIA (OpenStreetMap-based):
- Category filtering (OR logic): theater, cinema, nightclub, music_venue, park, garden,
  beach, nature_reserve, mall, market, shopping
- Event type filtering: indoor, outdoor
- Price range filtering (max_price)
- Accessibility filtering (wheelchair_friendly)
- Weather-appropriateness tracking

DUAL-MODE OPERATION:
- Mode 1: Receive pre-filtered locations from geography-agent → apply domain filters
- Mode 2: Load data myself → apply domain filters

MULTI-CATEGORY SUPPORT:
Handles events, entertainment, outdoor, and shopping location categories.""",
                tags=[
                    "events",
                    "activities",
                    "things-to-do",
                    "attractions",
                    "travel",
                    "entertainment",
                    "refinement",
                    "domain-specific",
                ],
                examples=[
                    "What events are happening in Seattle?",
                    "Find things to do in Seattle this weekend",
                    "What activities are available in Seattle?",
                    "Show me attractions in Seattle",
                    "Find events near Pike Place Market",
                    "Show me activities close to downtown",
                ],
                input_schema={
                    "type": "object",
                    "properties": {
                        "locations": {
                            "type": "array",
                            "description": "Pre-filtered locations to refine (optional - preferred). If provided, refine these. If not provided, load from data.",
                            "items": {"type": "object"},
                        },
                        "location": {"type": "string", "description": "City name (required if locations not provided)"},
                        "event_type": {
                            "type": "string",
                            "description": "Type filter (indoor/outdoor/all)",
                            "default": "all",
                        },
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Category filter (OR logic): theater, cinema, nightclub, music_venue, park, garden, beach, nature_reserve, mall, market. Match ANY category.",
                        },
                        "max_price": {
                            "type": "number",
                            "description": "Maximum price filter (events with price <= max_price)",
                        },
                        "accessibility": {
                            "type": "string",
                            "description": "Accessibility filter (e.g., 'wheelchair_friendly')",
                        },
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of results",
                            "default": 10,
                        },
                    },
                    "required": ["location"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "events": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Name of the event or attraction",
                                    },
                                    "type": {
                                        "type": "string",
                                        "description": "Event type: indoor or outdoor",
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "Description of the event",
                                    },
                                    "price": {
                                        "type": "number",
                                        "description": "Price in USD",
                                    },
                                    "latitude": {
                                        "type": "number",
                                        "description": "Geographic latitude coordinate",
                                    },
                                    "longitude": {
                                        "type": "number",
                                        "description": "Geographic longitude coordinate",
                                    },
                                    "accessibility": {
                                        "type": "string",
                                        "description": "Accessibility information",
                                    },
                                    "weather_dependent": {
                                        "type": "boolean",
                                        "description": "Whether event depends on weather (optional)",
                                    },
                                    "duration": {
                                        "type": "string",
                                        "description": "Duration of event (optional)",
                                    },
                                    "category": {
                                        "type": "string",
                                        "description": "Event category (theater, cinema, nightclub, music_venue, park, garden, beach, nature_reserve, mall, market, shopping)",
                                    },
                                    "opening_hours": {
                                        "type": "string",
                                        "description": "Opening hours in OSM format (e.g., 'Mo-Fr 10:00-22:00; Sa-Su 10:00-18:00')",
                                    },
                                    "contact": {
                                        "type": "object",
                                        "description": "Contact information",
                                        "properties": {
                                            "phone": {
                                                "type": "string",
                                                "description": "Phone number",
                                            },
                                            "website": {
                                                "type": "string",
                                                "description": "Website URL",
                                            },
                                        },
                                    },
                                },
                                "required": [
                                    "name",
                                    "type",
                                    "description",
                                    "price",
                                    "latitude",
                                    "longitude",
                                ],
                            },
                        },
                        "location": {"type": "string", "description": "City name"},
                        "total_count": {
                            "type": "number",
                            "description": "Total number of events returned",
                        },
                    },
                },
                # Enhancement Service Pattern
                optional_enhancements=["geography-agent"],
                service_type="primary",
            ),
        ]

    def _process_task_impl(self, task: Task, user_input: dict[str, Any]) -> Task:
        """
        Process events task - performs event search only.

        This agent has a single capability: find-events.
        It returns events with coordinates that can be filtered by geography-agent.

        Args:
            task: A2A Task object
            user_input: Extracted user input with location and query

        Returns:
            Updated task with events data
        """
        # 📥 INLINE LOGGING - Log what we received (extra={} doesn't show in CloudWatch)
        import json

        user_input_preview = json.dumps(user_input, default=str)[:300]
        self.logger.info(
            f"📥 EVENTS INPUT - Received: task_id={task.id} input_keys={list(user_input.keys())} preview={user_input_preview}"
        )

        # Extract parameters
        locations = user_input.get("locations")  # Pre-filtered locations (optional)
        location = user_input.get("location", "Seattle")
        event_type = user_input.get("event_type", "all")

        # Parse categories if it's a JSON string
        # The orchestrator may pass arrays as JSON strings: '["park", "garden"]'
        categories_raw = user_input.get("categories", [])
        if isinstance(categories_raw, str):
            try:
                categories = json.loads(categories_raw)
                self.logger.debug(
                    f"Parsed categories from JSON string: {categories_raw} -> {categories}"
                )
            except json.JSONDecodeError:
                self.logger.warning(
                    f"Failed to parse categories JSON string: {categories_raw}"
                )
                categories = []
        else:
            categories = categories_raw

        max_price = user_input.get("max_price")
        accessibility = user_input.get("accessibility")
        max_results = int(
            user_input.get("max_results", self.max_results)
        )  # Convert to int
        user_query = user_input.get("query", "")

        self.logger.info(
            f"📥 EVENTS INPUT - Extracted: "
            f"locations_provided={locations is not None} "
            f"location={location} "
            f"event_type={event_type} "
            f"categories={categories} "
            f"categories_type={type(categories).__name__} "
            f"max_price={max_price} "
            f"accessibility={accessibility} "
            f"max_results={max_results}"
        )

        # Directly perform event refinement (single capability)
        return self._find_events(
            task, location, event_type, max_results, locations, categories, max_price, accessibility
        )

    def _find_events(
        self,
        task: Task,
        location: str,
        event_type: str = "all",
        max_results: int = 10,
        locations: list = None,
        categories: list[str] = None,
        max_price: float | None = None,
        accessibility: str | None = None,
    ) -> Task:
        """
        Refine events in a location.

        DUAL-MODE SUPPORT:
        - Option 1 (PREFERRED): Work with pre-filtered locations from geography-agent
        - Option 2 (FALLBACK): Load data ourselves if no pre-filtered locations provided

        Args:
            task: A2A Task
            location: City name
            event_type: Type filter (indoor/outdoor/all)
            max_results: Maximum number of results
            locations: Optional pre-filtered locations (from geography-agent or location-loader)
            categories: List of categories to filter (OR logic)
            max_price: Maximum price filter
            accessibility: Accessibility requirement (e.g., 'wheelchair_friendly')

        Returns:
            Task with refined events data
        """
        try:
            # DUAL-MODE LOGIC: Check for pre-filtered locations first
            if locations:
                # Option 1: Work with pre-filtered locations (PREFERRED)
                self.logger.info(
                    f"🎭 DUAL-MODE: Received {len(locations)} pre-filtered locations "
                    f"(from geography-agent or location-loader). "
                    f"operation=refine_events mode=pre-filtered"
                )
                events = locations
            else:
                # Option 2: Load ourselves (BACKWARD COMPATIBILITY)
                self.logger.info(
                    f"🎭 DUAL-MODE: No pre-filtered locations provided. "
                    f"Loading data ourselves. "
                    f"operation=refine_events mode=self-load location={location}"
                )
                events = self._fetch_events_data(location)

            self.logger.debug(
                f"🎭 Refining events: "
                f"operation=refine_events "
                f"location={location} "
                f"event_type_filter={event_type} "
                f"max_results={max_results} "
                f"initial_count={len(events)} "
                f"note='Refining indoor and outdoor activities'"
            )

            if not events:
                return self._create_error_task(task, f"No events found for {location}")

            # Filter by type
            initial_count = len(events)
            if event_type == "indoor":
                events = [e for e in events if e.get("type") == "indoor"]
            elif event_type == "outdoor":
                events = [e for e in events if e.get("type") == "outdoor"]

            self.logger.debug(
                f"🔍 Filtered events: "
                f"location={location} "
                f"initial_count={initial_count} "
                f"filter_applied={event_type} "
                f"filtered_count={len(events)} "
                f"note='Filtered from {initial_count} to {len(events)} events based on {event_type} type'"
            )

            # Filter by categories
            if categories:
                events = self._filter_by_category(events, categories)

            # Filter by price
            if max_price is not None:
                events = self._filter_by_price(events, max_price)

            # Filter by accessibility
            if accessibility:
                events = self._filter_by_accessibility(events, accessibility)

            # Limit results
            events = events[:max_results]

            # Format response
            response_text = f"Events and Activities in {location}:\n\n"

            indoor_events = [e for e in events if e.get("type") == "indoor"]
            outdoor_events = [e for e in events if e.get("type") == "outdoor"]

            if indoor_events:
                response_text += "🏛️ Indoor Activities:\n"
                for event in indoor_events:
                    name = event.get("name", "Unknown")
                    description = event.get("description", "")
                    duration = event.get("duration", "Varies")
                    price = event.get("price", 0)

                    response_text += f"\n• {name}\n"
                    if description:
                        response_text += f"  {description}\n"
                    response_text += f"  Duration: {duration} | Price: ${price}\n"

            if outdoor_events:
                response_text += "\n🌲 Outdoor Activities:\n"
                for event in outdoor_events:
                    name = event.get("name", "Unknown")
                    description = event.get("description", "")
                    duration = event.get("duration", "Varies")
                    price = event.get("price", 0)
                    weather_dependent = event.get("weather_dependent", False)

                    response_text += f"\n• {name}"
                    if weather_dependent:
                        response_text += " ⛈️ (weather dependent)"
                    response_text += "\n"
                    if description:
                        response_text += f"  {description}\n"
                    response_text += f"  Duration: {duration} | Price: ${price}\n"

            response_text += f"\n\nTotal: {len(events)} activities found"

            # Add note about weather filtering (for orchestrator)
            weather_dependent_count = sum(
                1 for e in events if e.get("weather_dependent", False)
            )
            if weather_dependent_count > 0:
                response_text += f"\n\nNote: {weather_dependent_count} activities are weather-dependent."

            # Structure data for other agents
            filters_applied = {}
            if event_type != "all":
                filters_applied["event_type"] = event_type
            if categories:
                filters_applied["categories"] = categories
            if max_price is not None:
                filters_applied["max_price"] = max_price
            if accessibility:
                filters_applied["accessibility"] = accessibility

            result_data = {
                "location": location,
                "events": events,
                "total_count": len(events),
                "indoor_count": len(indoor_events),
                "outdoor_count": len(outdoor_events),
                "weather_dependent_count": weather_dependent_count,
                "filters_applied": filters_applied,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            top_3 = [e.get("name", "N/A") for e in events[:3]]
            self.logger.info(
                f"✅ EVENTS OUTPUT - Search completed: "
                f"task_id={task.id} "
                f"location={location} "
                f"total_results={len(events)} "
                f"indoor_count={len(indoor_events)} "
                f"outdoor_count={len(outdoor_events)} "
                f"weather_dependent={weather_dependent_count} "
                f"filters_applied={filters_applied} "
                f"result_keys={list(result_data.keys())} "
                f"top_3={top_3}"
            )

            return self._create_success_task(task, response_text, result_data)

        except Exception as e:
            import traceback

            tb = traceback.format_exc()[:500]
            self.logger.error(
                f"❌ EXCEPTION in _find_events: {e!s} "
                f"task_id={task.id} "
                f"location={location} "
                f"event_type={event_type} "
                f"exception_type={type(e).__name__} "
                f"traceback={tb}",
                exc_info=True,
            )
            return self._create_error_task(task, f"Events search failed: {e!s}")

    def _fetch_events_data(self, location: str) -> list[dict[str, Any]]:
        """
        Fetch events data from configured source.

        Args:
            location: City name

        Returns:
            List of events
        """
        self.logger.debug(
            f"📊 Fetching events data: "
            f"operation=fetch_events_data "
            f"location={location} "
            f"note='Using mock data for workshop demonstration'"
        )

        # Always use mock data for workshop
        data = self.mock_factory.get_events(location)
        event_count = len(data) if data else 0
        self.logger.debug(
            f"✓ Mock events data loaded: "
            f"location={location} "
            f"events_count={event_count} "
            f"note='Mock data includes diverse indoor/outdoor activities for Seattle'"
        )
        return data

    def _filter_by_category(
        self, events: list[dict[str, Any]], categories: list[str]
    ) -> list[dict[str, Any]]:
        """
        Filter events by category.

        Uses OR logic: Event matches if it has ANY of the requested categories.

        Args:
            events: List of event dicts
            categories: List of category strings
                (theater, cinema, nightclub, music_venue, park, garden, beach, nature_reserve, mall, market)

        Returns:
            Filtered list of events
        """
        if not categories:
            return events

        filtered = [e for e in events if e.get("category") in categories]

        self.logger.debug(
            f"🎭 Category filter applied: "
            f"categories={categories} "
            f"before_count={len(events)} "
            f"after_count={len(filtered)} "
            f"note='OR logic: event matches if it has ANY requested category'"
        )

        return filtered

    def _filter_by_price(
        self, events: list[dict[str, Any]], max_price: float
    ) -> list[dict[str, Any]]:
        """
        Filter events by maximum price.

        Args:
            events: List of event dicts
            max_price: Maximum price threshold

        Returns:
            Filtered list of events
        """
        filtered = [e for e in events if e.get("price", 0) <= max_price]

        self.logger.debug(
            f"💰 Price filter applied: "
            f"max_price={max_price} "
            f"before_count={len(events)} "
            f"after_count={len(filtered)}"
        )

        return filtered

    def _filter_by_accessibility(
        self, events: list[dict[str, Any]], accessibility: str
    ) -> list[dict[str, Any]]:
        """
        Filter events by accessibility requirement.

        Args:
            events: List of event dicts
            accessibility: Accessibility requirement (e.g., "wheelchair_friendly")

        Returns:
            Filtered list of events
        """
        filtered = [e for e in events if e.get("accessibility") == accessibility]

        self.logger.debug(
            f"♿ Accessibility filter applied: "
            f"requirement={accessibility} "
            f"before_count={len(events)} "
            f"after_count={len(filtered)}"
        )

        return filtered


# ============================================================================
# Standard Entry Points for Agent Launcher
# ============================================================================


def get_agent() -> EventsAgent:
    """
    Create and return EventsAgent instance.

    Called by agent_launcher.py to initialize the agent.

    Returns:
        EventsAgent instance
    """
    agent = EventsAgent()
    agent.initialize()
    return agent


def get_http_app(agent: EventsAgent):
    """
    Create and return FastAPI app for EventsAgent.

    Called by agent_launcher.py to initialize HTTP server.

    Args:
        agent: EventsAgent instance

    Returns:
        FastAPI application instance
    """
    from datetime import datetime
    import json

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Events Agent", version="1.0.0")

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {
            "status": "ok",
            "agent": "events-agent",
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

            # Process task (using Task imported at module level - line 52)
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

            # Create error task (using types imported at module level)
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

    logger.info("🚀 Starting EventsAgent...")
    agent = get_agent()

    logger.info(
        "✓ Agent initialized",
    )

    for cap in agent.capabilities:
        logger.info(f"  Capability: {cap.id}")
