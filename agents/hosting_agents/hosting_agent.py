import asyncio
import os

# Google ADK imports
from google.adk.agents import Agent, LlmAgent

# ==================== REMOTE A2A AGENT ====================
# from pydantic import Field
# class RemoteA2AAgent(Agent):
#     """Wrapper for existing A2A agent servers as sub-agents"""
#     base_url: str = Field(..., description="URL of the remote agent")
#     def __init__(self, name: str, description: str, base_url: str):
#         super().__init__(name=name, description=description)
#         self.base_url = base_url
#     async def invoke(self, input_text: str, **kwargs) -> str:
#         """Invoke the remote A2A agent"""
#         import httpx
#         import json
#         try:
#             # A2A JSON-RPC format
#             payload = {
#                 "jsonrpc": "2.0",
#                 "method": "invoke",
#                 "params": {
#                     "input": input_text,
#                     "session_id": kwargs.get(
#                         "session_id", f"session_{hash(input_text)}"
#                     ),
#                 },
#                 "id": 1,
#             }
#             async with httpx.AsyncClient(timeout=30.0) as client:
#                 response = await client.post(
#                     f"{self.base_url}/invoke",
#                     json=payload,
#                     headers={"Content-Type": "application/json"},
#                 )
#                 if response.status_code == 200:
#                     result = response.json()
#                     if "result" in result:
#                         output = result["result"]["output"]
#                         # Format as from this sub-agent
#                         return f"## From {self.name}:\n{output}"
#                     elif "error" in result:
#                         return (
#                             f"**Error from {self.name}:** {result['error']['message']}"
#                         )
#                 return f"**Failed to get response from {self.name}**"
#         except Exception as e:
#             return f"**Connection error with {self.name}:** {str(e)}"
from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ==================== MAIN HEALTHCARE ORCHESTRATOR ====================
async def main() -> None:
    print("Building Healthcare Orchestrator with ADK Sub-Agents")
    host = os.getenv("AGENT_HOST", "localhost")
    policy_agent_port = os.getenv("POLICY_AGENT_PORT", "8887")
    research_agent_port = os.getenv("RESEARCH_AGENT_PORT", "8888")
    provider_agent_port = os.getenv("PROVIDER_AGENT_PORT", "8889")

    # 1. Create RemoteA2AAgent instances as SUB-AGENTS
    policy_agent = RemoteA2aAgent(
        name="PolicyAgent",
        description="Checks health insurance policy details for coverage, co-pays, and deductibles.",
        agent_card=(
            f"http://localhost:{policy_agent_port}{AGENT_CARD_WELL_KNOWN_PATH}"
        ),
    )

    research_agent = RemoteA2aAgent(
        name="ResearchAgent",
        description="Researches medical conditions, symptoms, and treatments.",
        agent_card=(
            f"http://localhost:{research_agent_port}{AGENT_CARD_WELL_KNOWN_PATH}"
        ),
    )

    provider_agent = RemoteA2aAgent(
        name="ProviderAgent",
        description="Finds in-network healthcare providers and facilities.",
        agent_card=(
            f"http:/localhost:{provider_agent_port}{AGENT_CARD_WELL_KNOWN_PATH}"
        ),
    )

    print(f"\t✅ Created remote sub-agents")

    # 2. Create Healthcare Orchestrator with SUB-AGENTS
    healthcare_orchestrator = LlmAgent(
        name="HealthcareOrchestrator",
        description="A personal concierge for Healthcare Information, customized to your policy.",
        model=LiteLlm("bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        # CRITICAL: Use sub_agents, not tools!
        sub_agents=[policy_agent, research_agent, provider_agent],
        instruction="""You are a concierge for healthcare services. You manage a team of specialist agents:

        **Your Sub-Agents:**
        1. **Policy Agent** - Handles insurance questions
        2. **Research Agent** - Handles medical information
        3. **Provider Agent** - Finds healthcare providers

        **How to Delegate:**
        - When you need information from a specialist, DELEGATE to the appropriate sub-agent
        - The sub-agent will respond, and you should integrate their response
        - You can delegate to multiple sub-agents if needed
        - Always wait for sub-agent responses before proceeding

        **Delegation Rules:**
        1. **Insurance questions** → Delegate to Policy Agent FIRST
        2. **Medical/symptom questions** → Delegate to Research Agent
        3. **Finding doctors** → Delegate to Provider Agent (after insurance check)

        **Output Requirements:**
        - Start with a brief acknowledgment
        - Show sub-agent responses clearly labeled
        - Synthesize a final summary that addresses all aspects
        - ALWAYS attribute information: "Policy Agent reported:", etc.
        - NEVER provide insurance info not from Policy Agent
        - NEVER recommend providers not from Provider Agent

        **Example Delegation:**
        User: "I have Blue Cross insurance and need a dermatologist for a skin rash"

        Your thought process:
        1. This needs insurance info → delegate to Policy Agent
        2. This needs medical info about rash → delegate to Research Agent  
        3. This needs a provider → delegate to Provider Agent
        4. Collect all responses and synthesize

        **Remember:** You're the orchestrator. Delegate to specialists, then integrate their expertise.""",
    )

    print(
        f"\t✅ Created {healthcare_orchestrator.name} with {len(healthcare_orchestrator.sub_agents)} sub-agents"
    )
    APP_NAME = "orchestrator_healthcare_app"
    USER_ID = "1234"
    SESSION_ID = "session1234"

    # Session and Runner
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    runner = Runner(
        agent=healthcare_orchestrator,
        app_name=APP_NAME,
        session_service=session_service,
    )

    print("\t✅ ADK Runner initialized")

    # 4. Test the orchestrator
    async def test_orchestration():
        """Test the sub-agent delegation"""
        test_cases = [
            {
                "query": "I have abdominal pain and Blue Cross insurance — what’s covered and who should I see nearby?",
                "expected_agents": ["Policy Agent", "Research Agent", "Provider Agent"],
                # "query": "I have Blue Cross insurance policy ID BC123. I have sharp lower abdominal pain. Can you find me a gastroenterologist?",
                # "expected_agents": ["Policy Agent", "Research Agent", "Provider Agent"],
            }
            # ,
            # {
            #     "query": "What's covered for physical therapy under my insurance plan?",
            #     "expected_agents": ["Policy Agent"],
            # },
            # {
            #     "query": "I have a rash and fever. What could it be and should I see a doctor?",
            #     "expected_agents": ["Research Agent"],
            # },
        ]

        for i, test in enumerate(test_cases):
            print(f"\n{'=' * 60}")
            print(f"Test {i + 1}: {test['query']}")
            print(f"Expected to use: {', '.join(test['expected_agents'])}")
            print(f"{'=' * 60}")

            content = types.Content(role="user", parts=[types.Part(text='Find and list of healthcare providers')])
            for event in runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
                print(f"\nDEBUG EVENT: {event.author}\n")
                if event.is_final_response() and event.content:
                    final_answer = event.content.parts[0].text.strip()
                    print("\n🟢 FINAL ANSWER\n", final_answer, "\n")

    # Run test
    print("\n🧪 Testing sub-agent delegation...")
    await test_orchestration()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
