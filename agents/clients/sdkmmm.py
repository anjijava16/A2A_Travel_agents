import logging
from uuid import uuid4
import httpx
import json
from datetime import datetime

async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    base_url = 'http://localhost:8889'
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Fetch agent card
        logger.info("🔍 Fetching agent card...")
        card_response = await client.get(f'{base_url}/.well-known/agent.json')
        card_response.raise_for_status()
        agent_card = card_response.json()
        
        endpoint_url = agent_card.get('url', base_url).rstrip('/')
        
        logger.info(f"\n{'='*60}")
        logger.info("📤 STREAMING MESSAGE (using SSE)")
        logger.info(f"{'='*60}\n")
        
        streaming_start = datetime.now()
        chunk_count = 0
        
        # The key difference: SDK likely uses a DIFFERENT METHOD NAME
        streaming_request = {
            "jsonrpc": "2.0",
            "method": "message/sendStreaming",  # Note: sendStreaming, not send!
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
            logger.info("🌊 Opening SSE streaming connection...")
            
            # Critical: Accept header for SSE
            async with client.stream(
                'POST',
                endpoint_url,
                json=streaming_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",  # SSE header
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
            ) as stream_response:
                stream_response.raise_for_status()
                
                logger.info("✅ SSE connection established\n")
                
                # Parse Server-Sent Events format
                async for line in stream_response.aiter_lines():
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    # SSE format: "data: {json}"
                    if line.startswith('data: '):
                        data_str = line[6:]  # Remove "data: " prefix
                        
                        try:
                            chunk = json.loads(data_str)
                            chunk_count += 1
                            elapsed = (datetime.now() - streaming_start).total_seconds()
                            
                            result = chunk.get('result', {})
                            kind = result.get('kind', 'unknown')
                            is_final = result.get('final', False)
                            
                            logger.info(f"🌊 Chunk #{chunk_count} @ {elapsed:.2f}s")
                            logger.info(f"   Kind: {kind}")
                            logger.info(f"   Final: {is_final}")
                            
                            # Show artifact if present
                            if 'artifact' in result:
                                parts = result['artifact'].get('parts', [])
                                if parts and 'text' in parts[0]:
                                    preview = parts[0]['text'][:80]
                                    logger.info(f"   Text: {preview}...")
                            
                            print(f"\n--- Chunk #{chunk_count} ---")
                            print(json.dumps(chunk, indent=2))
                            print()
                            
                            logger.info("")
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse JSON: {e}")
                            logger.warning(f"Data: {data_str[:100]}")
                    
                    elif line.startswith('event: '):
                        # SSE event type (usually ignored)
                        pass
                    
                    elif line.startswith('id: '):
                        # SSE event ID (usually ignored)
                        pass
                
                total_time = (datetime.now() - streaming_start).total_seconds()
                
                logger.info(f"\n{'='*60}")
                logger.info(f"✅ Streaming completed")
                logger.info(f"⏱️  Total duration: {total_time:.2f}s")
                logger.info(f"📦 Total chunks: {chunk_count}")
                logger.info(f"{'='*60}\n")
                
                if chunk_count == 1:
                    logger.warning("⚠️  Only 1 chunk - server not truly streaming")
                else:
                    logger.info(f"✅ TRUE STREAMING: {chunk_count} incremental chunks!")
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP {e.response.status_code}")
            logger.error(f"Response: {e.response.text}")
        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())