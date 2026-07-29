"""
Shared LLM client factory.

All agents (supervisor, exercise-recommender, plan-assembler) and the InBody
VLM pipeline go through the same get_llm() factory.
"""

from typing import Any, List, Optional
from langchain_openai import ChatOpenAI

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


def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    """Build a fresh ChatOpenAI client using the configured OpenAI key and model.
    Provides fallback defaults so offline build-time tasks (such as pre-downloading
    embedding models) do not fail when env vars are unpopulated.
    """
    model_name = OPENAI_MODEL or AZURE_OPENAI_DEPLOYMENT_NAME or OPENROUTER_MODEL or "gpt-4o-mini"
    api_key = OPENAI_API_KEY or AZURE_OPENAI_API_KEY or OPENROUTER_API_KEY or "sk-dummy-key-for-build"

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )
