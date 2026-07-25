"""
Shared LLM client factory.

All agents (supervisor, exercise-recommender, plan-assembler) and the InBody
VLM pipeline go through the same get_llm() factory, currently wired to the
direct OpenAI API. ITIBedrockChat (below, adapted from the reference
implementation in the repo-root llm.py) is text-only and doesn't support
with_structured_output, so it can't serve tools/inbody.py's vision +
structured-output extraction — kept here commented out, not deleted, in
case a text-only agent path wants it later.
"""

from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
import requests

from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL
)

# def get_llm(temperature: float = 0.3) -> ChatOpenAI:
#     """Build a fresh ChatOpenAI client using the direct OpenAI key.

#     max_retries=6 (not the langchain-openai default of 2): a full plan
#     generation dispatches many sequential/occasionally-concurrent sub-agent
#     calls against a single org-wide TPM quota, and the accumulating
#     conversation context per turn means later muscle groups (chest onward)
#     can legitimately brush the ceiling even on a normal run — observed live
#     via scripts/debug_full_pipeline.py: openai.RateLimitError 429 with
#     "try again in 797ms" exhausting 2 retries and killing the whole run.
#     The 429 clears in well under a second each time; the fix is riding out
#     the burst, not backing off for longer.
#     """
#     return ChatOpenAI(
#         model=OPENROUTER_MODEL,
#         api_key=OPENROUTER_API_KEY,
#         base_url="https://openrouter.ai/api/v1",
#         temperature=temperature,
#         timeout=60,
#         max_retries=6,
#     )


def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    """Build a fresh ChatOpenAI client using the direct OpenAI key.

    max_retries=2: a full plan
    generation dispatches many sequential/occasionally-concurrent sub-agent
    calls against a single org-wide TPM quota, and the accumulating
    conversation context per turn means later muscle groups (chest onward)
    can legitimately brush the ceiling even on a normal run — observed live
    via scripts/debug_full_pipeline.py: openai.RateLimitError 429 with
    "try again in 797ms" exhausting 2 retries and killing the whole run.
    The 429 clears in well under a second each time; the fix is riding out
    the burst, not backing off for longer.
    """
    return ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )

# def get_llm(temperature: float = 0.3) -> ChatOpenAI:
#     """Build a fresh ChatOpenAI client pointed at the Azure deployment.

#     temperature=0.3 for agent reasoning (supervisor / sub-agents).
#     temperature=0 is used by the InBody extraction pipeline, where
#     deterministic reads matter more than variety.
#     """
#     return ChatOpenAI(
#         model=AZURE_OPENAI_DEPLOYMENT_NAME,
#         base_url=AZURE_OPENAI_ENDPOINT,
#         api_key=AZURE_OPENAI_API_KEY,
#         temperature=temperature,
#         timeout=60,
#         max_retries=2,
#         stream_usage=True,
#     )


if __name__ == "__main__":
    # Manual smoke test: `python agents/llm.py` — confirms the configured
    # LLM backend is reachable and responds to an ordinary question.
    llm = get_llm()
    question = "What is the capital of France?"
    response = llm.invoke([HumanMessage(content=question)])
    print(f"Q: {question}")
    print(f"A: {response.content}")
