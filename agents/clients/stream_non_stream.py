"""
Simple A2A Client - No SDK Required
Demonstrates: Agent card fetching, regular messages, true streaming, and multi-turn conversations
"""

import logging
from uuid import uuid4
import httpx
from httpx_sse import aconnect_sse
import json
from datetime import datetime
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleA2AClient:
    """Simple A2A client without using the full SDK"""
    
    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=timeout)
        self.agent_card = None
        self.endpoint_url = None
    
    async def __aenter__(self):
        await self.fetch_agent_card()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def fetch_agent_card(self) -> dict:
        """Fetch the agent card from /.well-known/agent.json"""
        url = f"{self.base_url}/.well-known/agent.json"
        logger.info(f"Fetching agent card from {url}")
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        self.agent_card = response.json()
        self.endpoint_url = self.agent_card.get('url', self.base_url).rstrip('/')
        
        logger.info(f"✅ Agent: {self.agent_card.get('name')}")
        logger.info(f"   Endpoint: {self.endpoint_url}")
        logger.info(f"   Streaming: {self.agent_card.get('capabilities', {}).get('streaming', False)}")
        
        return self.agent_card
    
    async def send_message(
        self,
        text: str,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None
    ) -> dict:
        """Send a non-streaming message"""
        message_id = uuid4().hex
        request_id = str(uuid4())
        
        request = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": request_id,
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": text}],
                    "messageId": message_id
                }
            }
        }
        
        # Add task/context IDs for multi-turn conversations
        if task_id:
            request["params"]["message"]["taskId"] = task_id
        if context_id:
            request["params"]["message"]["contextId"] = context_id
        
        logger.info(f"📤 Sending message: {text[:50]}...")
        
        response = await self.client.post(
            self.endpoint_url,
            json=request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        result = response.json()
        logger.info("✅ Response received")
        
        return result
    
    async def send_message_streaming(self, text: str):
        """Send a streaming message and yield chunks as they arrive"""
        message_id = uuid4().hex
        request_id = str(uuid4())
        
        request = {
            "jsonrpc": "2.0",
            "method": "message/stream",  # Key: use 'message/stream' for streaming
            "id": request_id,
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": text}],
                    "messageId": message_id
                }
            }
        }
        
        logger.info(f"📤 Sending streaming message: {text[:50]}...")
        start_time = datetime.now()
        chunk_count = 0
        
        async with aconnect_sse(
            self.client,
            'POST',
            self.endpoint_url,
            json=request
        ) as event_source:
            async for sse in event_source.aiter_sse():
                chunk_count += 1
                elapsed = (datetime.now() - start_time).total_seconds()
                
                chunk = json.loads(sse.data)
                result = chunk.get('result', {})
                
                logger.info(
                    f"🌊 Chunk #{chunk_count} @ {elapsed:.2f}s - "
                    f"Kind: {result.get('kind', 'unknown')}, "
                    f"Final: {result.get('final', False)}"
                )
                
                yield chunk
        
        total_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ Streaming completed: {chunk_count} chunks in {total_time:.2f}s")


async def demo():
    """Demonstration of all A2A client features"""
    
    async with SimpleA2AClient('http://localhost:8889') as client:
        
        print("\n" + "="*60)
        print("DEMO 1: Regular Non-Streaming Message")
        print("="*60 + "\n")
        
        result = await client.send_message(
            "Find a pediatrician in Boston, MA"
        )
        
        # Extract response text
        response_text = result.get("result", {}).get("artifacts", [{}])[0].get("parts", [{}])[0].get("text", "")
        print(f"\n🤖 Agent Response:\n{response_text[:200]}...\n")
        
        
        print("\n" + "="*60)
        print("DEMO 2: Streaming Message with Live Updates")
        print("="*60 + "\n")
        
        async for chunk in client.send_message_streaming(
            "Find psychiatrists in Boston, MA with Blue Cross insurance"
        ):
            result = chunk.get('result', {})
            kind = result.get('kind')
            
            # Show status updates
            if kind == 'status-update':
                status = result.get('status', {})
                state = status.get('state')
                message = status.get('message', {})
                text = message.get('parts', [{}])[0].get('text', '') if message else ''
                
                if text:
                    print(f"💬 Agent: {text[:100]}...")
            
            # Show final artifact
            elif kind == 'artifact-update':
                artifact = result.get('artifact', {})
                text = artifact.get('parts', [{}])[0].get('text', '')
                print(f"\n📄 Final Response:\n{text}\n")
        
        
        print("\n" + "="*60)
        print("DEMO 3: Multi-Turn Conversation")
        print("="*60 + "\n")
        
        # First message
        first_result = await client.send_message(
            "I need a gastroenterologist"
        )
        
        task_id = first_result.get("result", {}).get("id")
        context_id = first_result.get("result", {}).get("contextId")
        
        print(f"📋 Conversation started - Task ID: {task_id}\n")
        
        # Follow-up message with context
        followup_result = await client.send_message(
            "I'm in Boston, MA and have Blue Cross insurance",
            task_id=task_id,
            context_id=context_id
        )
        
        response_text = followup_result.get("result", {}).get("artifacts", [{}])[0].get("parts", [{}])[0].get("text", "")
        print(f"\n🤖 Agent Response:\n{response_text[:200]}...\n")


if __name__ == '__main__':
    import asyncio
    asyncio.run(demo())