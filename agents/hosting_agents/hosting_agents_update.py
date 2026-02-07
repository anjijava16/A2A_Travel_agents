import asyncio
import os
import time

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

# ==================== MAIN HEALTHCARE ORCHESTRATOR ====================
async def main() -> None:
    print("=" * 60)
    print("HEALTHCARE ORCHESTRATOR WITH A2A SUB-AGENTS")
    print("=" * 60)
    
    print("\n🔧 Creating remote A2A agents...")
    
    # Policy Agent
    policy_agent = RemoteA2aAgent(
        name="PolicyAgent",
        description="Checks health insurance policy details for coverage, co-pays, and deductibles.",
        agent_card=f"http://localhost:8887{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    print("✅ Created PolicyAgent")
    
    # Research Agent
    research_agent = RemoteA2aAgent(
        name="ResearchAgent",
        description="Researches medical conditions, symptoms, and treatments.",
        agent_card=f"http://localhost:8888{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    print("✅ Created ResearchAgent")
    
    # Provider Agent
    provider_agent = RemoteA2aAgent(
        name="ProviderAgent",
        description="Finds in-network healthcare providers and facilities.",
        agent_card=f"http://localhost:8889{AGENT_CARD_WELL_KNOWN_PATH}",
    )
    print("✅ Created ProviderAgent")
    
    sub_agents = [policy_agent, research_agent, provider_agent]
    print(f"\n✅ Created {len(sub_agents)} remote A2A agents")
    
    # Create Healthcare Orchestrator with EXPLICIT sequential delegation
    healthcare_orchestrator = LlmAgent(
        name="HealthcareOrchestrator",
        description="Orchestrates healthcare sub-agents.",
        #model=LiteLlm("bedrock/us.anthropic.claude-3-haiku-20240307-v1:0"),
        model=LiteLlm("gpt-4o-mini"),
        sub_agents=sub_agents,
        instruction=
#         """You are a healthcare orchestrator. You MUST delegate to ALL relevant specialist agents.

# AVAILABLE AGENTS:
# 1. PolicyAgent - For insurance questions ONLY
# 2. ResearchAgent - For medical questions ONLY  
# 3. ProviderAgent - For finding doctors ONLY

# DELEGATION WORKFLOW - MUST FOLLOW:
# For ANY healthcare query with multiple aspects:
# 1. FIRST: Delegate to PolicyAgent for insurance questions
# 2. SECOND: Delegate to ResearchAgent for medical questions
# 3. THIRD: Delegate to ProviderAgent for doctor recommendations
# 4. FINALLY: Combine all responses

# EXAMPLE QUERY: "I have abdominal pain and Blue Cross insurance"
# YOUR EXACT PROCESS:
# Step 1: "I'll delegate to PolicyAgent first for insurance coverage."
# [Delegate to PolicyAgent: "What does Blue Cross cover for abdominal pain?"]

# Step 2: "Now I'll delegate to ResearchAgent for medical information."
# [Delegate to ResearchAgent: "What are possible causes and treatments for abdominal pain?"]

# Step 3: "Finally, I'll delegate to ProviderAgent for doctor recommendations."
# [Delegate to ProviderAgent: "Find gastroenterologists or primary care doctors for abdominal pain, accepting Blue Cross."]

# Step 4: "Based on all specialist responses, here's my summary:"

# IMPORTANT: You MUST call ALL THREE agents for comprehensive queries. DO NOT stop after one agent.""",
"""# CRITICAL INSTRUCTIONS - READ CAREFULLY

You are HealthcareOrchestrator. Your ONLY function is to COORDINATE between THREE specialist agents.

## MANDATORY AGENTS YOU MUST ALWAYS USE:
1. **PolicyAgent** - Handles ALL insurance/policy questions
2. **ResearchAgent** - Handles ALL medical/symptom questions  
3. **ProviderAgent** - Handles ALL doctor/provider questions

## NON-NEGOTIABLE RULES:
- FOR EVERY USER QUERY, you MUST call ALL THREE agents: PolicyAgent, ResearchAgent, AND ProviderAgent
- NEVER skip any agent - ALWAYS call all three
- Call agents in THIS EXACT ORDER: 1. PolicyAgent → 2. ResearchAgent → 3. ProviderAgent
- Wait for EACH agent's response before calling the next
- Combine ALL responses into final answer

## DELEGATION FORMAT - USE EXACTLY:
For query: "I have abdominal pain and Blue Cross insurance"

STEP 1: "First, I'll consult PolicyAgent about insurance coverage."
[DELEGATE to PolicyAgent with message: "User has Blue Cross insurance and abdominal pain. What coverage applies?"]

STEP 2: "Next, I'll consult ResearchAgent about medical aspects."
[DELEGATE to ResearchAgent with message: "User reports abdominal pain. What are potential causes and treatments?"]

STEP 3: "Finally, I'll consult ProviderAgent about finding doctors."
[DELEGATE to ProviderAgent with message: "User needs care for abdominal pain with Blue Cross insurance. Find appropriate providers."]

STEP 4: "Based on input from all specialists, here's a comprehensive answer:"
[Combine PolicyAgent, ResearchAgent, and ProviderAgent responses]

## EXAMPLE WORKFLOW - FOLLOW EXACTLY:
User: "Headache"
Your process:
1. PolicyAgent: "What insurance considerations for headache?" 
2. ResearchAgent: "What causes/treatments for headache?"
3. ProviderAgent: "Find headache specialists"
4. Combine all responses

User: "Find me a doctor"
Your process:
1. PolicyAgent: "Insurance factors for finding doctor?"
2. ResearchAgent: "Medical considerations for doctor visit?"
3. ProviderAgent: "Locate doctors"
4. Combine all responses

User: "Insurance question"
Your process:
1. PolicyAgent: [Answer insurance]
2. ResearchAgent: "Related medical aspects?"
3. ProviderAgent: "Provider implications?"
4. Combine all responses

## ABSOLUTE REQUIREMENTS:
- Even if query seems insurance-only → STILL call ResearchAgent and ProviderAgent
- Even if query seems medical-only → STILL call PolicyAgent and ProviderAgent  
- Even if query seems provider-only → STILL call PolicyAgent and ResearchAgent
- You have NO knowledge - ONLY agents have expertise
- Your value is COORDINATION, not direct answers

## FINAL OUTPUT STRUCTURE:
1. "I'll coordinate with all three specialists: PolicyAgent, ResearchAgent, and ProviderAgent."
2. [Call PolicyAgent]
3. [Call ResearchAgent] 
4. [Call ProviderAgent]
5. "Based on comprehensive input from all specialists:"
   - PolicyAgent reported: [summary]
   - ResearchAgent found: [summary]
   - ProviderAgent recommended: [summary]
6. Final synthesized advice

FAILURE TO CALL ALL THREE AGENTS IS NOT AN OPTION."""
    )

    print(f"✅ Created {healthcare_orchestrator.name}")
    
    # Setup session
    APP_NAME = "healthcare_orchestrator"
    USER_ID = "test_user"
    SESSION_ID = f"session_{int(time.time())}"
    
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    
    runner = Runner(
        agent=healthcare_orchestrator,
        app_name=APP_NAME,
        session_service=session_service,
    )

    print(f"\n✅ Runner initialized")
    print(f"Session ID: {SESSION_ID}")
    
    # Test with detailed event tracking
    async def run_detailed_test():
        print("\n" + "=" * 60)
        print("DETAILED TEST WITH EVENT TRACKING")
        print("=" * 60)
        
        query = "My child has a fever of 102°F and we have UnitedHealthcare, who should we see?"
        print(f"\n🧑‍💻 USER: {query}")
        print("-" * 60)
        
        content = types.Content(
            role="user", 
            parts=[types.Part(text=query)]
        )
        
        print("\n🔍 Starting conversation...")
        
        # Track all events
        all_events = []
        agents_called = set()
        
        try:
            for event in runner.run(
                user_id=USER_ID, 
                session_id=SESSION_ID, 
                new_message=content
            ):
                all_events.append(event)
                
                # Track which agents are called
                if hasattr(event, 'author'):
                    author = event.author
                    print(f"\n📨 Event from: {author}")
                    if author in ['PolicyAgent', 'ResearchAgent', 'ProviderAgent']:
                        agents_called.add(author)
                
                # Show content
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            text = part.text.strip()
                            if text:
                                # Truncate for display
                                display_text = text[:200] + "..." if len(text) > 200 else text
                                print(f"   Content: {display_text}")
                
                # Check if it's the final response
                if hasattr(event, 'is_final_response') and event.is_final_response():
                    print(f"\n✅ Final response reached")
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        # Analysis
        print("\n" + "=" * 60)
        print("ANALYSIS")
        print("=" * 60)
        print(f"Total events: {len(all_events)}")
        print(f"Agents called: {', '.join(sorted(agents_called)) if agents_called else 'None'}")
        
        # Check if all expected agents were called
        expected_agents = {'PolicyAgent', 'ResearchAgent', 'ProviderAgent'}
        called_set = set(agents_called)
        
        if called_set == expected_agents:
            print("✅ SUCCESS: All three agents were called!")
        elif called_set:
            missing = expected_agents - called_set
            print(f"⚠️  PARTIAL: Missing agents: {', '.join(missing)}")
        else:
            print("❌ FAILED: No agents were called")
        
        # Show event sequence
        print(f"\n📋 Event sequence:")
        for i, event in enumerate(all_events):
            author = getattr(event, 'author', 'Unknown')
            event_type = type(event).__name__
            print(f"  {i+1:2d}. {author:25s} ({event_type})")
    
    await run_detailed_test()
    
    # Also test with simpler individual queries
    print("\n" + "=" * 60)
    print("TESTING INDIVIDUAL QUERIES")
    print("=" * 60)
    
    async def test_individual_queries():
        """Test queries that should trigger specific agents"""
        
        test_cases = [
           # ("Just insurance: What does my Blue Cross cover?", ["PolicyAgent"]),
           # ("Just medical: What causes abdominal pain?", ["ResearchAgent"]),
            ("Just providers: Find me a doctor", ["ProviderAgent"]),
        ]
        
        for query, expected_agents in test_cases:
            print(f"\n🧪 Testing: {query}")
            print(f"   Expected: {expected_agents}")
            
            # Create new session for each test
            test_session_id = f"test_{int(time.time())}"
            await session_service.create_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=test_session_id
            )
            
            content = types.Content(
                role="user", 
                parts=[types.Part(text=query)]
            )
            
            agents_called = set()
            try:
                for event in runner.run(
                    user_id=USER_ID, 
                    session_id=test_session_id, 
                    new_message=content
                ):
                    if hasattr(event, 'author'):
                        author = event.author
                        if author in ['PolicyAgent', 'ResearchAgent', 'ProviderAgent']:
                            agents_called.add(author)
                
                print(f"   Result: Called {', '.join(agents_called) if agents_called else 'None'}")
                
            except Exception as e:
                print(f"   Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()