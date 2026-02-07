#!/usr/bin/env python3
"""
MCP Gateway for A2A Workshop

Provides MCP (Model Context Protocol) interface for A2A agents.
Users connect via Claude Code/Desktop and interact with agents through MCP tools.

ARCHITECTURE NOTES:
------------------
This service uses a hybrid architecture combining MCP SDK with FastAPI:

1. MCP SDK (mcp.server.Server):
   - Provides protocol correctness and type safety
   - Decorators (@mcp_server.list_tools, @mcp_server.call_tool) define tool schemas
   - Ensures compliance with MCP specification
   - Note: MCP SDK natively supports stdio transport, not HTTP

2. FastAPI (HTTP Transport Layer):
   - Provides HTTP endpoint (/mcp) for remote clients
   - Enables ALB integration for production deployment
   - Implements Server-Sent Events (SSE) for long-running operations
   - Manually routes requests to MCP SDK decorated functions

3. SSE Streaming (Critical for Production):
   - Orchestrator calls can take 80+ seconds (decomposition + agent calls + synthesis)
   - ALB may timeout idle connections without periodic heartbeats
   - SSE sends heartbeat events every 20 seconds to keep connection alive
   - Only used if client sends "Accept: text/event-stream" header
   - Falls back to standard JSON-RPC if streaming not requested

Why This Design:
- MCP SDK ensures protocol compliance but doesn't provide HTTP transport
- FastAPI provides HTTP + SSE capabilities needed for ALB deployment
- Decorators act as type-safe protocol handlers called by FastAPI endpoint
- Result: Best of both worlds - protocol correctness + production features
"""

import asyncio
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any
import uuid

from a2a.types import Message, Role, Task, TaskState, TaskStatus, TextPart
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from mcp.server import Server
from mcp.types import TextContent, Tool

# Add project root to path for imports
project_root = Path(__file__).parent.parent  # gateway/main.py -> project_root
sys.path.insert(0, str(project_root))

from lib.agents.discover_agent import discover_agent

load_dotenv()

# Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
CLOUDMAP_NAMESPACE = os.getenv("CLOUDMAP_NAMESPACE", "a2a-agents.local")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8000"))

# FastAPI app for health checks and agent card
app = FastAPI(title="MCP Gateway", version="1.0.0")

# MCP Server
mcp_server = Server("a2a-workshop-gateway")

# HTTP client for agent communication (extended timeout for long operations)
http_client = httpx.AsyncClient(timeout=180.0)


#############################################################################
# MCP Tool Definitions
#############################################################################


async def get_dynamic_tool_description() -> str:
    """
    Build dynamic tool description by querying orchestrator for available agents.

    Falls back to generic description if discovery fails.

    Returns:
        Dynamic tool description string
    """
    try:
        # Discover orchestrator via CloudMap
        logging.info("Discovering orchestrator for dynamic tool description...")
        orchestrator_info = await asyncio.to_thread(discover_agent, "orchestrator")
        orchestrator_url = orchestrator_info["base_url"]

        # Fetch available agents from orchestrator
        logging.info(f"Fetching agents from {orchestrator_url}/agents/available")
        response = await http_client.get(f"{orchestrator_url}/agents/available")
        response.raise_for_status()
        agents_data = response.json()
        available_agents = agents_data.get("agents", [])

        # Build rich description
        if available_agents:
            # List agent names
            agent_names = ", ".join([a["name"] for a in available_agents])

            # Build capability summary (show first 3 agents' top capabilities)
            capability_examples = []
            for agent in available_agents[:3]:  # Limit to 3 for brevity
                caps = [
                    c["name"] for c in agent.get("capabilities", [])[:2]
                ]  # Top 2 caps
                if caps:
                    capability_examples.append(f"{agent['name']} ({', '.join(caps)})")

            cap_summary = "; ".join(capability_examples) if capability_examples else ""

            # Build description
            description = (
                f"Ask the universal orchestrator to coordinate specialist agents and provide comprehensive responses. "
                f"Available agents: {agent_names}. "
            )

            if cap_summary:
                description += f"Example capabilities: {cap_summary}. "

            description += (
                "The orchestrator will intelligently route your question to the most relevant agents, "
                "call them in parallel, and synthesize their responses into a cohesive answer."
            )
        else:
            description = "Ask the universal orchestrator to coordinate available specialist agents and provide comprehensive responses"

        logging.info(f"Built tool description with {len(available_agents)} agents")
        return description

    except Exception as e:
        logging.warning(f"Could not build dynamic description: {e}")
        # Fallback to generic description (graceful degradation)
        return "Ask the universal orchestrator to coordinate available specialist agents and provide comprehensive responses"


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """
    Register MCP tools with dynamic descriptions.

    Tool list is dynamically generated based on available agents
    discovered through the orchestrator.
    """
    # Get dynamic description
    description = await get_dynamic_tool_description()

    return [
        Tool(
            name="ask_workshop",
            description=description,
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Pass the user's EXACT original message without modification or enhancement. Do not rephrase, expand, or interpret - forward exactly as written.",
                    }
                },
                "required": ["question"],
            },
        )
    ]


#############################################################################
# Helper Functions
#############################################################################


async def send_a2a_message(agent_url: str, user_message: str) -> dict[str, Any]:
    """
    Send A2A protocol message to an agent.

    Args:
        agent_url: Base URL of the agent
        user_message: User's message/query

    Returns:
        Agent's response as dictionary
    """
    # Generate IDs
    task_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    context_id = str(uuid.uuid4())

    # Construct Message object
    message = Message(
        role=Role.user,
        parts=[TextPart(kind="text", text=user_message, metadata={})],
        message_id=message_id,
        kind="message",
        context_id=context_id,
        task_id=task_id,
    )

    # Construct Task object
    task = Task(
        id=task_id,
        context_id=context_id,
        status=TaskStatus(
            state=TaskState.submitted,
            timestamp=datetime.now(UTC).isoformat() + "Z",
        ),
        history=[message],
        input={"query": user_message},
        artifacts=[],
        metadata={},
        kind="task",
    )

    # Construct A2A protocol message (JSON-RPC format)
    a2a_message = {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "message/send",
        "params": {"message": task.model_dump(mode="json")},
    }

    try:
        endpoint = f"{agent_url}/message/send"
        logging.info(f"Sending A2A message to {endpoint}")
        response = await http_client.post(endpoint, json=a2a_message)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {
            "status": "error",
            "error": f"Failed to communicate with agent: {e!s}",
        }


def format_agent_response(response: dict[str, Any]) -> str:
    """
    Format agent response for MCP client display.

    CRITICAL: Extract ONLY the synthesized text from artifacts to avoid
    token overflow. The full response can contain 864k+ tokens of raw agent data.

    Args:
        response: Agent's response dictionary (A2A Task structure)

    Returns:
        Synthesized text string (human-readable narrative only)
    """
    if response.get("status") == "error":
        return f"❌ Error: {response.get('error', 'Unknown error')}"

    # Extract synthesized text from Task artifacts
    # Task structure: response.artifacts[0].parts[0].text = synthesized narrative
    try:
        artifacts = response.get("artifacts", [])
        if artifacts and len(artifacts) > 0:
            parts = artifacts[0].get("parts", [])
            for part in parts:
                # Find the TextPart with synthesized narrative
                if part.get("kind") == "text" and "text" in part:
                    synthesized_text = part["text"]
                    logging.info(
                        f"✓ Extracted synthesized text ({len(synthesized_text)} chars)"
                    )
                    return synthesized_text

        # Fallback: if no artifacts found, return basic message
        logging.warning("No synthesized text found in artifacts, using fallback")
        if "result" in response:
            return json.dumps(response["result"], indent=2)
        elif "message" in response:
            return response["message"]
        else:
            return json.dumps(response, indent=2)

    except Exception as e:
        logging.error(f"Failed to extract synthesized text: {e}", exc_info=True)
        # Emergency fallback
        return f"❌ Error extracting response: {e!s}"


def format_sse_event(
    event_type: str, data: dict[str, Any], event_id: str | None = None
) -> str:
    """
    Format data as Server-Sent Event (SSE).

    Args:
        event_type: Type of event (e.g., "message", "progress", "error")
        data: Data payload to send
        event_id: Optional event ID for resumability

    Returns:
        Formatted SSE string
    """
    lines = []
    if event_id:
        lines.append(f"id: {event_id}\n")
    lines.append(f"event: {event_type}\n")
    lines.append(f"data: {json.dumps(data)}\n\n")
    return "".join(lines)


async def stream_orchestrator_response(question: str, request_id: str, agent_url: str):
    """
    Stream orchestrator response as SSE events.
    Sends periodic heartbeats to keep connection alive and prevent ALB timeout.

    CRITICAL: This function prevents ALB from terminating idle connections during
    long-running orchestrator operations (which can take 80+ seconds). Without
    periodic heartbeats, the ALB may close the connection before the orchestrator
    finishes processing, causing the request to fail.

    Heartbeat Strategy:
    - Send heartbeat event every 20 seconds while waiting for orchestrator
    - Include elapsed time to show progress to user
    - ALB interprets heartbeats as activity, maintaining connection

    Args:
        question: User's question
        request_id: MCP request ID
        agent_url: Orchestrator agent URL

    Yields:
        SSE-formatted events
    """
    import time

    try:
        # Send initial progress event
        yield format_sse_event(
            "progress",
            {
                "status": "starting",
                "message": "Initializing orchestrator...",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            event_id=f"{request_id}-0",
        )

        # Start orchestrator task
        start_time = time.time()
        logging.info(f"Starting orchestrator call for request {request_id}")

        # Send decomposition progress
        yield format_sse_event(
            "progress",
            {
                "status": "decomposing",
                "message": "Decomposing request into subtasks...",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            event_id=f"{request_id}-1",
        )

        # Call orchestrator (this may take 80+ seconds)
        # We'll send periodic heartbeats while waiting
        task = asyncio.create_task(send_a2a_message(agent_url, question))

        # Send heartbeat every 20 seconds while waiting
        event_counter = 2
        while not task.done():
            await asyncio.sleep(20)
            if not task.done():
                elapsed = int(time.time() - start_time)
                yield format_sse_event(
                    "heartbeat",
                    {
                        "status": "processing",
                        "message": f"Orchestrating agents... ({elapsed}s elapsed)",
                        "elapsed_seconds": elapsed,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    event_id=f"{request_id}-{event_counter}",
                )
                event_counter += 1

        # Get result
        response = await task
        elapsed_ms = int((time.time() - start_time) * 1000)

        # Check for errors
        if response.get("status") == "error":
            yield format_sse_event(
                "error",
                {
                    "error": response.get("error", "Unknown error"),
                    "elapsed_ms": elapsed_ms,
                },
                event_id=f"{request_id}-error",
            )
            return

        # Send final result as MCP response format
        result_text = format_agent_response(response)

        # Format as MCP tools/call response
        mcp_response = {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": result_text}]},
            "id": request_id,
        }

        yield format_sse_event("message", mcp_response, event_id=f"{request_id}-final")
        logging.info(
            f"Orchestrator completed in {elapsed_ms}ms for request {request_id}"
        )

    except Exception as e:
        logging.error(f"Streaming error: {e}", exc_info=True)
        yield format_sse_event(
            "error",
            {"code": -32603, "message": f"Streaming failed: {e!s}"},
            event_id=f"{request_id}-error",
        )


#############################################################################
# MCP Tool Handlers
#############################################################################


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle MCP tool calls and route to orchestrator"""
    import time

    try:
        logging.info(f"Tool called: {name} with arguments: {arguments}")

        if name == "ask_workshop":
            question = arguments.get("question", "")
            logging.info(f"Routing question to orchestrator: {question[:100]}...")

            # Always route to orchestrator - it will handle decomposition and coordination
            start_time = time.time()
            agent = await asyncio.to_thread(discover_agent, "orchestrator")
            discovery_elapsed = int((time.time() - start_time) * 1000)
            logging.info(
                f"Found orchestrator at: {agent['base_url']} (discovery took {discovery_elapsed}ms)"
            )

            orchestrator_start = time.time()
            response = await send_a2a_message(agent["base_url"], question)
            orchestrator_elapsed = int((time.time() - orchestrator_start) * 1000)
            total_elapsed = int((time.time() - start_time) * 1000)

            logging.info(
                f"Orchestrator response received in {orchestrator_elapsed}ms (total: {total_elapsed}ms)"
            )
            result = format_agent_response(response)

        else:
            result = f"❌ Unknown tool: {name}"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        error_msg = f"❌ Tool execution failed: {e!s}"
        logging.error(f"Tool execution error: {e}", exc_info=True)
        return [TextContent(type="text", text=error_msg)]


#############################################################################
# FastAPI Endpoints (Health & Agent Card)
#############################################################################


@app.get("/health")
async def health():
    """Health check endpoint for ALB"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "mcp-gateway",
    }


@app.get("/.well-known/agent.json")
async def agent_card():
    """
    Agent card for MCP Gateway.

    Not a typical A2A agent - it's a protocol gateway.
    Routes all requests through the universal orchestrator.
    """
    return {
        "name": "MCP Gateway",
        "description": "Gateway service providing MCP protocol access to A2A workshop agents",
        "version": "1.0.0",
        "role": "gateway",  # Distinguish from agents
        "capabilities": {
            "protocol": "MCP",
            "routing": "Routes all requests through universal orchestrator",
        },
        "endpoints": {
            "health": "/health",
            "mcp": "/mcp",
            "agent_card": "/.well-known/agent.json",
        },
    }


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    MCP protocol endpoint (HTTP transport).
    Handles MCP requests from clients like Claude Code.
    """
    try:
        body = await request.json()
        method = body.get("method")
        request_id = body.get("id")

        logging.info(f"MCP request: method={method}, id={request_id}")

        # Handle initialize request
        if method == "initialize":
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "a2a-workshop-gateway",
                            "version": "1.0.0",
                        },
                    },
                    "id": request_id,
                }
            )

        # Handle tools/list request
        elif method == "tools/list":
            tools = await list_tools()
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "result": {
                        "tools": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema,
                            }
                            for tool in tools
                        ]
                    },
                    "id": request_id,
                }
            )

        # Handle tools/call request
        elif method == "tools/call":
            params = body.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            # Check if client accepts streaming and if this is a long-running operation
            accept_header = request.headers.get("accept", "")
            supports_streaming = "text/event-stream" in accept_header

            # Log transport decision for monitoring
            logging.info(
                f"[{request_id}] Accept header: {accept_header if accept_header else '(none)'}"
            )
            logging.info(
                f"[{request_id}] Response type: {'SSE streaming' if (tool_name == 'ask_workshop' and supports_streaming) else 'standard JSON-RPC'}"
            )

            # Use streaming for ask_workshop (long-running orchestrator operations)
            if tool_name == "ask_workshop" and supports_streaming:
                question = arguments.get("question", "")
                logging.info(
                    f"Using SSE streaming for ask_workshop: {question[:100]}..."
                )

                # Discover orchestrator
                agent = await asyncio.to_thread(discover_agent, "orchestrator")
                agent_url = agent["base_url"]

                # Return streaming response
                return StreamingResponse(
                    stream_orchestrator_response(question, request_id, agent_url),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",  # Disable nginx buffering
                    },
                )

            # For non-streaming or other tools, use standard JSON response
            result = await call_tool(tool_name, arguments)

            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "result": {
                        "content": [
                            {"type": content.type, "text": content.text}
                            for content in result
                        ]
                    },
                    "id": request_id,
                }
            )

        # Handle ping
        elif method == "ping":
            return JSONResponse({"jsonrpc": "2.0", "result": {}, "id": request_id})

        # Handle notifications (no response needed)
        elif method and method.startswith("notifications/"):
            # Notifications don't require a response
            return JSONResponse({"jsonrpc": "2.0"}, status_code=200)

        # Unknown method
        else:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": request_id,
                },
                status_code=404,
            )

    except Exception as e:
        logging.error(f"MCP endpoint error: {e}", exc_info=True)

        # Safely extract request_id even if body parsing failed
        request_id = None
        try:
            if "body" in locals() and body:
                request_id = body.get("id")
        except Exception:
            pass

        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": request_id,
            },
            status_code=500,
        )


#############################################################################
# Main Application
#############################################################################


class HealthCheckFilter(logging.Filter):
    """Filter out health check endpoint logs"""

    def filter(self, record: logging.LogRecord) -> bool:
        # Suppress logs for /health endpoint
        return "/health" not in record.getMessage()


if __name__ == "__main__":
    import uvicorn

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting MCP Gateway on port {GATEWAY_PORT}")
    logger.info(f"Cloud Map namespace: {CLOUDMAP_NAMESPACE}")
    logger.info(f"AWS Region: {AWS_REGION}")

    # Add health check filter to uvicorn access logger
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(HealthCheckFilter())

    # Run FastAPI with HTTP transport
    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT, log_level="info")
