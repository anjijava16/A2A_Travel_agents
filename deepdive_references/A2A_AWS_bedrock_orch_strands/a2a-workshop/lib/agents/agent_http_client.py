import json
import uuid

from a2a.types import Task
import aiohttp

from lib.config import config
from lib.logger import get_logger

# Initialize logger with component context
logger = get_logger(context={"component": "AgentHTTPClient"})


class AgentHTTPClient:
    """
    HTTP client for sending A2A tasks to remote agents.

    Provides a clean interface for agent-to-agent communication using the A2A protocol.

    Configuration:
        Uses centralized core.config module for timeout settings.
        Override via environment variables with CORE_ prefix.
        See core.config for full configuration options.
    """

    def __init__(self, timeout: int | None = None):
        """
        Initialize AgentHTTPClient.

        Args:
            timeout: Timeout in seconds for requests (defaults to config.agent_timeout)
        """
        self.timeout = timeout or config.agent_timeout

    def send_task(self, endpoint: str, task: Task, skill: str | None = None) -> Task:
        """
        Send a task to a remote agent synchronously.

        This is a synchronous wrapper around the async send_task function.

        Args:
            endpoint: Full URL endpoint (e.g., http://agent:8000/message/send)
            task: A2A Task to send
            skill: Skill name (defaults to extracting from task)

        Returns:
            Task response from the agent

        Raises:
            RuntimeError: If the agent returns an error or invalid response
        """
        import asyncio

        # Extract skill from endpoint or use provided skill
        if skill is None:
            skill = "default"

        # Run the async function synchronously
        return asyncio.run(send_task_async(task, endpoint, skill, self.timeout))


async def send_task_async(
    task: Task, endpoint: str, skill: str, timeout: int | None = None
) -> Task:
    """
    Sends a Task to a remote agent using A2A-compliant JSON-RPC via /message/send.
    Accepts both raw Task response and JSON-RPC wrapped result.message.

    This is the async implementation. Use AgentHTTPClient.send_task() for synchronous calls.

    Args:
        task: A2A Task to send
        endpoint: Full URL endpoint (e.g., http://agent:8000/message/send)
        skill: Skill name to invoke
        timeout: Timeout in seconds (defaults to config.agent_timeout)

    Returns:
        Task response from the agent

    Raises:
        RuntimeError: If the agent returns an error or invalid response
    """
    # Use configured timeout if not specified
    if timeout is None:
        timeout = config.agent_timeout

    try:
        request_id = task.id or str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "message/send",
            "params": {"skill": skill, "message": task.model_dump(mode="json")},
        }

        logger.info(
            "Sending A2A task",
            extra={
                "skill": skill,
                "endpoint": endpoint,
                "task_id": request_id,
                "method": "message/send",
            },
        )

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            ) as response,
        ):
            response_text = await response.text()
            logger.info(
                "Received response from agent",
                extra={
                    "skill": skill,
                    "status_code": response.status,
                    "response_length": len(response_text),
                },
            )

            if response.status != 200:
                raise RuntimeError(f"Agent returned {response.status}: {response_text}")

            # Accept both agent raw Task and JSON-RPC 'result.message'
            try:
                response_data = await response.json()
            except Exception:
                response_data = json.loads(response_text)

            if isinstance(response_data, dict) and "result" in response_data:
                # Official A2A JSON-RPC
                task_json = response_data["result"].get("message")
            else:
                # Raw Task (legacy, current FastAPI style)
                task_json = response_data

            if not task_json:
                raise RuntimeError(f"Missing Task in agent reply: {response_data}")

            response_task = Task.model_validate(task_json)
            return response_task

    except Exception as e:
        logger.error(
            "Failed to send task to agent",
            extra={"skill": skill, "endpoint": endpoint, "error": str(e)},
            exc_info=True,
        )
        raise
