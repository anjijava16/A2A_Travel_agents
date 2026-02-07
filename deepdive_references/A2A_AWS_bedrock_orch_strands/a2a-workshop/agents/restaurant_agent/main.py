#!/usr/bin/env python3
"""
Restaurant Agent - Travel Domain

Provides restaurant and dining recommendations.

Key Learning Objective:
    This agent completes the baseline travel planning system.
    Restaurants are primarily indoor activities, so less affected by weather.

Design:
    - Restaurant recommendations with ratings and cuisine types
    - Indoor/outdoor seating information
    - Price range indicators
    - Mock data includes diverse cuisine options
    - Optional integration with Yelp/Google Places APIs

Example Queries:
    "Where should I eat in Seattle?"
    "Find good restaurants in Seattle"
    "Recommend seafood restaurants in Seattle"
    "What are the best rated restaurants in Seattle?"

Mock Data Location:
    data/mock/restaurants/locations.json

Restaurant Categories:
    - Seafood (Pike Place Chowder)
    - Cajun (Toulouse Petit)
    - Italian (The Pink Door)
    - Pizza (Serious Pie)
    - American (Local 360)
"""

from datetime import UTC, datetime
from typing import Any

from a2a.types import Task

from lib.agents import AgentCapability, BaseAgent
from lib.agents.config_loader import get_agent_config, load_domain_config
from lib.agents.mock_data_factory import MockDataFactory


class RestaurantAgent(BaseAgent):
    """
    Restaurant and dining recommendation agent.

    Single Capability:
        - find-restaurants: Search for restaurants in a location

    Service Type:
        Primary - Returns restaurants with coordinates that can be enhanced by geography-agent

    Data Sources:
        - Mock data (default): Curated restaurant list
        - Yelp Fusion API (optional): Real restaurant data
        - Google Places API (optional): Real restaurant data

    Configuration:
        Environment Variables:
            - RESTAURANT_DATA_SOURCE: "mock" or "yelp" or "google_places" (default: mock)
            - YELP_API_KEY: API key for Yelp Fusion (optional)
            - GOOGLE_PLACES_API_KEY: API key for Google Places (optional)
    """

    def __init__(
        self,
        domain: str = "travel",
        agent_name: str = "restaurant-agent",
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize RestaurantAgent.

        Args:
            domain: Domain name (default: "travel")
            agent_name: Agent name (default: "restaurant-agent")
            config: Optional configuration override
        """
        super().__init__(domain, agent_name, config)

        # Load domain configuration
        try:
            domain_config = load_domain_config(domain)
            agent_config = get_agent_config(domain_config, "restaurants")
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
        self.max_results = self.agent_config.get("max_results", 20)
        self.include_ratings = self.agent_config.get("include_ratings", True)
        self.cuisine_types = self.agent_config.get("cuisine_types", "all")

        self.logger.info(
            f"Restaurant agent configured: "
            f"max_results={self.max_results} "
            f"include_ratings={self.include_ratings} "
            f"cuisine_types={self.cuisine_types} "
            f"note='Using mock data for workshop demonstration'"
        )

    def _define_capabilities(self) -> list[AgentCapability]:
        """
        Define restaurant agent capabilities.

        Returns:
            List of AgentCapability objects
        """
        return [
            AgentCapability(
                id="refine-restaurants",
                name="Refine Restaurants",
                description="""Restaurant refinement agent. I refine restaurant lists by domain-specific criteria.

USAGE: Use me after loading or filtering to apply restaurant-specific refinement.
I work with pre-filtered data OR can load myself if no pre-filtered data provided.

WORKFLOW:
1. Receive: locations array (from loader or geography filter) - PREFERRED
   OR load data myself if no locations provided
2. Refine: by cuisine, price, dietary restrictions, amenities
3. Return: refined restaurants sorted by rating

REFINEMENT CRITERIA (OpenStreetMap-based):
- Cuisine type filtering (italian, thai, vietnamese, etc.)
- Price range filtering ($, $$, $$$, $$$$)
- Dietary restrictions (ALL-OF logic): vegan, vegetarian, gluten_free, lactose_free,
  halal, kosher, dairy_free, pescetarian
- Amenities: outdoor_seating, delivery, takeaway
- Rating sort (highest first)

DUAL-MODE OPERATION:
- Mode 1: Receive pre-filtered locations from geography-agent → apply domain filters
- Mode 2: Load data myself → apply domain filters""",
                tags=[
                    "restaurants",
                    "dining",
                    "food",
                    "cuisine",
                    "travel",
                    "meals",
                    "refinement",
                    "domain-specific",
                ],
                examples=[
                    "Where should I eat in Seattle?",
                    "Find good restaurants in Seattle",
                    "Recommend seafood restaurants in Seattle",
                    "What are the best restaurants in Seattle?",
                    "Find restaurants near Pike Place Market",
                    "Show me dining options close to downtown",
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
                        "cuisine": {
                            "type": "string",
                            "description": "Cuisine type (optional)",
                        },
                        "price_range": {
                            "type": "string",
                            "description": "Price range ($, $$, $$$, $$$$)",
                        },
                        "dietary_restrictions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Dietary restrictions filter (vegan, vegetarian, gluten_free, lactose_free, halal, kosher, dairy_free, pescetarian). ALL must be satisfied.",
                        },
                        "outdoor_seating": {
                            "type": "boolean",
                            "description": "Filter for restaurants with outdoor seating",
                        },
                        "delivery": {
                            "type": "boolean",
                            "description": "Filter for restaurants with delivery service",
                        },
                        "takeaway": {
                            "type": "boolean",
                            "description": "Filter for restaurants with takeaway/takeout service",
                        },
                        "max_results": {
                            "type": "number",
                            "description": "Maximum number of results",
                            "default": 20,
                        },
                    },
                    "required": ["location"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "restaurants": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Name of the restaurant",
                                    },
                                    "cuisine": {
                                        "type": "string",
                                        "description": "Cuisine type(s), semicolon-separated",
                                    },
                                    "rating": {
                                        "type": "number",
                                        "description": "Rating out of 5.0",
                                    },
                                    "price": {
                                        "type": "string",
                                        "description": "Price range ($, $$, $$$, $$$$)",
                                    },
                                    "type": {
                                        "type": "string",
                                        "description": "Restaurant type (e.g., indoor)",
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
                                    "opening_hours": {
                                        "type": "string",
                                        "description": "Opening hours in OSM format (e.g., 'Mo-Fr 11:00-21:00; Sa-Su 11:00-20:00')",
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
                                    "dietary": {
                                        "type": "object",
                                        "description": "Dietary options available (vegan, vegetarian, gluten_free, etc.)",
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
                                    "outdoor_seating": {
                                        "type": "boolean",
                                        "description": "Has outdoor seating available",
                                    },
                                    "delivery": {
                                        "type": "boolean",
                                        "description": "Offers delivery service",
                                    },
                                    "takeaway": {
                                        "type": "boolean",
                                        "description": "Offers takeaway/takeout service",
                                    },
                                },
                                "required": [
                                    "name",
                                    "cuisine",
                                    "rating",
                                    "price",
                                    "latitude",
                                    "longitude",
                                ],
                            },
                        },
                        "location": {"type": "string", "description": "City name"},
                        "total_count": {
                            "type": "number",
                            "description": "Total number of restaurants returned",
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
        Process restaurant task - performs restaurant search only.

        This agent has a single capability: find-restaurants.
        It returns restaurants with coordinates that can be enhanced by geography-agent.

        Args:
            task: A2A Task object
            user_input: Extracted user input with location and query

        Returns:
            Updated task with restaurant data
        """
        # 📥 INLINE LOGGING - Log what we received (extra={} doesn't show in CloudWatch)
        import json

        user_input_preview = json.dumps(user_input, default=str)[:300]
        self.logger.info(
            f"📥 RESTAURANT INPUT - Received: task_id={task.id} input_keys={list(user_input.keys())} preview={user_input_preview}"
        )

        # Extract parameters
        locations = user_input.get("locations")  # Pre-filtered locations (optional)
        location = user_input.get("location", "Seattle")
        cuisine = user_input.get("cuisine")
        price_range = user_input.get("price_range")

        # Parse dietary_restrictions if it's a JSON string
        # The orchestrator may pass arrays as JSON strings: '["vegan"]'
        dietary_restrictions_raw = user_input.get("dietary_restrictions", [])
        if isinstance(dietary_restrictions_raw, str):
            try:
                dietary_restrictions = json.loads(dietary_restrictions_raw)
                self.logger.debug(
                    f"Parsed dietary_restrictions from JSON string: {dietary_restrictions_raw} -> {dietary_restrictions}"
                )
            except json.JSONDecodeError:
                self.logger.warning(
                    f"Failed to parse dietary_restrictions JSON string: {dietary_restrictions_raw}"
                )
                dietary_restrictions = []
        else:
            dietary_restrictions = dietary_restrictions_raw

        outdoor_seating = user_input.get("outdoor_seating")
        delivery = user_input.get("delivery")
        takeaway = user_input.get("takeaway")
        max_results = int(
            user_input.get("max_results", self.max_results)
        )  # Convert to int
        user_query = user_input.get("query", "")

        self.logger.info(
            f"📥 RESTAURANT INPUT - Extracted: "
            f"locations_provided={locations is not None} "
            f"location={location} "
            f"cuisine={cuisine or 'all'} "
            f"price_range={price_range or 'all'} "
            f"dietary_restrictions={dietary_restrictions} "
            f"dietary_restrictions_type={type(dietary_restrictions).__name__} "
            f"outdoor_seating={outdoor_seating} "
            f"delivery={delivery} "
            f"takeaway={takeaway} "
            f"max_results={max_results}"
        )

        # Directly perform restaurant refinement (single capability)
        return self._find_restaurants(
            task,
            location,
            cuisine,
            price_range,
            max_results,
            locations,
            dietary_restrictions,
            outdoor_seating,
            delivery,
            takeaway,
        )

    def _find_restaurants(
        self,
        task: Task,
        location: str,
        cuisine: str | None = None,
        price_range: str | None = None,
        max_results: int = 20,
        locations: list = None,
        dietary_restrictions: list[str] = None,
        outdoor_seating: bool | None = None,
        delivery: bool | None = None,
        takeaway: bool | None = None,
    ) -> Task:
        """
        Refine restaurants in a location.

        DUAL-MODE SUPPORT:
        - Option 1 (PREFERRED): Work with pre-filtered locations from geography-agent
        - Option 2 (FALLBACK): Load data ourselves if no pre-filtered locations provided

        Args:
            task: A2A Task
            location: City name
            cuisine: Cuisine type filter (optional)
            price_range: Price range filter (optional)
            max_results: Maximum number of results
            locations: Optional pre-filtered locations (from geography-agent or location-loader)
            dietary_restrictions: List of dietary requirements (all must be satisfied)
            outdoor_seating: Filter for outdoor seating
            delivery: Filter for delivery service
            takeaway: Filter for takeaway service

        Returns:
            Task with refined restaurant data
        """
        try:
            # DUAL-MODE LOGIC: Check for pre-filtered locations first
            if locations:
                # Option 1: Work with pre-filtered locations (PREFERRED)
                self.logger.info(
                    f"🍽️ DUAL-MODE: Received {len(locations)} pre-filtered locations "
                    f"(from geography-agent or location-loader). "
                    f"operation=refine_restaurants mode=pre-filtered"
                )
                restaurants = locations
            else:
                # Option 2: Load ourselves (BACKWARD COMPATIBILITY)
                self.logger.info(
                    f"🍽️ DUAL-MODE: No pre-filtered locations provided. "
                    f"Loading data ourselves. "
                    f"operation=refine_restaurants mode=self-load location={location}"
                )
                restaurants = self._fetch_restaurants_data(location)

            self.logger.debug(
                f"🍽️ Refining restaurants: "
                f"operation=refine_restaurants "
                f"location={location} "
                f"cuisine_filter={cuisine or 'all'} "
                f"price_filter={price_range or 'all'} "
                f"max_results={max_results} "
                f"initial_count={len(restaurants)} "
                f"note='Refining dining options with domain-specific criteria'"
            )

            if not restaurants:
                return self._create_error_task(
                    task, f"No restaurants found for {location}"
                )

            # Filter by cuisine
            initial_count = len(restaurants)
            if cuisine:
                restaurants = [
                    r
                    for r in restaurants
                    if cuisine.lower() in r.get("cuisine", "").lower()
                ]
                self.logger.debug(
                    f"🔍 Cuisine filter applied: "
                    f"cuisine_filter={cuisine} "
                    f"before_count={initial_count} "
                    f"after_count={len(restaurants)} "
                    f"note='Filtered to {cuisine} restaurants'"
                )

            # Filter by price range
            if price_range:
                before_price_filter = len(restaurants)
                restaurants = [
                    r for r in restaurants if r.get("price", "") == price_range
                ]
                self.logger.debug(
                    f"🔍 Price filter applied: "
                    f"price_filter={price_range} "
                    f"before_count={before_price_filter} "
                    f"after_count={len(restaurants)} "
                    f"note='Filtered to {price_range} price range'"
                )

            # Filter by dietary restrictions
            if dietary_restrictions:
                restaurants = self._filter_by_dietary(restaurants, dietary_restrictions)

            # Filter by amenities
            if outdoor_seating or delivery or takeaway:
                restaurants = self._filter_by_amenities(
                    restaurants, outdoor_seating, delivery, takeaway
                )

            # Sort by rating (descending)
            restaurants = sorted(
                restaurants, key=lambda r: r.get("rating", 0), reverse=True
            )
            top_rating = restaurants[0].get("rating") if restaurants else 0
            self.logger.debug(
                f"⭐ Sorted by rating: "
                f"count={len(restaurants)} "
                f"top_rating={top_rating} "
                f"note='Sorted restaurants by rating (highest first)'"
            )

            # Limit results
            restaurants = restaurants[:max_results]

            # Format response
            response_text = f"Restaurants in {location}:\n\n"

            if cuisine:
                response_text = f"{cuisine.capitalize()} Restaurants in {location}:\n\n"

            for idx, restaurant in enumerate(restaurants, 1):
                name = restaurant.get("name", "Unknown")
                cuisine_type = restaurant.get("cuisine", "Unknown")
                rating = restaurant.get("rating", 0)
                price = restaurant.get("price", "$$")
                rest_type = restaurant.get("type", "indoor")

                response_text += f"{idx}. {name}\n"
                response_text += f"   Cuisine: {cuisine_type.capitalize()}\n"

                if self.include_ratings:
                    stars = "⭐" * int(rating)
                    response_text += f"   Rating: {stars} {rating}/5.0\n"

                response_text += f"   Price: {price}\n"

                if rest_type == "outdoor":
                    response_text += "   🌤️ Outdoor seating available\n"

                response_text += "\n"

            response_text += f"Total: {len(restaurants)} restaurants found"

            # Add note about ratings
            if self.include_ratings:
                avg_rating = (
                    sum(r.get("rating", 0) for r in restaurants) / len(restaurants)
                    if restaurants
                    else 0
                )
                response_text += f"\n\nAverage rating: {avg_rating:.1f}/5.0"

            # Structure data for other agents
            filters_applied = {}
            if cuisine:
                filters_applied["cuisine"] = cuisine
            if price_range:
                filters_applied["price_range"] = price_range
            if dietary_restrictions:
                filters_applied["dietary_restrictions"] = dietary_restrictions
            if outdoor_seating:
                filters_applied["outdoor_seating"] = True
            if delivery:
                filters_applied["delivery"] = True
            if takeaway:
                filters_applied["takeaway"] = True

            result_data = {
                "location": location,
                "restaurants": restaurants,
                "total_count": len(restaurants),
                "average_rating": avg_rating if restaurants else 0,
                "filters_applied": filters_applied,
                "cuisine_filter": cuisine,  # Keep for backward compatibility
                "price_filter": price_range,  # Keep for backward compatibility
                "timestamp": datetime.now(UTC).isoformat(),
            }

            top_3 = [r.get("name", "N/A") for r in restaurants[:3]]
            self.logger.info(
                f"✅ RESTAURANT OUTPUT - Search completed: "
                f"task_id={task.id} "
                f"location={location} "
                f"total_results={len(restaurants)} "
                f"avg_rating={avg_rating if restaurants else 0} "
                f"filters_applied={filters_applied} "
                f"result_keys={list(result_data.keys())} "
                f"top_3={top_3}"
            )

            return self._create_success_task(task, response_text, result_data)

        except Exception as e:
            import traceback

            tb = traceback.format_exc()[:500]
            self.logger.error(
                f"❌ EXCEPTION in _find_restaurants: {e!s} "
                f"task_id={task.id} "
                f"location={location} "
                f"cuisine={cuisine} "
                f"price_range={price_range} "
                f"exception_type={type(e).__name__} "
                f"traceback={tb}",
                exc_info=True,
            )
            return self._create_error_task(task, f"Restaurant search failed: {e!s}")

    def _fetch_restaurants_data(self, location: str) -> list[dict[str, Any]]:
        """
        Fetch restaurants data from configured source.

        Args:
            location: City name

        Returns:
            List of restaurants
        """
        self.logger.debug(
            f"📊 Fetching restaurant data: "
            f"operation=fetch_restaurants_data "
            f"location={location} "
            f"note='Using mock data for workshop demonstration'"
        )

        # Always use mock data for workshop
        data = self.mock_factory.get_restaurants(location)
        count = len(data) if data else 0
        self.logger.debug(
            f"✓ Mock restaurant data loaded: "
            f"location={location} "
            f"restaurants_count={count} "
            f"note='Mock data includes diverse cuisine types and ratings for Seattle'"
        )
        return data

    def _filter_by_dietary(
        self, restaurants: list[dict[str, Any]], dietary_restrictions: list[str]
    ) -> list[dict[str, Any]]:
        """
        Filter restaurants by dietary restrictions.

        Uses ALL-OF logic: Restaurant must satisfy ALL requested restrictions.

        Args:
            restaurants: List of restaurant dicts
            dietary_restrictions: List of dietary requirement strings
                (vegan, vegetarian, gluten_free, lactose_free, halal, kosher, dairy_free, pescetarian)

        Returns:
            Filtered list of restaurants
        """
        if not dietary_restrictions:
            return restaurants

        filtered = []
        for r in restaurants:
            dietary_info = r.get("dietary")

            # Skip if no dietary info (null or missing)
            if not dietary_info:
                continue

            # Check if ALL restrictions are satisfied
            if all(dietary_info.get(diet) is True for diet in dietary_restrictions):
                filtered.append(r)

        self.logger.debug(
            f"🥗 Dietary filter applied: "
            f"restrictions={dietary_restrictions} "
            f"before_count={len(restaurants)} "
            f"after_count={len(filtered)} "
            f"note='ALL-OF logic: restaurant must have ALL requested dietary options'"
        )

        return filtered

    def _filter_by_amenities(
        self,
        restaurants: list[dict[str, Any]],
        outdoor_seating: bool | None = None,
        delivery: bool | None = None,
        takeaway: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Filter restaurants by amenities.

        Uses AND logic: Restaurant must have ALL requested amenities.

        Args:
            restaurants: List of restaurant dicts
            outdoor_seating: Filter for outdoor seating
            delivery: Filter for delivery service
            takeaway: Filter for takeaway service

        Returns:
            Filtered list of restaurants
        """
        filtered = restaurants
        initial_count = len(filtered)

        if outdoor_seating:
            filtered = [r for r in filtered if r.get("outdoor_seating") is True]
            self.logger.debug(
                f"🌤️ Outdoor seating filter: {len(restaurants)} → {len(filtered)}"
            )

        if delivery:
            before_delivery = len(filtered)
            filtered = [r for r in filtered if r.get("delivery") is True]
            self.logger.debug(
                f"🚗 Delivery filter: {before_delivery} → {len(filtered)}"
            )

        if takeaway:
            before_takeaway = len(filtered)
            filtered = [r for r in filtered if r.get("takeaway") is True]
            self.logger.debug(
                f"🥡 Takeaway filter: {before_takeaway} → {len(filtered)}"
            )

        if initial_count != len(filtered):
            amenities_requested = []
            if outdoor_seating:
                amenities_requested.append("outdoor_seating")
            if delivery:
                amenities_requested.append("delivery")
            if takeaway:
                amenities_requested.append("takeaway")

            self.logger.debug(
                f"🏪 Amenity filter summary: "
                f"amenities={amenities_requested} "
                f"before_count={initial_count} "
                f"after_count={len(filtered)}"
            )

        return filtered


# ============================================================================
# Standard Entry Points for Agent Launcher
# ============================================================================


def get_agent() -> RestaurantAgent:
    """
    Create and return RestaurantAgent instance.

    Called by agent_launcher.py to initialize the agent.

    Returns:
        RestaurantAgent instance
    """
    agent = RestaurantAgent()
    agent.initialize()
    return agent


def get_http_app(agent: RestaurantAgent):
    """
    Create and return FastAPI app for RestaurantAgent.

    Called by agent_launcher.py to initialize HTTP server.

    Args:
        agent: RestaurantAgent instance

    Returns:
        FastAPI application instance
    """
    from datetime import datetime
    import json

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Restaurant Agent", version="1.0.0")

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {
            "status": "ok",
            "agent": "restaurant-agent",
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

            # Process task (using Task imported at module level - line 45)
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

    logger.info("🚀 Starting RestaurantAgent...")
    agent = get_agent()

    logger.info(
        "✓ Agent initialized",
    )

    for cap in agent.capabilities:
        logger.info(f"  Capability: {cap.id}")
