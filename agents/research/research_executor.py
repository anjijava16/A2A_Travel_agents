import os

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools import google_search
from google.adk.models.lite_llm import LiteLlm


PORT = 8888
HOST = "localhost"

import litellm


def bedrock_claude_completion(prompt):
    response = litellm.completion(
        model="bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        prompt=prompt,
        max_tokens=1024,
    )
    return response["text"]


from duckduckgo_search import DDGS

def duckduckgo_search_tool(query: str) -> str:
    """Search DuckDuckGo and return top results."""
    
    results_text = []

    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=5)

        for r in results:
            results_text.append(
                f"Title: {r['title']}\n"
                f"URL: {r['href']}\n"
                f"Snippet: {r['body']}\n"
            )

    return "\n---\n".join(results_text)


def main() -> None:
    # Create the Agent
    root_agent = LlmAgent(
        #model=LiteLlm("bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"), # Not supported tools 
        #model=LiteLlm("bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        model=LiteLlm("gpt-4o-mini"),
        name="HealthResearchAgent",
        #tools=[duckduckgo_search_tool],
        description="Provides healthcare information about symptoms, health conditions, treatments, and procedures using up-to-date web resources.",
        instruction="You are a healthcare research agent tasked with providing information about health conditions. Use the google_search tool to find information on the web about options, symptoms, treatments, and procedures. Cite your sources in your responses. Output all of the information you find.",
    )
    from a2a.types import (
        AgentCapabilities,
        AgentCard,
        AgentSkill,
    )
    skill = AgentSkill(
        id="insurance_coverage",
        name="Insurance coverage",
        description="Provides information about insurance coverage options and details.",
        tags=["insurance", "coverage"],
        examples=["What does my policy cover?", "Are mental health services included?"],
    )

    agent_card = AgentCard(
        name="InsurancePolicyCoverageAgent",
        description="Provides information about insurance policy coverage options and details.",
        url=f"http://{HOST}:{PORT}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )
    

    # Make the agent A2A-compatible
    a2a_app = to_a2a(root_agent,agent_card=agent_card, host=HOST, port=PORT)
    print("Running Health Research Agent")
    uvicorn.run(a2a_app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
