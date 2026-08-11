import os
from enum import Enum
from dataclasses import dataclass
from typing import Any
import requests

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from .configs import settings
from agents.llm import GoogleGenAIChat, ITIBedrockChat


class LLMProvider(Enum):
    GEMINI = "gemini"
    GROQ = "groq"
    NVIDIA = "nvidia"
    OPENROUTER = "openrouter"
    ITI = "iti"


@dataclass(frozen=True)
class LLMConfig:
    provider: LLMProvider
    model: str
    temperature: float = 0.0


def create_llm(config: LLMConfig) -> BaseChatModel:
    if config.provider == LLMProvider.GEMINI:
        api_key = settings.google_api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return GoogleGenAIChat(
            model_name=config.model,
            temperature=config.temperature,
            api_key=api_key,
        )

    if config.provider == LLMProvider.GROQ:
        return ChatGroq(
            model=config.model,
            temperature=config.temperature,
            api_key=settings.groq_api_key,
        )

    if config.provider == LLMProvider.NVIDIA:
        return ChatNVIDIA(
            model=config.model,
            temperature=config.temperature,
            api_key=settings.nvidia_api_key,
        )

    if config.provider == LLMProvider.OPENROUTER:
        return ChatOpenAI(
            openai_api_base="https://openrouter.ai/api/v1",
            model=config.model,
            api_key=settings.openrouter_api_key,
            temperature=config.temperature,
        )

    if config.provider == LLMProvider.ITI:
        return ITIBedrockChat(
            model_name=config.model,
            temperature=config.temperature,
        )

    raise ValueError(f"Unsupported provider: {config.provider}")
