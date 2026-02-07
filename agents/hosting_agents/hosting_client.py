# test_a2a_direct.py
import asyncio
import httpx
import json

async def test_a2a_agent(agent_url: str, query: str):
    """Test an A2A agent directly"""
    print(f"\n🔍 Testing agent at: {agent_url}")
    
    # 1. Get agent card
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get agent card
            agent_card_url = f"{agent_url}/.well-known/agent-card.json"
            response = await client.get(agent_card_url)
            
            if response.status_code == 200:
                agent_card = response.json()
                print(f"✅ Agent card loaded:")
                print(f"   Name: {agent_card.get('name')}")
                print(f"   Description: {agent_card.get('description')}")
            else:
                print(f"❌ Failed to get agent card: {response.status_code}")
                return
            
            # 2. Test invoke endpoint
            invoke_url = f"{agent_url}/invoke"
            payload = {
                "jsonrpc": "2.0",
                "method": "invoke",
                "params": {
                    "input": query,
                    "session_id": "test_session_123"
                },
                "id": 1
            }
            
            print(f"\n📤 Sending query: '{query}'")
            response = await client.post(
                invoke_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    print(f"✅ Agent response:")
                    print(f"   Output: {result['result'].get('output', 'No output')}")
                elif "error" in result:
                    print(f"❌ Agent error: {result['error']}")
                else:
                    print(f"⚠️  Unexpected response format: {result}")
            else:
                print(f"❌ Invoke failed: {response.status_code}")
                print(f"   Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Connection error: {e}")

async def main():
    """Test all A2A agents"""
    agents = {
        "PolicyAgent": "http://localhost:8887",
        "ResearchAgent": "http://localhost:8888",
        "ProviderAgent": "http://localhost:8889"
    }
    
    test_query = "I have Blue Cross insurance and abdominal pain"
    
    for name, url in agents.items():
        await test_a2a_agent(url, test_query)

if __name__ == "__main__":
    asyncio.run(main())