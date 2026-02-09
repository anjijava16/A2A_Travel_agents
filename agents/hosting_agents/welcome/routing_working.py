# pylint: disable=logging-fstring-interpolation
import asyncio
import json
import os
import uuid

from typing import Any

import httpx

from a2a.client import A2ACardResolver
from a2a.types import (
    AgentCard,
    MessageSendParams,
    Part,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
)
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.tool_context import ToolContext
from remote_agent_connection import (
    RemoteAgentConnections,
    TaskUpdateCallback,
)
from datetime import datetime


load_dotenv()


def convert_part(part: Part, tool_context: ToolContext):
    """Convert a part to text. Only text parts are supported."""
    if part.type == 'text':
        return part.text

    return f'Unknown type: {part.type}'


def convert_parts(parts: list[Part], tool_context: ToolContext):
    """Convert parts to text."""
    rval = []
    for p in parts:
        rval.append(convert_part(p, tool_context))
    return rval


def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    """Helper function to create the payload for sending a task."""
    payload: dict[str, Any] = {
        'message': {
            'role': 'user',
            'parts': [{'type': 'text', 'text': text}],
            'messageId': uuid.uuid4().hex,
        },
    }

    if task_id:
        payload['message']['taskId'] = task_id

    if context_id:
        payload['message']['contextId'] = context_id
    return payload


class RoutingAgent:
    """The Routing agent.

    This is the agent responsible for choosing which remote seller agents to send
    tasks to and coordinate their work.
    """

    def __init__(
        self,
        task_callback: TaskUpdateCallback | None = None,
    ):
        self.task_callback = task_callback
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        self.agents: str = ''

    async def _async_init_components(
        self, remote_agent_addresses: list[str]
    ) -> None:
        """Asynchronous part of initialization."""
        # Use a single httpx.AsyncClient for all card resolutions for efficiency
        async with httpx.AsyncClient(timeout=30) as client:
            for address in remote_agent_addresses:
                card_resolver = A2ACardResolver(
                    client, address
                )  # Constructor is sync
                try:
                    card = (
                        await card_resolver.get_agent_card()
                    )  # get_agent_card is async

                    remote_connection = RemoteAgentConnections(
                        agent_card=card, agent_url=address
                    )
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                except httpx.ConnectError as e:
                    print(
                        f'ERROR: Failed to get agent card from {address}: {e}'
                    )
                except Exception as e:  # Catch other potential errors
                    print(
                        f'ERROR: Failed to initialize connection for {address}: {e}'
                    )

        # Populate self.agents using the logic from original __init__ (via list_remote_agents)
        agent_info = []
        for agent_detail_dict in self.list_remote_agents():
            agent_info.append(json.dumps(agent_detail_dict))
        self.agents = '\n'.join(agent_info)

    @classmethod
    async def create(
        cls,
        remote_agent_addresses: list[str],
        task_callback: TaskUpdateCallback | None = None,
    ) -> 'RoutingAgent':
        """Create and asynchronously initialize an instance of the RoutingAgent."""
        instance = cls(task_callback)
        await instance._async_init_components(remote_agent_addresses)
        return instance

    def create_agent(self) -> Agent:
        """Create an instance of the RoutingAgent."""
        from google.adk.models.lite_llm import LiteLlm
        return Agent(
            #model='gemini-2.5-flash-lite',
            model=LiteLlm("gpt-4o-mini"),
            name='Routing_agent',
            instruction=self.root_instruction,
            before_model_callback=self.before_model_callback,
            description=(
                'This Routing agent orchestrates the decomposition of the user asking for weather forecast or airbnb accommodation'
            ),
            tools=[
                self.send_message,
            ],
        )
    def root_instruction(self, context: ReadonlyContext) -> str:
        """Root instruction for the orchestrator"""
        # First, let's see what agent names we actually have
        agent_list = "\n".join([f"- {name}" for name in self.remote_agent_connections.keys()])
        
        return f"""
        **Role:** You are the Healthcare Orchestrator, an expert coordinator for healthcare consultations. 
        Your function is to consult with specialist agents using the `send_message` tool and synthesize comprehensive healthcare guidance.

        **Available Specialist Agents:**
        {agent_list}

        **Core Workflow - MUST FOLLOW FOR EVERY QUERY:**
        1. **First**: Use `send_message` with agent_name="[ACTUAL_POLICY_AGENT_NAME]" for insurance analysis
        2. **Second**: Use `send_message` with agent_name="[ACTUAL_RESEARCH_AGENT_NAME]" for medical assessment  
        3. **Third**: Use `send_message` with agent_name="[ACTUAL_PROVIDER_AGENT_NAME]" for provider recommendations
        4. **Finally**: Synthesize all responses into comprehensive guidance

        **Tool Usage Instructions:**
        - Always use: `send_message(agent_name="ExactAgentName", task="Your task description")`
        - Use the EXACT agent names from the list above
        - Include relevant context in the task parameter

        **Example Query Handling:**
        User: "I have abdominal pain and Blue Cross insurance"
        
        Your process:
        1. `send_message(agent_name="[ACTUAL_POLICY_AGENT_NAME]", task="What does Blue Cross insurance cover for abdominal pain evaluation and treatment? User has abdominal pain.")`
        2. `send_message(agent_name="[ACTUAL_RESEARCH_AGENT_NAME]", task="What are potential causes, urgency levels, and treatments for abdominal pain?")`
        3. `send_message(agent_name="[ACTUAL_PROVIDER_AGENT_NAME]", task="Find gastroenterologists or urgent care for abdominal pain evaluation. Ask user for location if needed.")`
        4. Synthesize all responses into final answer

        **Important Rules:**
        - ALWAYS consult ALL THREE agents for comprehensive healthcare queries
        - If user doesn't provide location, ask BEFORE calling ProviderAgent
        - Present information clearly
        """
    def root_instruction11(self, context: ReadonlyContext) -> str:
        """Root instruction for the orchestrator"""
        return f"""
        **Role:** You are the Healthcare Orchestrator, an expert coordinator for healthcare consultations. 
        Your function is to consult with specialist agents using the `send_message` tool and synthesize comprehensive healthcare guidance.

        **Available Specialist Agents:**
        {self.agents}

        **Agent Descriptions:**
        1. **PolicyAgent**: Expert in insurance coverage, deductibles, co-pays, policy details
        2. **ResearchAgent**: Expert in medical conditions, symptoms, treatments, diagnoses  
        3. **ProviderAgent**: Expert in finding doctors, specialists, healthcare facilities

        **Core Workflow - MUST FOLLOW FOR EVERY QUERY:**
        1. **First**: Use `send_message` with agent_name="PolicyAgent" for insurance analysis
        2. **Second**: Use `send_message` with agent_name="ResearchAgent" for medical assessment
        3. **Third**: Use `send_message` with agent_name="ProviderAgent" for provider recommendations
        4. **Finally**: Synthesize all responses into comprehensive guidance

        **Tool Usage Instructions:**
        - Always use: `send_message(agent_name="AgentName", task="Your task description")`
        - Include relevant context in the task parameter
        - For ProviderAgent, include location if available

        **Example Query Handling:**
        User: "I have abdominal pain and Blue Cross insurance"
        
        Your process:
        1. `send_message(agent_name="PolicyAgent", task="What does Blue Cross insurance cover for abdominal pain evaluation and treatment?")`
        2. `send_message(agent_name="ResearchAgent", task="What are potential causes, urgency levels, and treatments for abdominal pain?")`
        3. `send_message(agent_name="ProviderAgent", task="Find gastroenterologists or urgent care for abdominal pain evaluation. Location: [ask user if not provided]")`
        4. Synthesize all responses into final answer

        **Important Rules:**
        - ALWAYS consult ALL THREE agents for comprehensive healthcare queries
        - ALWAYS follow the sequence: Policy → Research → Provider
        - If user doesn't provide location, ask before calling ProviderAgent
        - Present information clearly, attributing each specialist
        - Highlight urgent medical advice immediately
        - Format responses for easy reading (use bullet points, sections)

        **Today's Date:** {datetime.now().strftime("%Y-%m-%d")}

        **CRITICAL:** Your value is in coordinating ALL specialists. Do not skip any agents.
        """

    def check_active_agent(self, context: ReadonlyContext):
        state = context.state
        if (
            'session_id' in state
            and 'session_active' in state
            and state['session_active']
            and 'active_agent' in state
        ):
            return {'active_agent': f'{state["active_agent"]}'}
        return {'active_agent': 'None'}

    def before_model_callback(
        self, callback_context: CallbackContext, llm_request
    ):
        state = callback_context.state
        if 'session_active' not in state or not state['session_active']:
            if 'session_id' not in state:
                state['session_id'] = str(uuid.uuid4())
            state['session_active'] = True

    def list_remote_agents(self):
        """List the available remote agents you can use to delegate the task."""
        if not self.cards:
            return []

        remote_agent_info = []
        for card in self.cards.values():
            print(f'Found agent card: {card.model_dump(exclude_none=True)}')
            print('=' * 100)
            remote_agent_info.append(
                {'name': card.name, 'description': card.description}
            )
        return remote_agent_info

    async def send_message(
        self, agent_name: str, task: str, tool_context: ToolContext
    ):
        """Sends a task to remote seller agent.

        This will send a message to the remote agent named agent_name.

        Args:
            agent_name: The name of the agent to send the task to.
            task: The comprehensive conversation context summary
                and goal to be achieved regarding user inquiry and purchase request.
            tool_context: The tool context this method runs in.

        Yields:
            A dictionary of JSON data.
        """
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f'Agent {agent_name} not found')
        state = tool_context.state
        state['active_agent'] = agent_name
        client = self.remote_agent_connections[agent_name]

        if not client:
            raise ValueError(f'Client not available for {agent_name}')
        task_id = state['task_id'] if 'task_id' in state else str(uuid.uuid4())

        if 'context_id' in state:
            context_id = state['context_id']
        else:
            context_id = str(uuid.uuid4())

        message_id = ''
        metadata = {}
        if 'input_message_metadata' in state:
            metadata.update(**state['input_message_metadata'])
            if 'message_id' in state['input_message_metadata']:
                message_id = state['input_message_metadata']['message_id']
        if not message_id:
            message_id = str(uuid.uuid4())

        payload = {
            'message': {
                'role': 'user',
                'parts': [
                    {'type': 'text', 'text': task}
                ],  # Use the 'task' argument here
                'messageId': message_id,
            },
        }

        # if task_id:
        #     payload['message']['taskId'] = task_id

        # if context_id:
        #     payload['message']['contextId'] = context_id

        message_request = SendMessageRequest(
            id=message_id, params=MessageSendParams.model_validate(payload)
        )
        send_response: SendMessageResponse = await client.send_message(
            message_request=message_request
        )
        print(
            'send_response',
            send_response.model_dump_json(exclude_none=True, indent=2),
        )

        if not isinstance(send_response.root, SendMessageSuccessResponse):
            print('received non-success response. Aborting get task ')
            return None

        if not isinstance(send_response.root.result, Task):
            print('received non-task response. Aborting get task ')
            return None

        return send_response.root.result


def _get_initialized_routing_agent_sync() -> Agent:
    """Synchronously creates and initializes the RoutingAgent."""

    async def _async_main() -> Agent:
        routing_agent_instance = await RoutingAgent.create(
            # remote_agent_addresses=[
            #     os.getenv('AIR_AGENT_URL', 'http://localhost:8887'),
            #     os.getenv('WEA_AGENT_URL', 'http://localhost:8887'),
            # ]
            remote_agent_addresses=[
                    "http://localhost:8887",  # PolicyAgent
                    "http://localhost:8888",  # ResearchAgent  
                    "http://localhost:8889",  # ProviderAgent
                ]
        )
        return routing_agent_instance.create_agent()

    try:
        return asyncio.run(_async_main())
    except RuntimeError as e:
        if 'asyncio.run() cannot be called from a running event loop' in str(e):
            print(
                f'Warning: Could not initialize RoutingAgent with asyncio.run(): {e}. '
                'This can happen if an event loop is already running (e.g., in Jupyter). '
                'Consider initializing RoutingAgent within an async function in your application.'
            )
        raise


root_agent = _get_initialized_routing_agent_sync()


from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

import asyncio
import time

# Google ADK imports
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


APP_NAME = 'routing_app'
USER_ID = 'default_user'
SESSION_ID = 'default_session'




# 4. Test the orchestrator
async def test_orchestration():
    """Test the sub-agent delegation"""
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    ROUTING_AGENT_RUNNER = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    # test_cases = [
    #     {
    #         "query": "I have abdominal pain and Blue Cross insurance — what’s covered and who should I see nearby?",
    #         "expected_agents": ["Policy Agent", "Research Agent", "Provider Agent"],
    #     }
    # ]
    test_cases = [
        {
            "query": "I have abdominal pain and Blue Cross insurance — what’s covered and who should I see nearby?",
            "expected_agents": ["PolicyAgent", "ResearchAgent", "ProviderAgent"],
        }
    ]

    for i, test in enumerate(test_cases):
        print(f"\n{'=' * 60}")
        print(f"Test {i + 1}: {test['query']}")
        print(f"Expected to use: {', '.join(test['expected_agents'])}")
        print(f"{'=' * 60}")

        content = types.Content(role="user", parts=[types.Part(text=test['query'])])
        for event in ROUTING_AGENT_RUNNER.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
            print(f"\nDEBUG EVENT: {event.author}\n")
            if event.is_final_response() and event.content:
                final_answer = event.content.parts[0].text.strip()
                print("\n🟢 FINAL ANSWER\n", final_answer, "\n")
import asyncio
asyncio.run(test_orchestration())