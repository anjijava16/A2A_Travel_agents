import logging
from uuid import uuid4
import httpx
from httpx_sse import aconnect_sse
import json
from datetime import datetime

async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    base_url = 'http://localhost:8889'
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Fetch agent card
        logger.info("🔍 Fetching agent card...")
        card_response = await client.get(f'{base_url}/.well-known/agent.json')
        card_response.raise_for_status()
        agent_card = card_response.json()
        logger.info(f"✅ Agent: {agent_card.get('name')}\n")
        
        endpoint_url = agent_card.get('url', base_url).rstrip('/')
        
        # 2. Regular message (non-streaming)
        logger.info(f"{'='*60}")
        logger.info("📤 REGULAR MESSAGE")
        logger.info(f"{'='*60}\n")
        
        regular_request = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": str(uuid4()),
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Find a pediatrician in Boston, MA"}],
                    "messageId": uuid4().hex
                }
            }
        }
        
        response = await client.post(endpoint_url, json=regular_request)
        response.raise_for_status()
        result = response.json()
        logger.info("✅ Response received\n")
        
        # 3. TRUE STREAMING MESSAGE (using correct method and SSE)
        logger.info(f"{'='*60}")
        logger.info("📤 STREAMING MESSAGE (TRUE SSE)")
        logger.info(f"{'='*60}\n")
        
        streaming_start = datetime.now()
        chunk_count = 0
        
        # KEY: Use 'message/stream' not 'message/send' or 'message/sendStreaming'
        streaming_request = {
            "jsonrpc": "2.0",
            "method": "message/stream",  # ← This is the correct method!
            "id": str(uuid4()),
            "params": {
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "kind": "text",
                            "text": "Find psychiatrists in Boston, MA with Blue Cross insurance."
                        }
                    ],
                    "messageId": uuid4().hex
                }
            }
        }
        
        try:
            logger.info("🌊 Opening SSE connection...")
            
            # Use aconnect_sse from httpx_sse library (same as SDK)
            async with aconnect_sse(
                client,
                'POST',
                endpoint_url,
                json=streaming_request
            ) as event_source:
                logger.info("✅ SSE connection established\n")
                
                # Iterate over SSE events
                async for sse in event_source.aiter_sse():
                    chunk_count += 1
                    elapsed = (datetime.now() - streaming_start).total_seconds()
                    
                    # Parse the SSE data as JSON
                    try:
                        chunk = json.loads(sse.data)
                        
                        result = chunk.get('result', {})
                        kind = result.get('kind', 'unknown')
                        is_final = result.get('final', False)
                        
                        logger.info(f"🌊 Chunk #{chunk_count} @ {elapsed:.2f}s")
                        logger.info(f"   Kind: {kind}")
                        logger.info(f"   Final: {is_final}")
                        
                        # Extract text if present
                        if 'artifact' in result:
                            parts = result.get('artifact', {}).get('parts', [])
                            if parts and 'text' in parts[0]:
                                preview = parts[0]['text'][:80]
                                logger.info(f"   Text: {preview}...")
                        
                        if 'artifacts' in result:
                            artifacts = result.get('artifacts', [])
                            if artifacts:
                                parts = artifacts[0].get('parts', [])
                                if parts and 'text' in parts[0]:
                                    preview = parts[0]['text'][:80]
                                    logger.info(f"   Text: {preview}...")
                        
                        print(f"\n--- Chunk #{chunk_count} ---")
                        print(json.dumps(chunk, indent=2))
                        print()
                        
                        logger.info("")
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON: {e}")
                
                total_time = (datetime.now() - streaming_start).total_seconds()
                
                logger.info(f"\n{'='*60}")
                logger.info(f"✅ Streaming completed")
                logger.info(f"⏱️  Total duration: {total_time:.2f}s")
                logger.info(f"📦 Total chunks: {chunk_count}")
                logger.info(f"{'='*60}\n")
                
                if chunk_count == 1:
                    logger.warning("⚠️  Only 1 chunk received")
                else:
                    logger.info(f"✅ TRUE STREAMING: {chunk_count} incremental chunks!")
                
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}", exc_info=True)
        
        # 4. Multi-turn conversation
        logger.info(f"\n{'='*60}")
        logger.info("📤 MULTI-TURN CONVERSATION")
        logger.info(f"{'='*60}\n")
        
        first_msg = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": str(uuid4()),
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "I need a gastroenterologist"}],
                    "messageId": uuid4().hex
                }
            }
        }
        
        first_resp = await client.post(endpoint_url, json=first_msg)
        first_resp.raise_for_status()
        first_result = first_resp.json()
        
        task_id = first_result.get("result", {}).get("id")
        context_id = first_result.get("result", {}).get("contextId")
        
        logger.info(f"✅ First message - Task ID: {task_id}\n")
        
        # Follow-up with context
        followup_msg = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": str(uuid4()),
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Boston, MA with Blue Cross"}],
                    "messageId": uuid4().hex,
                    "taskId": task_id,
                    "contextId": context_id
                }
            }
        }
        
        followup_resp = await client.post(endpoint_url, json=followup_msg)
        followup_resp.raise_for_status()
        logger.info("✅ Follow-up message sent\n")


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())