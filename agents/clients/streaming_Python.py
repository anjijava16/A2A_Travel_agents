import logging
from uuid import uuid4
import httpx
import json

async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    base_url = 'http://localhost:8889'
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Fetch the agent card
        logger.info("🔍 Fetching agent card...")
        card_response = await client.get(f'{base_url}/.well-known/agent.json')
        card_response.raise_for_status()
        agent_card = card_response.json()
        logger.info(f"✅ Agent: {agent_card.get('name')}")
        
        endpoint_url = agent_card.get('url', base_url).rstrip('/')
        
        # 2. Send regular message
        logger.info(f"\n{'='*60}")
        logger.info("📤 Sending regular (non-streaming) message...")
        logger.info(f"{'='*60}")
        
        regular_request = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": str(uuid4()),
            "params": {
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "kind": "text",
                            "text": "I have Blue Cross insurance. Find me a gastroenterologist in Boston, MA."
                        }
                    ],
                    "messageId": uuid4().hex
                }
            }
        }
        
        response = await client.post(
            endpoint_url,
            json=regular_request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        result = response.json()
        
        agent_message = result.get("result", {}).get("artifacts", [{}])[0].get("parts", [{}])[0].get("text", "")
        logger.info(f"\n🤖 Agent response:\n{agent_message}\n")
        
        # 3. Send streaming message (corrected approach)
        logger.info(f"\n{'='*60}")
        logger.info("📤 Sending STREAMING message...")
        logger.info(f"{'='*60}")
        
        streaming_request = {
            "jsonrpc": "2.0",
            "method": "message/send",  # Use same method, not sendStreaming!
            "id": str(uuid4()),
            "params": {
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "kind": "text",
                            "text": "Find psychiatrists in Boston, MA."
                        }
                    ],
                    "messageId": uuid4().hex
                }
            }
        }
        
        # Key difference: Stream the response with proper headers
        try:
            logger.info("🌊 Opening streaming connection...")
            async with client.stream(
                'POST',
                endpoint_url,
                json=streaming_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream"  # Important for SSE
                }
            ) as stream_response:
                stream_response.raise_for_status()
                
                logger.info("✅ Receiving streaming chunks:\n")
                print(f"{'='*60}")
                
                async for line in stream_response.aiter_lines():
                    if line.strip():
                        # Handle Server-Sent Events format
                        if line.startswith('data: '):
                            data = line[6:]  # Remove 'data: ' prefix
                            try:
                                chunk = json.loads(data)
                                print(json.dumps(chunk, indent=2))
                            except json.JSONDecodeError:
                                print(data)
                        else:
                            # Plain JSON-RPC streaming
                            try:
                                chunk = json.loads(line)
                                print(json.dumps(chunk, indent=2))
                            except json.JSONDecodeError:
                                print(line)
                
                print(f"{'='*60}\n")
                logger.info("✅ Streaming completed")
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error: {e.response.status_code}")
            logger.error(f"Response: {e.response.text}")
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}")


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())