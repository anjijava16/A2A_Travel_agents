import asyncio
import time
from typing import Dict, List

# Google ADK imports
from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ==================== ENHANCED MANUAL ORCHESTRATOR ====================
class HealthcareOrchestrator:
    """Enhanced orchestrator with better error handling and synthesis"""
    
    def __init__(self):
        self.agents = {}
        self.session_service = InMemorySessionService()
        self.app_name = "healthcare_orchestrator"
        self.user_id = "user_123"
    
    async def initialize_agents(self):
        """Initialize all three A2A agents"""
        print("🔧 Initializing healthcare agents...")
        
        self.agents = {
            'policy': RemoteA2aAgent(
                name="PolicyAgent",
                description="Insurance coverage expert",
                agent_card=f"http://localhost:8887{AGENT_CARD_WELL_KNOWN_PATH}",
            ),
            'research': RemoteA2aAgent(
                name="ResearchAgent",
                description="Medical information expert",
                agent_card=f"http://localhost:8888{AGENT_CARD_WELL_KNOWN_PATH}",
            ),
            'provider': RemoteA2aAgent(
                name="ProviderAgent",
                description="Healthcare provider expert",
                agent_card=f"http://localhost:8889{AGENT_CARD_WELL_KNOWN_PATH}",
            )
        }
        print("✅ All 3 agents initialized")
    
    async def call_agent(self, agent_key: str, query: str, context: str = "") -> str:
        """Call a specific agent and get response"""
        agent = self.agents[agent_key]
        agent_name = agent.name
        
        # Create session for this call
        session_id = f"{self.app_name}_{agent_key}_{int(time.time())}"
        await self.session_service.create_session(
            app_name=self.app_name,
            user_id=self.user_id,
            session_id=session_id
        )
        
        runner = Runner(
            agent=agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )
        
        # Create enhanced query with context
        full_query = f"{query}\n\nContext: {context}" if context else query
        
        content = types.Content(
            role="user",
            parts=[types.Part(text=full_query)]
        )
        
        response_text = ""
        try:
            for event in runner.run(
                user_id=self.user_id,
                session_id=session_id,
                new_message=content
            ):
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text + "\n"
            
            return response_text.strip()
            
        except Exception as e:
            return f"Error calling {agent_name}: {str(e)}"
    
    async def orchestrate_query(self, user_query: str, user_location: str = "") -> Dict:
        """Orchestrate a user query across all three agents"""
        print(f"\n🧑‍💻 USER QUERY: {user_query}")
        if user_location:
            print(f"📍 User Location: {user_location}")
        print("-" * 60)
        
        responses = {}
        
        # Step 1: Policy Agent (Insurance)
        print("\n1️⃣ Calling PolicyAgent for insurance analysis...")
        policy_query = f"Insurance coverage analysis for: {user_query}"
        responses['policy'] = await self.call_agent('policy', policy_query)
        print(f"   ✅ Received {len(responses['policy'])} characters")
        
        # Step 2: Research Agent (Medical)
        print("\n2️⃣ Calling ResearchAgent for medical analysis...")
        research_query = f"Medical assessment and recommendations for: {user_query}"
        responses['research'] = await self.call_agent('research', research_query)
        print(f"   ✅ Received {len(responses['research'])} characters")
        
        # Step 3: Provider Agent (Doctors/Facilities)
        print("\n3️⃣ Calling ProviderAgent for provider recommendations...")
        provider_query = f"Find healthcare providers for: {user_query}"
        if user_location:
            provider_query += f"\nLocation: {user_location}"
        else:
            provider_query += "\nPlease provide general guidance on types of providers to consider."
        
        responses['provider'] = await self.call_agent('provider', provider_query)
        print(f"   ✅ Received {len(responses['provider'])} characters")
        
        return responses
    
    def synthesize_responses(self, user_query: str, responses: Dict) -> str:
        """Synthesize all agent responses into comprehensive answer"""
        
        print("\n" + "=" * 60)
        print("4️⃣ SYNTHESIZING COMPREHENSIVE RESPONSE")
        print("=" * 60)
        
        # Create final synthesis
        synthesis = f"""
# 🏥 COMPREHENSIVE HEALTHCARE GUIDANCE

## 📋 Original Query
"{user_query}"

## 🔍 Analysis from Specialist Agents

### 1. 🛡️ Insurance Coverage (PolicyAgent)
{responses['policy'][:1000]}{'...' if len(responses['policy']) > 1000 else ''}

### 2. 🩺 Medical Assessment (ResearchAgent)
{responses['research'][:1000]}{'...' if len(responses['research']) > 1000 else ''}

### 3. 🏥 Provider Recommendations (ProviderAgent)
{responses['provider'][:1000]}{'...' if len(responses['provider']) > 1000 else ''}

## 🎯 Integrated Action Plan

### Immediate Steps:
1. **Insurance Verification**: {self._extract_action(responses['policy'], 'insurance')}
2. **Medical Priority**: {self._extract_action(responses['research'], 'medical')}
3. **Provider Selection**: {self._extract_action(responses['provider'], 'provider')}

### Timeline:
- **Today**: {self._extract_timeline(responses['research'], 'today')}
- **This Week**: {self._extract_timeline(responses['policy'], 'week')}

### Key Considerations:
{self._extract_considerations(responses)}

## 📞 Next Actions
1. Contact providers as recommended
2. Verify insurance coverage details
3. Schedule appropriate appointments

---
*This guidance combines expertise from PolicyAgent (insurance), ResearchAgent (medical), and ProviderAgent (provider selection).*
"""
        
        return synthesis
    
    def _extract_action(self, text: str, action_type: str) -> str:
        """Extract action items from agent responses"""
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            if action_type == 'insurance' and any(word in line_lower for word in ['coverage', 'copay', 'deductible', 'covered', 'network']):
                return line[:120].strip()
            elif action_type == 'medical' and any(word in line_lower for word in ['recommend', 'suggest', 'advise', 'should', 'urgent', 'immediate']):
                return line[:120].strip()
            elif action_type == 'provider' and any(word in line_lower for word in ['doctor', 'provider', 'specialist', 'clinic', 'hospital']):
                return line[:120].strip()
        
        return "Review the detailed recommendations above"
    
    def _extract_timeline(self, text: str, timeframe: str) -> str:
        """Extract timeline information"""
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            if timeframe == 'today' and any(word in line_lower for word in ['today', 'immediate', 'urgent', 'now', 'right away']):
                return line[:100].strip()
            elif timeframe == 'week' and any(word in line_lower for word in ['week', 'soon', 'schedule', 'appointment']):
                return line[:100].strip()
        
        return "Follow up as appropriate"
    
    def _extract_considerations(self, responses: Dict) -> str:
        """Extract key considerations"""
        considerations = []
        
        # Check each response for important considerations
        for key, response in responses.items():
            lines = response.split('\n')
            for line in lines:
                line_lower = line.lower()
                if any(word in line_lower for word in ['important', 'note', 'warning', 'consider', 'caution', 'critical']):
                    if len(line.strip()) > 20:  # Avoid very short lines
                        considerations.append(f"- {key.title()}: {line.strip()}")
                        if len(considerations) >= 3:
                            break
        
        if not considerations:
            considerations = [
                "- Verify all information with your actual insurance policy",
                "- Consult with healthcare providers for personalized advice",
                "- Consider location and availability when selecting providers"
            ]
        
        return '\n'.join(considerations[:5])  # Limit to top 5
    
    async def run_interactive_session(self):
        """Run interactive session with user input"""
        print("=" * 60)
        print("🏥 HEALTHCARE ORCHESTRATOR - INTERACTIVE MODE")
        print("=" * 60)
        
        await self.initialize_agents()
        
        while True:
            print("\n" + "─" * 60)
            user_query = input("\n💬 Enter your healthcare query (or 'quit' to exit): ").strip()
            
            if user_query.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Thank you for using Healthcare Orchestrator!")
                break
            
            if not user_query:
                print("⚠️  Please enter a query")
                continue
            
            location = input("📍 Enter your location (city, state - optional): ").strip()
            
            print(f"\n🔍 Processing your query...")
            
            try:
                # Get responses from all agents
                responses = await self.orchestrate_query(user_query, location)
                
                # Synthesize final response
                final_response = self.synthesize_responses(user_query, responses)
                
                # Display final response
                print("\n" + "✅" * 30 + " FINAL GUIDANCE " + "✅" * 30)
                print(final_response)
                print("✅" * 76 + "\n")
                
                # Show summary
                print("\n📊 CONSULTATION SUMMARY:")
                print(f"   • PolicyAgent: {len(responses['policy'])} characters")
                print(f"   • ResearchAgent: {len(responses['research'])} characters")
                print(f"   • ProviderAgent: {len(responses['provider'])} characters")
                print(f"   • Total expertise combined: ✓")
                
            except Exception as e:
                print(f"❌ Error processing query: {e}")
                import traceback
                traceback.print_exc()

# ==================== BATCH TESTING ====================
async def run_test_suite():
    """Run a suite of test queries"""
    print("=" * 60)
    print("🧪 HEALTHCARE ORCHESTRATOR TEST SUITE")
    print("=" * 60)
    
    orchestrator = HealthcareOrchestrator()
    await orchestrator.initialize_agents()
    
    test_cases = [
        {
            "query": "My child has a fever of 102°F and we have UnitedHealthcare, who should we see?",
            "location": "San Francisco, CA"
        },
        {
            "query": "I have persistent abdominal pain and Blue Cross insurance",
            "location": "New York, NY"
        },
        {
            "query": "Need a dermatologist for skin rash, have Cigna insurance",
            "location": "Austin, TX"
        },
        {
            "query": "Annual physical exam coverage with Aetna",
            "location": "Chicago, IL"
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\n{'='*50}")
        print(f"TEST {i+1}: {test_case['query']}")
        print(f"{'='*50}")
        
        responses = await orchestrator.orchestrate_query(
            test_case['query'],
            test_case['location']
        )
        
        # Quick summary
        print(f"\n📋 Results:")
        print(f"   • PolicyAgent: ✓ ({len(responses['policy'])} chars)")
        print(f"   • ResearchAgent: ✓ ({len(responses['research'])} chars)")
        print(f"   • ProviderAgent: ✓ ({len(responses['provider'])} chars)")
        
        # Show key insights
        print(f"\n💡 Key Insights:")
        
        # Extract first important line from each
        for key in ['policy', 'research', 'provider']:
            lines = responses[key].split('\n')
            for line in lines:
                if line.strip() and len(line.strip()) > 20:
                    print(f"   • {key.title()}: {line.strip()[:80]}...")
                    break

# ==================== MAIN ====================
async def main():
    """Main function"""
    print("=" * 60)
    print("🏥 HEALTHCARE MULTI-AGENT ORCHESTRATION SYSTEM")
    print("=" * 60)
    
    print("\nChoose mode:")
    print("1. Interactive Session (Enter your own queries)")
    print("2. Test Suite (Run predefined test cases)")
    print("3. Quick Single Query")
    
    choice = input("\nEnter choice (1, 2, or 3): ").strip()
    
    orchestrator = HealthcareOrchestrator()
    await orchestrator.initialize_agents()
    
    if choice == "1":
        # Interactive mode
        await orchestrator.run_interactive_session()
    
    elif choice == "2":
        # Test suite
        await run_test_suite()
    
    elif choice == "3":
        # Quick single query
        query = input("\n💬 Enter your healthcare query: ").strip()
        location = input("📍 Enter your location (optional): ").strip()
        
        print(f"\n🔍 Processing: {query}")
        if location:
            print(f"📍 Location: {location}")
        
        responses = await orchestrator.orchestrate_query(query, location)
        final_response = orchestrator.synthesize_responses(query, responses)
        
        print("\n" + "✅" * 30 + " RESULTS " + "✅" * 30)
        print(final_response)
        print("✅" * 68 + "\n")
    
    else:
        print("❌ Invalid choice. Running test suite...")
        await run_test_suite()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Session interrupted")
    except Exception as e:
        print(f"\n❌ System error: {e}")
        import traceback
        traceback.print_exc()