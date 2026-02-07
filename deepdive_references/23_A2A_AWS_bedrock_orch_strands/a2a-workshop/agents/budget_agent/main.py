#!/usr/bin/env python3
"""
Budget Planning Agent - Travel Domain

Budget allocation agent using LLM reasoning for trade-off decisions.

This agent demonstrates strategic LLM usage:
- Tools are deterministic (data filtering, math calculations)
- LLM provides reasoning (trade-offs, subjective preferences, explanations)

Key capabilities:
- Understands subjective preferences ("good food" vs "save money")
- Makes trade-off decisions (quality vs cost vs variety)
- Balances multiple constraints (budget + dietary + preferences)
- Provides natural language explanations of reasoning

Example queries:
- "Plan $1000 budget for 2 people in Seattle for 3 days"
- "Allocate budget with good food preference"
- "Budget-friendly dining and entertainment for 4 people"
"""

from datetime import UTC
import json
from typing import Any

from a2a.types import Task
from strands.tools import tool

from lib.agents import AgentCapability
from lib.agents.agentic_base import AgenticBaseAgent
from lib.agents.config_loader import get_agent_config, load_domain_config
from lib.agents.mock_data_factory import MockDataFactory
from lib.logger import get_logger

logger = get_logger()


class BudgetPlanningAgent(AgenticBaseAgent):
    """
    Budget Planning Agent using LLM reasoning.

    This agent uses Strands + Claude for genuine reasoning about:
    - Budget allocation across categories (dining, entertainment, attractions)
    - Trade-off decisions (quality vs cost)
    - Subjective preference interpretation ("good food", "save money")
    - Natural language explanations of decisions
    """

    def __init__(
        self,
        domain: str = "travel",
        agent_name: str = "budget-agent",
        config: dict[str, Any] | None = None,
    ):
        """Initialize Budget Planning Agent."""
        # Initialize mock data factory (needed by tools)
        self.mock_factory = MockDataFactory(domain)

        # Load domain configuration
        try:
            domain_config = load_domain_config(domain)
            agent_config = get_agent_config(domain_config, "budget")
            self.agent_config = agent_config.config
        except Exception as e:
            logger.warning(f"Could not load domain config: {e}")
            self.agent_config = {}

        # Call parent init (this creates Strands Agent with tools + system prompt)
        super().__init__(domain, agent_name, config)

        logger.info("Budget Planning Agent initialized with LLM reasoning")

    def _define_agent_tools(self) -> list:
        """
        Define tools for budget planning.

        Tools are DETERMINISTIC operations that the LLM can use.
        The LLM decides WHEN and HOW to use them based on reasoning.
        """

        @tool(
            name="get_restaurants_by_price_tier",
            description="Get restaurants filtered by maximum price tier. Use when planning dining budget. Price tiers: $ (budget $10-15pp), $$ (moderate $20-30pp), $$$ (upscale $40-60pp), $$$$ (fine dining $70+pp). Tier includes all lower tiers (e.g., $$ includes $ and $$).",
        )
        def get_restaurants_by_price_tier(
            geography: str,
            max_price_tier: str,
            cuisine: str | None = None,
            dietary: str | None = None,
        ) -> dict[str, Any]:
            """
            Filter restaurants by price tier.

            Args:
                geography: City/location (e.g., "Seattle", "Portland")
                max_price_tier: "$", "$$", "$$$", or "$$$$"
                cuisine: Optional cuisine filter (e.g., "italian", "thai")
                dietary: Optional dietary restriction ("vegan", "vegetarian", "gluten_free")

            Returns:
                {
                    "restaurants": [...],  # List of restaurant objects
                    "count": int,
                    "price_range": {"min": float, "max": float},
                    "avg_rating": float,
                    "filters_applied": {...}
                }
            """
            # Map price tiers to inclusive list
            tier_map = {
                "$": ["$"],
                "$$": ["$", "$$"],
                "$$$": ["$", "$$", "$$$"],
                "$$$$": ["$", "$$", "$$$", "$$$$"],
            }

            allowed_tiers = tier_map.get(max_price_tier, ["$"])

            # Get restaurant data from mock factory
            all_restaurants = self.mock_factory.get_restaurants(geography)

            # Filter by price tier
            filtered = [r for r in all_restaurants if r.get("price") in allowed_tiers]

            # Apply cuisine filter if specified
            if cuisine:
                cuisine_lower = cuisine.lower()
                filtered = [
                    r for r in filtered if cuisine_lower in r.get("cuisine", "").lower()
                ]

            # Apply dietary filter if specified
            if dietary:
                dietary_key = dietary.lower().replace("_", "")
                filtered = [
                    r for r in filtered if r.get("dietary", {}).get(dietary_key, False)
                ]

            # Calculate stats
            avg_rating = (
                sum(r.get("rating", 0) for r in filtered) / len(filtered)
                if filtered
                else 0
            )

            # Price ranges per tier (per person estimates)
            price_ranges = {
                "$": (10, 15),
                "$$": (20, 30),
                "$$$": (40, 60),
                "$$$$": (70, 120),
            }

            min_price = min(price_ranges[t][0] for t in allowed_tiers)
            max_price = max(price_ranges[t][1] for t in allowed_tiers)

            return {
                "restaurants": filtered[:20],  # Limit to top 20 for token efficiency
                "count": len(filtered),
                "price_range": {"min": min_price, "max": max_price},
                "avg_rating": round(avg_rating, 2),
                "filters_applied": {
                    "max_price_tier": max_price_tier,
                    "cuisine": cuisine,
                    "dietary": dietary,
                },
            }

        @tool(
            name="get_entertainment_under_budget",
            description="Find entertainment venues under price limit. Use for activity planning. Categories: cinema ($15), theater ($50), nightlife ($25), music_venue ($25-50). Returns venues within budget constraint.",
        )
        def get_entertainment_under_budget(
            geography: str,
            max_price_per_activity: float,
            categories: list[str] | None = None,
        ) -> dict[str, Any]:
            """
            Filter entertainment by max price.

            Args:
                geography: City/location (e.g., "Seattle", "San Francisco")
                max_price_per_activity: Maximum price per person per activity
                categories: Optional list ["cinema", "theater", "nightlife", "music_venue"]

            Returns:
                {
                    "entertainment": [...],  # List of venue objects
                    "count": int,
                    "categories_available": List[str],
                    "price_breakdown": {...}  # Stats by category
                }
            """
            # Get entertainment data from mock factory
            all_venues = self.mock_factory.get_entertainment(geography)

            # Filter by max price
            filtered = [
                v for v in all_venues if v.get("price", 0) <= max_price_per_activity
            ]

            # Apply category filter if specified
            if categories:
                filtered = [v for v in filtered if v.get("category") in categories]

            # Group by category
            by_category = {}
            for venue in filtered:
                cat = venue.get("category", "other")
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(venue)

            # Calculate price breakdown
            price_breakdown = {}
            for cat, venues in by_category.items():
                if venues:
                    prices = [v.get("price", 0) for v in venues]
                    price_breakdown[cat] = {
                        "count": len(venues),
                        "avg_price": round(sum(prices) / len(prices), 2),
                        "price_range": (min(prices), max(prices)),
                    }

            return {
                "entertainment": filtered[:15],  # Limit for token efficiency
                "count": len(filtered),
                "categories_available": list(by_category.keys()),
                "price_breakdown": price_breakdown,
                "filters_applied": {
                    "max_price_per_activity": max_price_per_activity,
                    "categories": categories,
                },
            }

        @tool(
            name="calculate_budget_allocation",
            description="Validate budget feasibility and calculate recommended allocation across categories. ALWAYS use this before making final recommendations. Checks if budget is sufficient and recommends allocation percentages.",
        )
        def calculate_budget_allocation(
            total_budget: float,
            num_people: int,
            num_days: int,
            meals_per_day: int = 2,
            entertainment_per_day: int = 1,
            attractions_per_day: int = 1,
        ) -> dict[str, Any]:
            """
            Calculate and validate budget allocation.

            Args:
                total_budget: Total budget available for the trip
                num_people: Number of people in travel party
                num_days: Number of days for the trip
                meals_per_day: Number of restaurant meals per day (default 2)
                entertainment_per_day: Number of entertainment activities per day (default 1)
                attractions_per_day: Number of paid attractions per day (default 1)

            Returns:
                {
                    "is_feasible": bool,
                    "per_person_budget": float,
                    "daily_budget": float,
                    "recommended_allocation": {
                        "meals": {"daily_budget": float, "recommended_tier": str},
                        "entertainment": {"daily_budget": float, "recommended_categories": [...]},
                        "attractions": {"daily_budget": float}
                    },
                    "warnings": List[str],
                    "alternatives": List[str]
                }
            """
            # Calculate per-person and daily budgets
            per_person_budget = total_budget / num_people
            daily_budget = per_person_budget / num_days

            # Price assumptions for calculations
            price_tiers = {"$": 12.5, "$$": 25, "$$$": 50, "$$$$": 95}

            entertainment_prices = {
                "cinema": 15,
                "theater": 50,
                "nightlife": 25,
                "music_venue": 35,
            }

            attraction_avg = 10  # Average attraction cost

            # Calculate minimum daily costs
            min_meals_cost = meals_per_day * price_tiers["$"]
            min_entertainment_cost = (
                entertainment_per_day * entertainment_prices["cinema"]
            )
            min_attractions_cost = attractions_per_day * attraction_avg
            min_daily_total = (
                min_meals_cost + min_entertainment_cost + min_attractions_cost
            )

            # Determine feasibility
            is_feasible = daily_budget >= min_daily_total

            # Recommend allocation based on budget
            warnings = []
            alternatives = []

            if daily_budget < min_daily_total:
                warnings.append(
                    f"Daily budget (${daily_budget:.2f}) is below minimum (${min_daily_total:.2f})"
                )
                alternatives.append(
                    f"Consider reducing to {meals_per_day - 1} meals per day"
                )
                alternatives.append("Consider free entertainment options")
                recommended_tier = "$"
                recommended_entertainment = ["cinema"]
            elif daily_budget < min_daily_total * 2:
                recommended_tier = "$"
                recommended_entertainment = ["cinema", "nightlife"]
                warnings.append("Budget allows basic options only")
            elif daily_budget < min_daily_total * 4:
                recommended_tier = "$$"
                recommended_entertainment = ["cinema", "theater", "nightlife"]
            else:
                recommended_tier = "$$$"
                recommended_entertainment = ["theater", "music_venue", "nightlife"]

            # Calculate recommended allocation
            meal_allocation = daily_budget * 0.50  # 50% for meals
            entertainment_allocation = daily_budget * 0.30  # 30% for entertainment
            attractions_allocation = daily_budget * 0.20  # 20% for attractions

            return {
                "is_feasible": is_feasible,
                "per_person_budget": round(per_person_budget, 2),
                "daily_budget": round(daily_budget, 2),
                "recommended_allocation": {
                    "meals": {
                        "daily_budget": round(meal_allocation, 2),
                        "recommended_tier": recommended_tier,
                        "avg_cost_per_meal": round(meal_allocation / meals_per_day, 2),
                    },
                    "entertainment": {
                        "daily_budget": round(entertainment_allocation, 2),
                        "recommended_categories": recommended_entertainment,
                        "avg_cost_per_activity": round(
                            entertainment_allocation / entertainment_per_day, 2
                        ),
                    },
                    "attractions": {
                        "daily_budget": round(attractions_allocation, 2),
                        "recommended_count": attractions_per_day,
                    },
                },
                "total_trip_cost_estimate": {
                    "min": round(min_daily_total * num_days * num_people, 2),
                    "recommended": round(daily_budget * num_days * num_people, 2),
                    "max": round(total_budget, 2),
                },
                "warnings": warnings,
                "alternatives": alternatives if not is_feasible else [],
            }

        return [
            get_restaurants_by_price_tier,
            get_entertainment_under_budget,
            calculate_budget_allocation,
        ]

    def _get_agent_system_prompt(self) -> str:
        """
        System prompt teaching LLM how to reason about budget allocation.

        This is WHERE the intelligence comes from - the prompt guides
        the LLM on HOW to make trade-off decisions based on subjective preferences.
        """
        return """You are a budget planning specialist for travelers.

## Your Role
Help travelers allocate budgets across dining, entertainment, and attractions while balancing quality, cost, and preferences.

## Your Tools

1. **get_restaurants_by_price_tier(geography, max_price_tier, cuisine, dietary)**
   - Filters restaurants by price tier ($ to $$$$)
   - Price tiers: $ = $10-15pp, $$ = $20-30pp, $$$ = $40-60pp, $$$$ = $70+pp
   - Tier includes lower tiers (e.g., $$ includes $ and $$)
   - Optional filters: cuisine, dietary restrictions

2. **get_entertainment_under_budget(geography, max_price_per_activity, categories)**
   - Finds entertainment venues under price limit
   - Cinema $15, Theater $50, Nightlife $25, Music $25-50
   - Optional category filter

3. **calculate_budget_allocation(total_budget, num_people, num_days, ...)**
   - Validates budget feasibility
   - Recommends allocation across categories
   - ALWAYS use this FIRST before making recommendations

## How to Reason About Budgets

### Step 1: Parse User Intent
Extract from the query:
- Total budget and party size
- Trip duration (days)
- Preferences:
  - "nice dinner" / "good food" = prioritize dining quality (60-70% to meals)
  - "save money" / "budget-friendly" = conservative spending (40-50% to meals)
  - "maximize activities" = prioritize entertainment (50-60% to activities)
- Constraints: dietary restrictions, cuisine preferences

### Step 2: Calculate Feasibility
ALWAYS call calculate_budget_allocation FIRST to:
- Check if budget is sufficient for the trip
- Get daily per-person budget
- Understand minimum costs
- Get recommended allocation percentages

### Step 3: Make Trade-Off Decisions
Based on user preferences, adjust allocation:
- **"Good food" / "Nice dinner"** → Allocate 60-70% to dining ($$$ tier)
- **"Save money" / "Budget"** → Allocate 40-50% to dining ($ or $$ tier)
- **"Maximize activities"** → Allocate 50-60% to entertainment
- **Default (balanced)**: 50% meals, 30% entertainment, 20% attractions

### Step 4: Get Options
Call tools to fetch actual options within budget:
- get_restaurants_by_price_tier with recommended tier
- get_entertainment_under_budget with remaining budget per activity

### Step 5: Present Recommendations
Provide 2-3 options showing different trade-offs:
- **Option A (Recommended)**: Best balance of quality and budget
- **Option B (Budget-conscious)**: More affordable, leaves buffer
- **Option C (Splurge)**: Maximum quality if budget allows

### Step 6: Explain Reasoning
ALWAYS explain WHY you made these allocation decisions:
- "I allocated 65% to dining because you wanted 'good food'"
- "This leaves $150 buffer (7.5%) for unexpected costs like tips or parking"
- "Theater tickets ($50) would exceed your entertainment budget of $40/day, so I suggest cinema ($15) or nightlife ($25)"

## Important Guidelines

1. **NEVER exceed the total budget** - this is a hard constraint
2. **ALWAYS call calculate_budget_allocation FIRST** before making recommendations
3. **ALWAYS explain your reasoning** - justify allocation percentages
4. **Provide alternatives** if budget is tight or infeasible
5. **Respect dietary restrictions** - these are non-negotiable constraints
6. **Account for per-person vs total costs** - be clear about which you're using
7. **Consider trip duration** - longer trips may need more conservative daily spending
8. **Suggest realistic activity counts** - don't over-pack the schedule

## Example Reasoning Process

User: "Plan $1000 budget for 2 people in Seattle for 3 days. Want good food."

Your reasoning:
1. Parse: $1000 total, 2 people, 3 days, preference = "good food"
2. Calculate: call calculate_budget_allocation(1000, 2, 3, 2, 1, 1)
   Result: $500/person, $166/person/day, feasible ✓
3. Reasoning: "Good food" = prioritize dining quality
   Adjust allocation: 60% to dining = $100/day/person ($$$ tier)
4. Call get_restaurants_by_price_tier("Seattle", "$$$")
   Get upscale restaurants ($40-60 per person)
5. Call get_entertainment_under_budget("Seattle", 50)
   Get entertainment under $50/activity
6. Recommend:
   - **Dining**: $$$ tier restaurants ($40-60pp x 2 meals = $80-120/day) ✓ fits $100/day budget
   - **Entertainment**: Theater ($50) or nightlife ($25) + cinema ($15) = $40/day ✓
   - **Attractions**: $16/day budget allows Space Needle ($35) spread over days
7. Explain: "I allocated 60% to dining ($100/day) because you prioritized 'good food'. This budget supports upscale $$$ restaurants for 2 meals per day. The remaining 40% covers quality entertainment ($50/day) and some paid attractions ($16/day). Total estimated cost: $990, leaving $10 buffer."

## Edge Cases

### Insufficient Budget
User: "$200 for 5 people for 5 days"
Response: "This budget is insufficient. Minimum cost is approximately $625 (5 people x 5 days x $25/day minimum). Alternatives: (1) Increase budget to $625, (2) Reduce to 2-3 days, (3) Reduce party size to 2 people, (4) Focus on free activities and budget dining."

### Conflicting Preferences
User: "Cheap but fancy restaurant"
Response: "These preferences conflict. 'Fancy' typically means $$$ tier ($40-60pp) while 'cheap' suggests $ tier ($10-15pp). I can offer: (1) $$ tier 'upscale casual' ($20-30pp) as a middle ground, (2) $$$ restaurant with cheaper entertainment to balance, or (3) $ tier with excellent ratings (4.5+ stars) for quality on a budget."

### Dietary Restrictions
User: "Vegan options required"
Response: "I've filtered all recommendations to include only restaurants with vegan options. This is a hard constraint and all suggestions respect it."

Remember: You're making judgment calls based on subjective preferences. Different allocations can be valid - the key is explaining your reasoning clearly."""

    def _define_capabilities(self) -> list[AgentCapability]:
        """Define budget planning capability for A2A discovery."""
        return [
            AgentCapability(
                id="plan-budget",
                name="Plan Budget Allocation",
                description="""Budget planning agent using LLM reasoning for trade-off decisions and strategic allocation.

USAGE: Use me AFTER restaurant-agent and hotel-agent have filtered options.
I provide the best recommendations when I can see the filtered results from other agents.

WORKFLOW:
1. Receive: Filtered restaurant/hotel options from upstream agents - PREFERRED
   OR work independently if no pre-filtered data provided
2. Analyze: Budget constraints, preferences, trade-offs
3. Return: Strategic allocation recommendations with reasoning

CAPABILITIES:
- Trade-off decisions (quality vs cost vs variety)
- Subjective preference interpretation ("good food", "save money")
- Budget feasibility analysis
- Natural language explanations of allocation decisions""",
                tags=["budget", "planning", "allocation", "trade-offs", "reasoning"],
                examples=[
                    "Plan $1000 budget for 2 people in Seattle for 3 days",
                    "Allocate budget with good food preference",
                    "Budget-friendly dining and entertainment for family of 4",
                    "Maximize activities within $500 budget",
                ],
                input_schema={
                    "type": "object",
                    "properties": {
                        "geography": {
                            "type": "string",
                            "description": "City or location for the trip",
                        },
                        "total_budget": {
                            "type": "number",
                            "description": "Total budget in dollars",
                        },
                        "num_people": {
                            "type": "integer",
                            "description": "Number of people in travel party",
                        },
                        "num_days": {
                            "type": "integer",
                            "description": "Trip duration in days",
                        },
                        "preferences": {
                            "type": "string",
                            "description": "Budget preferences (e.g., 'good food', 'save money', 'maximize activities')",
                        },
                        "dietary_restrictions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Dietary requirements (vegan, vegetarian, gluten_free)",
                        },
                        "cuisine_preference": {
                            "type": "string",
                            "description": "Preferred cuisine type",
                        },
                    },
                    "required": ["geography", "total_budget", "num_people", "num_days"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "budget_allocation": {
                            "type": "object",
                            "description": "Recommended allocation breakdown",
                        },
                        "restaurant_recommendations": {
                            "type": "array",
                            "description": "Filtered restaurants within budget",
                        },
                        "entertainment_recommendations": {
                            "type": "array",
                            "description": "Entertainment venues within budget",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Natural language explanation of allocation decisions",
                        },
                        "feasibility": {
                            "type": "object",
                            "description": "Budget feasibility analysis",
                        },
                    },
                },
            ),
        ]

    def _process_task_impl(self, task: Task, user_input: dict[str, Any]) -> Task:
        """
        Process budget planning task using LLM reasoning.

        The LLM will:
        1. Understand user preferences (subjective interpretation)
        2. Decide which tools to call and in what order
        3. Make trade-off decisions about allocation
        4. Generate natural language explanations of reasoning
        """
        user_input_preview = json.dumps(user_input, default=str)[:300]
        self.logger.info(
            f"📥 BUDGET INPUT - task_id={task.id} input={user_input_preview}"
        )

        # Extract parameters
        geography = user_input.get("geography", "Seattle")
        total_budget = user_input.get("total_budget", 1000)
        num_people = user_input.get("num_people", 2)
        num_days = user_input.get("num_days", 3)
        preferences = user_input.get("preferences", "")
        dietary = user_input.get("dietary_restrictions", [])
        cuisine = user_input.get("cuisine_preference", "")

        # Build query for LLM
        query = f"""Plan a travel budget allocation for {num_people} people visiting {geography} for {num_days} days with a total budget of ${total_budget}.

User preferences: {preferences if preferences else 'balanced allocation'}
{f'Dietary restrictions: {", ".join(dietary)}' if dietary else ''}
{f'Cuisine preference: {cuisine}' if cuisine else ''}

Please:
1. Call calculate_budget_allocation to check feasibility
2. Based on preferences, decide allocation percentages
3. Call get_restaurants_by_price_tier with appropriate tier
4. Call get_entertainment_under_budget with budget constraint
5. Provide 2-3 allocation options with clear trade-offs
6. Explain your reasoning for the recommended allocation
"""

        self.logger.info(f"🤖 Sending query to LLM: {query[:200]}...")

        # LLM processes with tools and reasoning
        try:
            response = self.strands_agent(query)
            # Extract response text safely (AgentResult may not have .text attribute)
            response_text = (
                response.text if hasattr(response, "text") else str(response)
            )
            self.logger.info(f"✅ LLM response received: {len(response_text)} chars")
        except Exception as e:
            self.logger.error(f"❌ LLM processing failed: {e}")
            error_text = f"Budget planning failed: {e!s}"
            return self._create_error_task(task, error_text)

        # Extract structured data from LLM response
        result_data = self._extract_result_data(response, **user_input)

        self.logger.info("📤 BUDGET OUTPUT - Completed successfully")

        return self._create_success_task(task, response_text, result_data)

    def _extract_result_data(self, response, **kwargs) -> dict:
        """
        Extract structured data from LLM response.

        Since the LLM response is natural language, we extract
        key information for structured output.
        """
        # Extract response text safely
        response_text = response.text if hasattr(response, "text") else str(response)

        # For now, return basic structure
        # In production, you might parse the response text more carefully
        return {
            "budget_allocation": {
                "total_budget": kwargs.get("total_budget", 0),
                "num_people": kwargs.get("num_people", 0),
                "num_days": kwargs.get("num_days", 0),
            },
            "recommendations": response_text,
            "reasoning_provided": True,
        }


# ============================================================================
# Standard Entry Points (Required by Agent Launcher)
# ============================================================================


def get_agent() -> BudgetPlanningAgent:
    """
    Create and return BudgetPlanningAgent instance.

    Called by agent_launcher.py to initialize the agent.
    """
    agent = BudgetPlanningAgent()
    agent.initialize()
    return agent


def get_http_app(agent: BudgetPlanningAgent):
    """
    Create and return FastAPI app for BudgetPlanningAgent.

    Called by agent_launcher.py to initialize HTTP server.
    """
    from datetime import datetime
    import json

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Budget Planning Agent", version="1.0.0")

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "ok",
            "agent": "budget-agent",
            "agent_type": "llm_reasoning",
            "framework": "AgenticBaseAgent + Strands",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    @app.get("/.well-known/agent.json")
    async def agent_card():
        """Agent card endpoint (A2A protocol discovery)."""
        card = agent.get_agent_card()
        return JSONResponse(card)

    @app.post("/message/send")
    async def handle_task(request: Request):
        """A2A message handler endpoint."""
        try:
            body = await request.body()
            body = body.decode("utf-8") if isinstance(body, bytes) else body
            body_json = json.loads(body)

            # A2A envelope unwrapping
            if "method" in body_json and "params" in body_json:
                if "message" in body_json["params"]:
                    task_dict = body_json["params"]["message"]
                else:
                    task_dict = body_json["params"]
            else:
                task_dict = body_json

            # Process task
            from a2a.types import Task

            task = Task.model_validate(task_dict)
            result_task = agent.process_task(task)

            return result_task.model_dump(mode="json")

        except Exception as e:
            import traceback
            import uuid

            traceback.print_exc()

            # Create error task
            from a2a.types import Message, Task, TaskState, TaskStatus, TextPart

            error_message = Message(
                role="agent",
                parts=[
                    TextPart(
                        kind="text",
                        text=f"Error processing task: {e!s}",
                        metadata={},
                    )
                ],
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

    logger.info("🚀 Starting Budget Planning Agent...")
    agent = get_agent()

    logger.info("✓ Budget Planning Agent initialized with LLM reasoning")
    logger.info(f"  Model: {agent.model_id}")
    logger.info(f"  Tools: {len(agent.tools)}")

    for tool in agent.tools:
        logger.info(f"    - {tool.name}")

    logger.info("  Capabilities:")
    for cap in agent.capabilities:
        logger.info(f"    - {cap.id}: {cap.name}")
