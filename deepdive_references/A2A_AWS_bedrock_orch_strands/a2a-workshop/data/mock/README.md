# Mock Data Directory

This directory contains comprehensive mock data for the inter-agent systems workshop. All data is self-contained, predictable, and designed for pedagogical clarity.

## Directory Structure

```
data/mock/
├── accommodations/      Budget to luxury lodging (7 options per city)
├── agent_capabilities/  Agent capability matrix for ADK routing
├── budget/              Cost indexes and budget breakdowns
├── entertainment/       Theater, music, cinema, nightlife
├── events/              Indoor/outdoor activities (16 per city)
├── food_tours/          Culinary tours, classes, brewery experiences
├── itineraries/         Pre-built trip templates by theme
├── outdoor/             Parks, trails, water sports, facilities
├── personas/            User personas for testing
├── restaurants/         Dining options (22 per city)
├── safety/              Safety scores and accessibility info
├── seasonal/            Peak seasons, crowd levels, pricing
├── services/            Healthcare, banking, emergency contacts
├── shopping/            Malls, markets, specialty shops
├── transportation/      Transit, rideshare, rental options
├── weather/             Current conditions + 7-day forecasts
└── workflow_patterns/   ADK workflow examples
```

## Coverage

- **17 Cities**: US (13), International (4)
- **270+ Events**: Mix of indoor/outdoor, free/paid
- **374 Restaurants**: 12 cuisines, 4 price tiers
- **119 Accommodations**: Budget to luxury across all cities

## Data Quality Features

### Rich Attributes
- Weather: Temperature, precipitation, UV, AQI, wind, humidity, 7-day forecast
- Events: Category, duration, price, accessibility, age restrictions, booking requirements
- Restaurants: Cuisine, price tier, ratings, dietary options, ambiance, dress code
- All data: Consistent structure, realistic values, interrelated

### Designed Relationships
- Weather affects event recommendations
- Budget constrains all selections
- Accessibility filters across categories
- Safety influences recommendations

### Edge Cases Included
- High AQI days (Los Angeles)
- Extreme weather (Denver snow, Miami thunderstorms)
- Expensive cities (NYC, SF, London cost indices)
- Limited transit cities (Las Vegas, Austin)
- Various accessibility levels
- Age-restricted venues

## Usage

### Direct Access
```python
import json
with open('data/mock/weather/locations.json') as f:
    weather = json.load(f)
    seattle_weather = weather['Seattle']
```

### Via MockDataFactory
```python
from agents.base.mock_data_factory import MockDataFactory

factory = MockDataFactory("travel")
weather = factory.get_weather("Seattle")
events = factory.get_events("Seattle")
```

See `docs/MOCK_DATA_USAGE_EXAMPLES.md` for comprehensive usage patterns.

## Regenerating Data

To add new cities with real-world data:

```bash
python3 scripts/gather_real_world_data.py --add-city "City Name"
```

This fetches real venue data from OpenStreetMap and Wikidata for restaurants, events, and hotels.

## ADK Integration

This data structure supports all ADK primitives documented in `docs/DYNAMIC_ADK.md`:

- **Router**: Weather, budget, accessibility criteria
- **Joiner**: Merge, concatenate, vote, synthesize strategies
- **Condition**: Multiple branching criteria (weather, budget, safety)
- **Agent Call**: 6+ mapped agents with clear capabilities

## Workshop Scenarios

The data enables demonstrating:

1. **Weather-Dependent Routing**: Seattle rain → indoor activities
2. **Budget-Aware Filtering**: $50/day → budget tier only
3. **Multi-City Comparison**: West Coast cities cost analysis
4. **Accessibility Requirements**: Wheelchair-friendly filtering
5. **Seasonal Planning**: Peak vs off-season pricing
6. **Cuisine Preferences**: Filter by cuisine type
7. **Safety Consciousness**: Safety scores influence recommendations
8. **Transportation Planning**: Modal selection based on walkability

## Data Maintenance

- Keep city data synchronized across all categories
- Maintain realistic price relationships
- Update seasonal data for current year
- Ensure attribute consistency

## Contributing

When adding new data:

1. Follow existing JSON structure patterns
2. Include all required attributes
3. Maintain realistic values and relationships
4. Update MockDataFactory if adding new methods
5. Add examples to MOCK_DATA_USAGE_EXAMPLES.md
6. Update this README

## See Also

- `docs/MOCK_DATA_GUIDE.md` - Detailed category documentation
- `docs/MOCK_DATA_USAGE_EXAMPLES.md` - Code examples and patterns
- `docs/DYNAMIC_ADK.md` - ADK workflow integration
- `agents/base/mock_data_factory.py` - Data access API
