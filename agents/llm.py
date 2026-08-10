"""
Shared LLM client factory.

All agents (supervisor, exercise-recommender, plan-assembler) and the InBody
VLM pipeline go through the same get_llm() factory. The Coach Agent
(agents/coach.py) uses get_coach_llm() instead, so its chat responses come
from the same ITI Bedrock model the nutrition service uses, not OpenAI.
"""

import random
import time
from typing import Any, List, Optional

import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI

from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    SBG_API_KEY,
    SBG_MODEL_ID,
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


# HTTP status codes that warrant an automatic retry (mirrors the nutrition
# service's app/core/llm.py::ITIBedrockChat — same proxy, same failure modes).
_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
_MAX_RETRIES = 4
_BASE_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 16.0
_JITTER_S = 0.5


def _backoff(attempt: int) -> float:
    wait = min(_BASE_BACKOFF_S * (2**attempt), _MAX_BACKOFF_S)
    return wait + random.uniform(0, _JITTER_S)


class ITIBedrockChat(BaseChatModel):
    """LangChain-compatible chat model that calls the ITI Bedrock proxy —
    the same proxy/model the nutrition service's meal-composition agents use
    (see Nutrition-Plan-Generation/app/core/llm.py). Ported here so the Coach
    Agent's chat responses come from the same model, not OpenAI."""

    model_id: str = SBG_MODEL_ID
    base_url: str = "http://apiaccess.iti.net.eg/api/v1"
    timeout: int = 90
    temperature: float = 0.4
    max_retries: int = _MAX_RETRIES

    @property
    def _llm_type(self) -> str:
        return "iti_bedrock_chat"

    def _build_payload(self, messages: List[BaseMessage], **kwargs: Any) -> tuple[dict, dict]:
        system_prompt = "You are a helpful assistant."
        formatted_messages: list[dict] = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_prompt = msg.content
            elif isinstance(msg, HumanMessage):
                formatted_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted_messages.append({"role": "assistant", "content": msg.content})

        if not formatted_messages:
            formatted_messages.append({"role": "user", "content": "Hello"})

        payload = {
            "model_id": self.model_id,
            "messages": formatted_messages,
            "system_prompt": system_prompt,
            "max_tokens": kwargs.get("max_tokens", 8192),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        if not SBG_API_KEY:
            raise ValueError("SBG_API_KEY is not set. Please add it to your .env file.")

        headers = {"Authorization": f"Bearer {SBG_API_KEY}", "Content-Type": "application/json"}
        return payload, headers

    @staticmethod
    def _parse_response(response: requests.Response) -> str:
        response_json = response.json()
        return (
            response_json.get("output_text")
            or response_json.get("text")
            or response_json.get("response")
            or response_json.get("message")
            or str(response_json)
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload, headers = self._build_payload(messages, **kwargs)
        url = f"{self.base_url}/student/chat"
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)

                if response.status_code == 200:
                    ai_text = self._parse_response(response)
                    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=ai_text))])

                if response.status_code in _RETRYABLE_STATUSES:
                    last_exc = requests.exceptions.HTTPError(
                        f"{response.status_code} retryable error", response=response
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(_backoff(attempt))
                    continue

                response.raise_for_status()

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    time.sleep(_backoff(attempt))

        raise last_exc or RuntimeError("ITI Bedrock request failed with unknown error")


def get_coach_llm(temperature: float = 0.4) -> ITIBedrockChat:
    """Build the Coach Agent's LLM client — ITI Bedrock, same model the
    nutrition agent uses, not OpenAI."""
    return ITIBedrockChat(model_id=SBG_MODEL_ID, temperature=temperature)
