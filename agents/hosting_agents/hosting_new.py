import asyncio
import time
from typing import List, Dict

# Google ADK imports
from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ==================== MANUAL ORCHESTRATOR ====================
async def manual_orchestrator():
    """Manually orchestrate calls to all three agents sequentially"""
    print("=" * 60)
    print("MANUAL HEALTHCARE ORCHESTRATOR")
    print("=" * 60)
    
    print("\n🔧 Creating remote A2A agents...")
    
    # Create agents
    policy_agent = RemoteA2aAgent(
        name="PolicyAgent",
        description="Insurance coverage expert",
        agent_card=f"http://localhost:8887{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    
    research_agent = RemoteA2aAgent(
        name="ResearchAgent",
        description="Medical information expert",
        agent_card=f"http://localhost:8888{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    
    provider_agent = RemoteA2aAgent(
        name="ProviderAgent",
        description="Healthcare provider expert",
        agent_card=f"http://localhost:8889{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    
    print("✅ Created all 3 agents")
    
    # Setup session service
    session_service = InMemorySessionService()
    APP_NAME = "manual_orchestrator"
    USER_ID = "user_123"
    
    # Test query
    query = "My child has a fever of 102°F and we have UnitedHealthcare, who should we see?"
    print(f"\n🧑‍💻 USER QUERY: {query}")
    print("-" * 60)
    
    # Create individual sessions for each agent
    responses = {}
    
    # STEP 1: Call PolicyAgent
    print("\n1️⃣ STEP 1: Calling PolicyAgent for insurance analysis...")
    session_id_1 = f"session_{int(time.time())}_policy"
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id_1
    )
    
    runner1 = Runner(
        agent=policy_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    
    policy_content = types.Content(
        role="user", 
        parts=[types.Part(text=f"Insurance analysis for: {query}")]
    )
    
    policy_response = ""
    for event in runner1.run(
        user_id=USER_ID, 
        session_id=session_id_1, 
        new_message=policy_content
    ):
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    policy_response += part.text + "\n"
    
    responses['PolicyAgent'] = policy_response[:500] + "..." if len(policy_response) > 500 else policy_response
    print(f"✅ PolicyAgent response received ({len(policy_response)} chars)")
    
    # STEP 2: Call ResearchAgent
    print("\n2️⃣ STEP 2: Calling ResearchAgent for medical analysis...")
    session_id_2 = f"session_{int(time.time())}_research"
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id_2
    )
    
    runner2 = Runner(
        agent=research_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    
    research_content = types.Content(
        role="user", 
        parts=[types.Part(text=f"Medical analysis for: {query}")]
    )
    
    research_response = ""
    for event in runner2.run(
        user_id=USER_ID, 
        session_id=session_id_2, 
        new_message=research_content
    ):
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    research_response += part.text + "\n"
    
    responses['ResearchAgent'] = research_response[:500] + "..." if len(research_response) > 500 else research_response
    print(f"✅ ResearchAgent response received ({len(research_response)} chars)")
    
    # STEP 3: Call ProviderAgent
    print("\n3️⃣ STEP 3: Calling ProviderAgent for provider analysis...")
    session_id_3 = f"session_{int(time.time())}_provider"
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id_3
    )
    
    runner3 = Runner(
        agent=provider_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    
    provider_content = types.Content(
        role="user", 
        parts=[types.Part(text=f"Provider analysis for: {query}")]
    )
    
    provider_response = ""
    for event in runner3.run(
        user_id=USER_ID, 
        session_id=session_id_3, 
        new_message=provider_content
    ):
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    provider_response += part.text + "\n"
    
    responses['ProviderAgent'] = provider_response[:500] + "..." if len(provider_response) > 500 else provider_response
    print(f"✅ ProviderAgent response received ({len(provider_response)} chars)")
    
    # STEP 4: Synthesize results
    print("\n" + "=" * 60)
    print("4️⃣ STEP 4: SYNTHESIZING ALL RESPONSES")
    print("=" * 60)
    
    print(f"\n📊 SUMMARY: All 3 agents consulted successfully!")
    print(f"• PolicyAgent: ✓ ({len(policy_response)} chars)")
    print(f"• ResearchAgent: ✓ ({len(research_response)} chars)")
    print(f"• ProviderAgent: ✓ ({len(provider_response)} chars)")
    
    print("\n" + "🔵" * 30 + " FINAL INTEGRATED RESPONSE " + "🔵" * 30)
    
    # Create final synthesized response
    final_response = f"""
COMPREHENSIVE HEALTHCARE ANALYSIS FOR: "{query}"

================================================================================
1. INSURANCE PERSPECTIVE (PolicyAgent)
================================================================================
{policy_response[:800]}{'...' if len(policy_response) > 800 else ''}

================================================================================
2. MEDICAL PERSPECTIVE (ResearchAgent)  
================================================================================
{research_response[:800]}{'...' if len(research_response) > 800 else ''}

================================================================================
3. PROVIDER PERSPECTIVE (ProviderAgent)
================================================================================
{provider_response[:800]}{'...' if len(provider_response) > 800 else ''}

================================================================================
🎯 INTEGRATED RECOMMENDATION
================================================================================
Based on analysis from all three specialists:

• INSURANCE ACTION: {extract_key_point(policy_response, 'action')}
• MEDICAL PRIORITY: {extract_key_point(research_response, 'priority')}  
• PROVIDER RECOMMENDATION: {extract_key_point(provider_response, 'recommendation')}

Immediate Next Steps:
1. Contact your pediatrician or urgent care based on PolicyAgent guidance
2. Monitor symptoms as ResearchAgent advised
3. Schedule appointment with recommended providers

Note: This is synthesized advice from PolicyAgent, ResearchAgent, and ProviderAgent.
"""
    
    print(final_response)
    print("🔵" * 80 + "\n")

def extract_key_point(text: str, point_type: str) -> str:
    """Extract key points from agent responses"""
    if not text:
        return "No information provided"
    
    # Simple extraction logic
    lines = text.split('\n')
    for line in lines:
        line_lower = line.lower()
        if point_type == 'action' and any(word in line_lower for word in ['recommend', 'suggest', 'advise', 'should']):
            return line[:150]
        elif point_type == 'priority' and any(word in line_lower for word in ['urgent', 'immediate', 'emergency', 'serious']):
            return line[:150]
        elif point_type == 'recommendation' and any(word in line_lower for word in ['doctor', 'provider', 'specialist', 'clinic']):
            return line[:150]
    
    return lines[0][:100] + "..." if lines else "Key point not specified"

# ==================== ALTERNATIVE: PARALLEL EXECUTION ====================
async def parallel_orchestrator():
    """Run all agents in parallel"""
    print("\n" + "=" * 60)
    print("PARALLEL AGENT EXECUTION")
    print("=" * 60)
    
    # Create agents
    policy_agent = RemoteA2aAgent(
        name="PolicyAgent",
        agent_card=f"http://localhost:8887{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    
    research_agent = RemoteA2aAgent(
        name="ResearchAgent",
        agent_card=f"http://localhost:8888{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    
    provider_agent = RemoteA2aAgent(
        name="ProviderAgent",
        agent_card=f"http://localhost:8889{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    
    query = "I have abdominal pain and Blue Cross insurance"
    print(f"\n🧑‍💻 QUERY: {query}")
    
    async def call_agent(agent, agent_name, query_part):
        """Call a single agent"""
        session_service = InMemorySessionService()
        session_id = f"session_{int(time.time())}_{agent_name}"
        
        await session_service.create_session(
            app_name="parallel_orch",
            user_id="user_123",
            session_id=session_id
        )
        
        runner = Runner(
            agent=agent,
            app_name="parallel_orch",
            session_service=session_service,
        )
        
        content = types.Content(
            role="user", 
            parts=[types.Part(text=f"{query_part}: {query}")]
        )
        
        response = ""
        try:
            for event in runner.run(
                user_id="user_123",
                session_id=session_id,
                new_message=content
            ):
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response += part.text + "\n"
            
            return (agent_name, response[:300] + "..." if len(response) > 300 else response)
        except Exception as e:
            return (agent_name, f"Error: {str(e)}")
    
    # Run all agents in parallel
    print("\n🚀 Running all 3 agents in parallel...")
    
    tasks = [
        call_agent(policy_agent, "PolicyAgent", "Insurance analysis"),
        call_agent(research_agent, "ResearchAgent", "Medical analysis"),
        call_agent(provider_agent, "ProviderAgent", "Provider analysis"),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\n📊 PARALLEL EXECUTION RESULTS:")
    for agent_name, response in results:
        if isinstance(response, Exception):
            print(f"❌ {agent_name}: {response}")
        else:
            print(f"✅ {agent_name}: {len(response)} chars")
            print(f"   Preview: {response[:150]}...")

# ==================== HYBRID SOLUTION ====================
async def hybrid_solution():
    """Hybrid: Use LLM orchestrator but manually trigger all agents"""
    print("\n" + "=" * 60)
    print("HYBRID SOLUTION: LLM + MANUAL ORCHESTRATION")
    print("=" * 60)
    
    # Create agents
    policy_agent = RemoteA2aAgent(
        name="PolicyAgent",
        agent_card=f"http://localhost:8887{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    
    research_agent = RemoteA2aAgent(
        name="ResearchAgent",
        agent_card=f"http://localhost:8888{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    
    provider_agent = RemoteA2aAgent(
        name="ProviderAgent",
        agent_card=f"http://localhost:8889{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    
    # Create a simple LLM for synthesis only
    synthesizer = LlmAgent(
        name="ResponseSynthesizer",
        description="Synthesizes responses from multiple agents",
        model=LiteLlm("bedrock/us.anthropic.claude-3-haiku-20240307-v1:0"),
        instruction="""You synthesize responses from healthcare specialists.
        
        You will receive responses from:
        1. PolicyAgent (insurance expert)
        2. ResearchAgent (medical expert)
        3. ProviderAgent (provider expert)
        
        Create a comprehensive response that integrates all three perspectives.
        Format clearly with sections for each agent and a final integrated recommendation.""",
    )
    
    # Test query
    query = "My child has a fever of 102°F and we have UnitedHealthcare"
    
    # Step 1: Get all agent responses manually
    print("\n🔧 Step 1: Collecting responses from all agents...")
    
    responses = {}
    agents = [
        ("PolicyAgent", policy_agent, "Insurance coverage analysis for child with fever"),
        ("ResearchAgent", research_agent, "Medical assessment of 102°F fever in child"),
        ("ProviderAgent", provider_agent, "Healthcare providers for child with fever"),
    ]
    
    for agent_name, agent, prompt in agents:
        print(f"   Calling {agent_name}...")
        session_service = InMemorySessionService()
        session_id = f"session_{int(time.time())}_{agent_name}"
        
        await session_service.create_session(
            app_name="hybrid",
            user_id="user",
            session_id=session_id
        )
        
        runner = Runner(
            agent=agent,
            app_name="hybrid",
            session_service=session_service,
        )
        
        content = types.Content(
            role="user", 
            parts=[types.Part(text=prompt)]
        )
        
        response_text = ""
        for event in runner.run(
            user_id="user",
            session_id=session_id,
            new_message=content
        ):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text + "\n"
        
        responses[agent_name] = response_text
        print(f"   ✅ {agent_name}: {len(response_text)} chars")
    
    # Step 2: Synthesize with LLM
    print("\n🔧 Step 2: Synthesizing all responses...")
    
    synthesis_prompt = f"""
    User Query: {query}
    
    Agent Responses:
    PolicyAgent (Insurance): {responses.get('PolicyAgent', 'No response')}
    ResearchAgent (Medical): {responses.get('ResearchAgent', 'No response')}
    ProviderAgent (Providers): {responses.get('ProviderAgent', 'No response')}
    
    Create a comprehensive, integrated response.
    """
    
    session_service = InMemorySessionService()
    session_id = f"session_{int(time.time())}_synthesis"
    
    await session_service.create_session(
        app_name="hybrid",
        user_id="user",
        session_id=session_id
    )
    
    runner = Runner(
        agent=synthesizer,
        app_name="hybrid",
        session_service=session_service,
    )
    
    content = types.Content(
        role="user", 
        parts=[types.Part(text=synthesis_prompt)]
    )
    
    print("\n" + "🎯" * 30 + " FINAL SYNTHESIZED RESPONSE " + "🎯" * 30)
    
    for event in runner.run(
        user_id="user",
        session_id=session_id,
        new_message=content
    ):
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    print(part.text)
    
    print("🎯" * 80 + "\n")

# ==================== MAIN ====================
async def main():
    print("=" * 60)
    print("HEALTHCARE ORCHESTRATION SOLUTIONS")
    print("=" * 60)
    print("\nChoose approach:")
    print("1. Manual Sequential Orchestrator")
    print("2. Parallel Execution")
    print("3. Hybrid Solution (LLM Synthesis)")
    
    # Run all approaches
    print("\n" + "=" * 60)
    await manual_orchestrator()
    
    print("\n" + "=" * 60)
    await parallel_orchestrator()
    
    print("\n" + "=" * 60)
    await hybrid_solution()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()