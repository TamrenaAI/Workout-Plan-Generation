"""
Shared LLM client factory.

All agents (supervisor, exercise-recommender, plan-assembler) and the InBody
VLM pipeline go through Azure OpenAI via the same OpenAI-compatible endpoint.
`ChatOpenAI` with `base_url` pointed at the Azure AI Foundry endpoint works
directly here (the endpoint already exposes an `/openai/v1` compatible
surface) — no need for the separate `AzureChatOpenAI` class.
"""

from langchain_openai import ChatOpenAI

from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)


# def get_llm(temperature: float = 0.3) -> ChatOpenAI:
#     """Build a fresh ChatOpenAI client pointed at the Azure deployment.

#     temperature=0.3 for agent reasoning (supervisor / sub-agents).
#     temperature=0 is used by the InBody extraction pipeline, where
#     deterministic reads matter more than variety.
#     """
#     return ChatOpenAI(
#         model=OPENAI_MODEL,
#         api_key=OPENAI_API_KEY,
#         temperature=temperature,
#         timeout=60,
#         max_retries=2
#     )

def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    """Build a fresh ChatOpenAI client pointed at the Azure deployment.

    temperature=0.3 for agent reasoning (supervisor / sub-agents).
    temperature=0 is used by the InBody extraction pipeline, where
    deterministic reads matter more than variety.
    """
    return ChatOpenAI(
        model=AZURE_OPENAI_DEPLOYMENT_NAME,
        base_url=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )
