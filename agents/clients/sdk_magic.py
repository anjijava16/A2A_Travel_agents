# Quick inspection script
from a2a.client import A2AClient
import inspect

print("SDK send_message_streaming method:")
print(inspect.getsource(A2AClient.send_message_streaming))


import logging
from uuid import uuid4
import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import MessageSendParams, SendStreamingMessageRequest
import inspect

async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    base_url = 'http://localhost:8889'
    
    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
        agent_card = await resolver.get_agent_card()
        
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)
        
        # Inspect the transport
        logger.info("🔍 Inspecting transport layer...")
        logger.info(f"Transport type: {type(client._transport)}")
        logger.info(f"Transport class: {client._transport.__class__.__name__}\n")
        
        # Get the transport's send_message_streaming method
        logger.info("📋 Transport send_message_streaming method:")
        try:
            source = inspect.getsource(client._transport.send_message_streaming)
            print(source)
        except Exception as e:
            logger.error(f"Could not get source: {e}")
        
        # Check what method name it uses
        logger.info("\n🔍 Checking transport properties...")
        logger.info(f"Transport attributes: {dir(client._transport)}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())