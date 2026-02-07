# Agent Implementations

This directory contains all specialist agent implementations for the A2A orchestration system.

## Existing Agents

| Agent | Type | Capability | Description |
|-------|------|------------|-------------|
| `weather_agent` | Primary | `get-weather` | Weather forecasts |
| `location_loader` | Primary | `load-locations` | Raw data loading |
| `restaurant_agent` | Primary | `refine-restaurants` | Restaurant filtering |
| `events_agent` | Primary | `refine-events` | Event filtering |
| `geography_agent` | Enhancement | `filter-by-proximity` | Proximity filtering |
| `budget_agent` | Primary | `plan-budget` | Budget allocation (LLM-powered) |

## Creating New Agents

**For comprehensive documentation, see:**
- [Agent Creation Guide](../.claude/docs/reference/agent-creation-guide.md) - Architecture and patterns
- [BaseAgent Template](../.claude/docs/reference/base-agent-template.md) - Rule-based agent template
- [AgenticBaseAgent Template](../.claude/docs/reference/agentic-base-agent-template.md) - LLM-powered agent template
- [Hotel Agent Walkthrough](../.claude/docs/tutorials/hotel-agent-walkthrough.md) - Step-by-step tutorial
- [Quickstart Checklist](../.claude/docs/how-to/agent-quickstart-checklist.md) - Implementation checklist

**Workshop Commands:**
- `/workshop:create-hotel-agent` - Guided hotel agent creation (Chapter 6)
- `/workshop:build-custom-agent` - Interactive custom agent builder
- `/workshop:validate-agent [name]` - Validate implementation
- `/workshop:deploy-agent [name]` - Deploy to AWS

**Consultation:**
- Use `agent-architect` for capability design help
- Use `agent-validator` for implementation validation

## Directory Structure

Each agent requires:
- `agents/<your_agent>/main.py` - Agent implementation
- `config/domains/<domain>.yaml` - Domain configuration (update)
- `services/<your-agent>/Dockerfile` - Deployment configuration

See the documentation links above for complete details.
