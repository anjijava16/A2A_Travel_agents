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
        try:
            card_response = await client.get(f'{base_url}/.well-known/agent.json')
            card_response.raise_for_status()
            agent_card = card_response.json()
            logger.info(f"✅ Agent card loaded: {agent_card.get('name')}")
        except Exception as e:
            logger.error(f"Failed to fetch agent card: {e}")
            raise
        
        # 2. Determine endpoint - use base URL from agent card
        endpoint_url = agent_card.get('url', base_url).rstrip('/')
        logger.info(f"Using endpoint: {endpoint_url}")
        
        # 3. Prepare message payload (matching SDK format exactly)
        message_id = uuid4().hex
        request_id = str(uuid4())
        
        # This is the JSON-RPC 2.0 request format that A2A uses
        request_payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": request_id,
            "params": {
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "kind": "text",
                            "text": "I have Blue Cross insurance policy ID BC123. I have sharp lower abdominal pain. Can you find me a gastroenterologist?"
                        }
                    ],
                    "messageId": message_id
                }
            }
        }
        
        logger.info(f"\n📤 Sending request to: {endpoint_url}")
        logger.info(f"Request payload:\n{json.dumps(request_payload, indent=2)}")
        
        # 4. Send the message
        try:
            response = await client.post(
                endpoint_url,
                json=request_payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"\n✅ Response received!")
            print(f"\n{'='*60}")
            print("RESPONSE:")
            print(json.dumps(result, indent=2))
            print(f"{'='*60}\n")
            
            # Extract useful info from response
            if "result" in result:
                task_id = result.get("result", {}).get("id")
                context_id = result.get("result", {}).get("contextId")
                logger.info(f"Task ID: {task_id}")
                logger.info(f"Context ID: {context_id}")
            
        except httpx.ReadTimeout:
            logger.error("❌ Request timed out")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error {e.response.status_code}")
            logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            raise
        
        # 5. Send streaming message (optional)
        logger.info(f"\n{'='*60}")
        logger.info("Testing streaming request...")
        logger.info(f"{'='*60}")
        
        streaming_request_id = str(uuid4())
        streaming_message_id = uuid4().hex
        
        streaming_payload = {
            "jsonrpc": "2.0",
            "method": "message/sendStreaming",
            "id": streaming_request_id,
            "params": {
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "kind": "text",
                            "text": "Are there any Psychiatrists near me in Boston, MA?"
                        }
                    ],
                    "messageId": streaming_message_id
                }
            }
        }
        
        try:
            logger.info("📤 Sending streaming request...")
            async with client.stream(
                'POST',
                endpoint_url,
                json=streaming_payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            ) as stream_response:
                stream_response.raise_for_status()
                
                logger.info("✅ Receiving streaming response:")
                print(f"\n{'='*60}")
                print("STREAMING RESPONSE:")
                print(f"{'='*60}")
                
                async for line in stream_response.aiter_lines():
                    if line.strip():
                        try:
                            chunk = json.loads(line)
                            print(json.dumps(chunk, indent=2))
                        except json.JSONDecodeError:
                            print(line)
                
                print(f"{'='*60}\n")
                
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}")


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())