from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.hosting_agents.welcome.samples.python.agents.airbnb_planner_multiagent.host_agent.routing_agent import RoutingAgent
import asyncio
import time

# Google ADK imports
from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


APP_NAME = 'routing_app'
USER_ID = 'default_user'
SESSION_ID = 'default_session'

SESSION_SERVICE = InMemorySessionService()
ROUTING_AGENT_RUNNER = Runner(
    agent=RoutingAgent,
    app_name=APP_NAME,
    session_service=SESSION_SERVICE,
)

# 4. Test the orchestrator
async def test_orchestration():
    """Test the sub-agent delegation"""
    test_cases = [
        {
            "query": "I have abdominal pain and Blue Cross insurance — what’s covered and who should I see nearby?",
            "expected_agents": ["Policy Agent", "Research Agent", "Provider Agent"],
        }
    ]

    for i, test in enumerate(test_cases):
        print(f"\n{'=' * 60}")
        print(f"Test {i + 1}: {test['query']}")
        print(f"Expected to use: {', '.join(test['expected_agents'])}")
        print(f"{'=' * 60}")

        content = types.Content(role="user", parts=[types.Part(text='Find and list of healthcare providers')])
        for event in ROUTING_AGENT_RUNNER.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
            print(f"\nDEBUG EVENT: {event.author}\n")
            if event.is_final_response() and event.content:
                final_answer = event.content.parts[0].text.strip()
                print("\n🟢 FINAL ANSWER\n", final_answer, "\n")
import asyncio
asyncio.run(test_orchestration())