from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)
from google.adk.agents import Agent, LlmAgent
# 1. Create RemoteA2AAgent instances as SUB-AGENTS
    policy_agent = RemoteA2aAgent(
        name="PolicyAgent",
        description="Checks health insurance policy details for coverage, co-pays, and deductibles.",
        agent_card=(
            f"http://localhost:{policy_agent_port}{AGENT_CARD_WELL_KNOWN_PATH}"
        ),
    )

    research_agent = RemoteA2aAgent(
        name="ResearchAgent",
        description="Researches medical conditions, symptoms, and treatments.",
        agent_card=(
            f"http://localhost:{research_agent_port}{AGENT_CARD_WELL_KNOWN_PATH}"
        ),
    )

    provider_agent = RemoteA2aAgent(
        name="ProviderAgent",
        description="Finds in-network healthcare providers and facilities.",
        agent_card=(
            f"http:/localhost:{provider_agent_port}{AGENT_CARD_WELL_KNOWN_PATH}"
        ),
    )

    print(f"\t✅ Created remote sub-agents")

    # 2. Create Healthcare Orchestrator with SUB-AGENTS
    healthcare_orchestrator = LlmAgent(
        name="HealthcareOrchestrator",
        description="A personal concierge for Healthcare Information, customized to your policy.",
        model=LiteLlm("bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        # CRITICAL: Use sub_agents, not tools!
        sub_agents=[policy_agent, research_agent, provider_agent],
        instruction="""You are a concierge for healthcare services.