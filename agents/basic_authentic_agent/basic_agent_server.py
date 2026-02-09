# agent_executor.py
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message


class HelloWorldAgent:
    """Hello World agent."""
    async def invoke(self) -> str:
        return 'Hello World'


class HelloWorldAgentExecutor(AgentExecutor):
    """AgentExecutor implementation."""

    def __init__(self):
        self.agent = HelloWorldAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # Execute the agent's logic—here, we directly return "Hello World"
        result = await self.agent.invoke()
        # Publish a text message to the event queue
        await event_queue.enqueue_event(new_agent_text_message(result))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        # Cancel logic for the agent—here, we raise an exception as cancellation is not supported
        raise Exception('cancel not supported')
    

# def new_agent_text_message(
#     text: str,
#     context_id: str | None = None,
#     task_id: str | None = None,
# ) -> Message:
#     """Create a new agent message containing a single TextPart.

#     Args:
#         text: The text content of the message
#         context_id: The context ID of the message
#         task_id: The task ID of the message

#     Returns:
#         A new `Message` object with the 'agent' role
#     """
#     return Message(
#         role=Role.agent,
#         parts=[Part(root=TextPart(text=text))],
#         messageId=str(uuid.uuid4()),
#         taskId=task_id,
#         contextId=context_id,
#     )

import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)


if __name__ == '__main__':
    # Define a simple skill that returns "hello world"
    skill = AgentSkill(
        id='hello_world',
        name='Returns hello world',
        description='just returns hello world',
        tags=['hello world'],
        examples=['hi', 'hello world'],
    )

    # Define a more complex skill that returns "super hello world"
    extended_skill = AgentSkill(
        id='super_hello_world',
        name='Returns a SUPER Hello World',
        description='A more enthusiastic greeting, only for authenticated users.',
        tags=['hello world', 'super', 'extended'],
        examples=['super hi', 'give me a super hello'],
    )

    # Define a public agent card
    public_agent_card = AgentCard(
        name='Hello World Agent',
        description='Just a hello world agent',
        url='http://0.0.0.0:9999/',
        version='1.0.0',
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],  # Only basic skills for the public card
        supportsAuthenticatedExtendedCard=True,
    )

    # Define an extended agent card that returns "super hello world"
    specific_extended_agent_card = public_agent_card.model_copy(
        update={
            'name': 'Hello World Agent - Extended Edition',  # Different name
            'description': 'The full-featured hello world agent for authenticated users.',
            'version': '1.0.1',  # Can even be a different version
            # Capabilities and other fields like url, defaultInputModes, defaultOutputModes, supportsAuthenticatedExtendedCard, etc.,
            # are inherited from public_agent_card unless specified here.
            'skills': [
                skill,
                extended_skill,
            ],  # Both skills for the extended card
        }
    )

    # Create a default request handler
    request_handler = DefaultRequestHandler(
        agent_executor=HelloWorldAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    # Create an A2A server, here we use `A2AStarletteApplication` to create an A2A server
    server = A2AStarletteApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
        extended_agent_card=specific_extended_agent_card,
    )

    # Run the server, here we use `uvicorn` to run the server
    uvicorn.run(server.build(), host='0.0.0.0', port=9979)
