from enum import Enum
from dataclasses import dataclass
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import ChatOpenAI
from .configs import settings

import requests
from typing import Any

from pydantic import Field

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import (
    ChatGeneration,
    ChatResult,
)



class ITIBedrockChat(BaseChatModel):
    """LangChain wrapper for the ITI Bedrock proxy."""

    model_id: str = Field(
        default="us.meta.llama3-3-70b-instruct-v1:0"
    )

    base_url: str = Field(
        default="http://apiaccess.iti.net.eg/api/v1"
    )

    timeout: int = Field(default=60)

    temperature: float = Field(default=0.0)

    @property
    def _llm_type(self) -> str:
        return "iti_bedrock"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:

        system_prompt = "You are a helpful assistant."
        formatted_messages = []

        for msg in messages:

            if isinstance(msg, SystemMessage):
                system_prompt = msg.content

            elif isinstance(msg, HumanMessage):
                formatted_messages.append(
                    {
                        "role": "user",
                        "content": msg.content,
                    }
                )

            elif isinstance(msg, AIMessage):
                formatted_messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content,
                    }
                )

        if not formatted_messages:
            formatted_messages.append(
                {
                    "role": "user",
                    "content": "Hello",
                }
            )

        payload = {
            "model_id": self.model_id,
            "messages": formatted_messages,
            "system_prompt": system_prompt,
            "max_tokens": kwargs.get("max_tokens", 8192),
            "temperature": kwargs.get(
                "temperature",
                self.temperature,
            ),
        }

        api_key = settings.iti_api_key

        if not api_key:
            raise ValueError(
                "ITI_API_KEY is not set."
            )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            f"{self.base_url}/student/chat",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        ai_text = (
            data.get("output_text")
            or data.get("text")
            or data.get("response")
            or data.get("message")
            or str(data)
        )

        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content=ai_text,
                    )
                )
            ]
        )










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
        return ChatGoogleGenerativeAI(
            model=config.model,
            temperature=config.temperature,
            api_key = settings.google_api_key
        )

    if config.provider == LLMProvider.GROQ:
        return ChatGroq(
            model=config.model,
            temperature=config.temperature,
            api_key=settings.groq_api_key
        )
    
    if config.provider == LLMProvider.NVIDIA:
        return ChatNVIDIA(
            model=config.model,
            temperature=config.temperature,
            api_key=settings.nvidia_api_key
        )
    
    if config.provider == LLMProvider.OPENROUTER:
        return ChatOpenAI(
            openai_api_base="https://openrouter.ai/api/v1",
            model=config.model,
            api_key= settings.openrouter_api_key,
            temperature=config.temperature,
        )
    
    if config.provider == LLMProvider.ITI:
        return ITIBedrockChat(
            model_id=config.model,
            temperature=config.temperature,
        )

    raise ValueError(
        f"Unsupported provider: {config.provider}"
    )

