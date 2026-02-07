# orchestrator/hosting_agent.py
import os
import uuid
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv

# Google ADK imports
from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.sessions import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.runners import Runner
from google.adk.tools.tool_context import ToolContext
from google import genai
from google.genai import types

# A2A imports for exposing this orchestrator
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor, A2aAgentExecutorConfig
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.task_manager import InMemoryTaskStore
from a2a.types import AgentCard, AgentSkill, AgentCapabilities

load_dotenv()

class ADKMultiAgentOrchestrator:
    """
    Production-grade orchestrator using Google ADK with A2A integration.
    
    Features:
    - LLM-based intent analysis for routing decisions
    - SequentialAgent for deterministic multi-agent execution
    - A2A protocol for cross-agent communication
    - State management for context passing between agents
    """
    
    def __init__(self):
        self.session_service = InMemorySessionService()
        self.memory_service = InMemoryMemoryService()
        self.artifact_service = InMemoryArtifactService()
        
        # A2A endpoints for remote agents (Policy, Research, Provider)
        self.agent_endpoints = {
            "policy": os.getenv("POLICY_AGENT_URL", "http://localhost:8001"),
            "research": os.getenv("RESEARCH_AGENT_URL", "http://localhost:8002"),
            "provider": os.getenv("PROVIDER_AGENT_URL", "http://localhost:8003")
        }
        
        # Initialize agents
        self._setup_agents()
        
    def _setup_agents(self):
        """Initialize all agents and workflows"""
        
        # 1. REMOTE A2A AGENTS (Your 3 specialized agents)
        # These connect to your existing Policy, Research, Provider agents via A2A
        
        self.policy_agent = RemoteA2aAgent(
            name="policy_agent",
            description="Validates compliance, checks rules, and ensures regulatory adherence. "
                       "Use this for: compliance checks, policy validation, rule interpretation, "
                       "risk assessment, and approval workflows.",
            agent_card=f"{self.agent_endpoints['policy']}/.well-known/agent.json",
            timeout=30.0
        )
        
        self.research_agent = RemoteA2aAgent(
            name="research_agent",
            description="Retrieves data, performs analysis, and gathers information. "
                       "Use this for: data lookup, market research, document analysis, "
                       "information synthesis, and fact-checking.",
            agent_card=f"{self.agent_endpoints['research']}/.well-known/agent.json",
            timeout=30.0
        )
        
        self.provider_agent = RemoteA2aAgent(
            name="provider_agent",
            description="Executes actions, performs operations, and interacts with external systems. "
                       "Use this for: API calls, database operations, file processing, "
                       "notifications, and external integrations.",
            agent_card=f"{self.agent_endpoints['provider']}/.well-known/agent.json",
            timeout=30.0
        )
        
        # 2. LLM ROUTER AGENT (Intelligent routing decision)
        # This uses Gemini to analyze intent and decide which agents to call
        
        self.router_agent = LlmAgent(
            name="intent_router",
            model="gemini-2.0-flash",
            description="Analyzes user queries and determines required agent capabilities",
            instruction=self._get_router_instruction(),
            tools=[
                AgentTool(agent=self.policy_agent),
                AgentTool(agent=self.research_agent),
                AgentTool(agent=self.provider_agent)
            ]
        )
        
        # 3. WORKFLOW AGENTS (Deterministic execution patterns)
        
        # Sequential: Policy -> Research -> Provider (Compliance-first workflow)
        self.compliance_workflow = SequentialAgent(
            name="compliance_first_workflow",
            description="Validates compliance before research and execution",
            sub_agents=[self.policy_agent, self.research_agent, self.provider_agent]
        )
        
        # Sequential: Research -> Policy -> Provider (Data-driven workflow)
        self.research_workflow = SequentialAgent(
            name="research_first_workflow",
            description="Gathers data first, then validates, then executes",
            sub_agents=[self.research_agent, self.policy_agent, self.provider_agent]
        )
        
        # Sequential: Research -> Provider (Direct execution workflow)
        self.direct_workflow = SequentialAgent(
            name="direct_workflow",
            description="For straightforward data-to-action requests",
            sub_agents=[self.research_agent, self.provider_agent]
        )
        
        # 4. MAIN ORCHESTRATOR AGENT
        # Combines LLM routing with workflow execution
        
        self.orchestrator = LlmAgent(
            name="hosting_orchestrator",
            model="gemini-2.0-flash",
            description="Main orchestrator that routes to appropriate workflow based on query analysis",
            instruction=self._get_orchestrator_instruction(),
            sub_agents=[
                self.compliance_workflow,
                self.research_workflow,
                self.direct_workflow,
                self.policy_agent,  # Fallback for single-agent
                self.research_agent,
                self.provider_agent
            ]
        )
        
        # 5. RUNNER for executing the orchestrator
        self.runner = Runner(
            app_name="hosting_orchestrator",
            agent=self.orchestrator,
            artifact_service=self.artifact_service,
            session_service=self.session_service,
            memory_service=self.memory_service
        )
    
    def _get_router_instruction(self) -> str:
        """System prompt for the intent router"""
        return """
        You are an intelligent intent analyzer. Your job is to:
        
        1. Analyze the user's query to understand what capabilities are needed
        2. Determine which agents must be involved and in what order
        3. Return a structured execution plan
        
        AVAILABLE AGENTS:
        - policy_agent: Compliance, rules validation, risk assessment, approvals
        - research_agent: Data retrieval, analysis, information gathering
        - provider_agent: Action execution, external operations, implementations
        
        DECISION RULES:
        - If query mentions "compliance", "rules", "approve", "validate" → Include policy_agent FIRST
        - If query mentions "research", "data", "analyze", "lookup" → Include research_agent
        - If query mentions "execute", "send", "create", "update", "delete" → Include provider_agent LAST
        
        WORKFLOW PATTERNS:
        1. "Check compliance then execute" → policy_agent → research_agent → provider_agent
        2. "Research then act" → research_agent → provider_agent
        3. "Validate data then process" → research_agent → policy_agent → provider_agent
        4. "Is this allowed?" → policy_agent only
        5. "Get information" → research_agent only
        
        OUTPUT FORMAT:
        Return JSON with:
        {
            "required_agents": ["agent_name", "agent_name"],
            "execution_order": ["first", "second", "third"],
            "workflow_type": "compliance_first|research_first|direct|single",
            "reasoning": "explanation of why this order"
        }
        
        Always prioritize compliance and safety. When in doubt, include policy_agent first.
        """
    
    def _get_orchestrator_instruction(self) -> str:
        """System prompt for the main orchestrator"""
        return """
        You are the Hosting Orchestrator managing Policy, Research, and Provider agents.
        
        Your workflow selection logic:
        
        1. ANALYZE the user query using your understanding
        2. SELECT the appropriate workflow:
           - Use 'compliance_first_workflow' if the request involves:
             * Regulatory requirements
             * Approval processes
             * Risk assessment needed before action
             * "Check if allowed" type queries
           
           - Use 'research_first_workflow' if the request involves:
             * Data needs to be gathered first
             * Analysis required before validation
             * "Research and validate" type queries
           
           - Use 'direct_workflow' if the request is:
             * Straightforward data lookup + action
             * No compliance validation needed
             * Low-risk operations
           
           - Use individual agents for simple, single-capability requests
        
        3. EXECUTE the selected workflow or agent
        4. RETURN the final result to the user
        
        IMPORTANT: 
        - Always explain which workflow you selected and why
        - If a workflow fails, fall back to individual agent calls
        - Maintain context between steps using session state
        """
    
    async def process_request(self, user_query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point for processing user requests
        
        Args:
            user_query: The user's natural language request
            session_id: Optional session ID for conversation continuity
            
        Returns:
            Dict containing execution results, agent chain, and metadata
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Create or retrieve session
        session = await self.session_service.get_session(
            app_name="hosting_orchestrator",
            user_id="default_user",
            session_id=session_id
        )
        
        if not session:
            session = await self.session_service.create_session(
                app_name="hosting_orchestrator",
                user_id="default_user",
                session_id=session_id,
                state={"conversation_history": []}
            )
        
        # Wrap user query in ADK Content format
        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_query)]
        )
        
        # Execute through the orchestrator
        start_time = datetime.now()
        final_response = []
        execution_trace = []
        
        try:
            async for event in self.runner.run_async(
                user_id="default_user",
                session_id=session_id,
                new_message=content
            ):
                # Track execution events for debugging
                if event.author:
                    execution_trace.append({
                        "timestamp": datetime.now().isoformat(),
                        "agent": event.author,
                        "event_type": type(event).__name__
                    })
                
                # Collect final response parts
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            final_response.append(part.text)
            
            # Compile results
            result = {
                "success": True,
                "session_id": session_id,
                "user_query": user_query,
                "response": "\n".join(final_response),
                "execution_trace": execution_trace,
                "metadata": {
                    "start_time": start_time.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "agents_involved": list(set([e["agent"] for e in execution_trace if e["agent"]]))
                }
            }
            
            # Update session state with history
            session.state["conversation_history"].append({
                "query": user_query,
                "response": result["response"],
                "timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "session_id": session_id,
                "user_query": user_query,
                "error": str(e),
                "execution_trace": execution_trace
            }


class ADKA2AServer:
    """
    Exposes the ADK orchestrator as an A2A server so other agents can communicate with it.
    """
    
    def __init__(self, orchestrator: ADKMultiAgentOrchestrator):
        self.orchestrator = orchestrator
        
        # Create the A2A-exposed agent
        self.a2a_agent = LlmAgent(
            name="hosting_orchestrator_a2a",
            model="gemini-2.0-flash",
            description="A2A-enabled hosting orchestrator for Policy, Research, and Provider agents",
            instruction="You are an A2A-enabled orchestrator. Process incoming tasks and coordinate with Policy, Research, and Provider agents.",
            tools=[
                self._process_orchestration_task
            ]
        )
        
        # Setup runner
        self.runner = Runner(
            app_name="hosting_orchestrator_a2a",
            agent=self.a2a_agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService()
        )
        
        # Setup A2A server
        self.agent_card = AgentCard(
            name="hosting_orchestrator",
            description="Multi-agent orchestrator coordinating Policy, Research, and Provider agents",
            url=os.getenv("ORCHESTRATOR_URL", "http://localhost:8080"),
            version="1.0.0",
            capabilities=AgentCapabilities(
                streaming=True,
                pushNotifications=False,
                stateTransitionHistory=True
            ),
            skills=[
                AgentSkill(
                    name="multi_agent_orchestration",
                    description="Routes queries to Policy, Research, and Provider agents in optimal sequence",
                    tags=["orchestration", "routing", "multi-agent"]
                ),
                AgentSkill(
                    name="compliance_validation",
                    description="Ensures compliance checks are performed before actions",
                    tags=["compliance", "policy", "validation"]
                ),
                AgentSkill(
                    name="research_execution",
                    description="Coordinates research and execution workflows",
                    tags=["research", "data", "execution"]
                )
            ]
        )
    
    async def _process_orchestration_task(self, task_input: str, tool_context: ToolContext) -> str:
        """Tool function that processes tasks through the orchestrator"""
        result = await self.orchestrator.process_request(
            user_query=task_input,
            session_id=tool_context.session.id if tool_context.session else None
        )
        
        if result["success"]:
            return result["response"]
        else:
            return f"Error: {result.get('error', 'Unknown error')}"
    
    def create_a2a_server(self):
        """Create and return the A2A Starlette application"""
        config = A2aAgentExecutorConfig()
        executor = A2aAgentExecutor(runner=self.runner, config=config)
        
        request_handler = DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore()
        )
        
        return A2AStarletteApplication(
            agent_card=self.agent_card,
            http_handler=request_handler
        )


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

async def example_usage():
    """Demonstrate different routing scenarios"""
    
    orchestrator = ADKMultiAgentOrchestrator()
    
    # Scenario 1: Compliance-first (Policy → Research → Provider)
    print("=== Scenario 1: Compliance Check Required ===")
    result1 = await orchestrator.process_request(
        "Check if we're compliant with GDPR, then research customer data handling procedures, "
        "and finally update our privacy policy document"
    )
    print(f"Response: {result1['response'][:500]}...")
    print(f"Agents involved: {result1['metadata']['agents_involved']}")
    
    # Scenario 2: Research-first (Research → Policy → Provider)
    print("\n=== Scenario 2: Data-Driven Decision ===")
    result2 = await orchestrator.process_request(
        "Analyze Q4 sales data, validate if we can offer discounts based on company policy, "
        "and execute the pricing updates"
    )
    print(f"Response: {result2['response'][:500]}...")
    print(f"Agents involved: {result2['metadata']['agents_involved']}")
    
    # Scenario 3: Direct execution (Research → Provider)
    print("\n=== Scenario 3: Direct Execution ===")
    result3 = await orchestrator.process_request(
        "Look up customer contact info and send them a welcome email"
    )
    print(f"Response: {result3['response'][:500]}...")
    print(f"Agents involved: {result3['metadata']['agents_involved']}")


if __name__ == "__main__":
    asyncio.run(example_usage())