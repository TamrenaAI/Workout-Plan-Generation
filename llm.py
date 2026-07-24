"""
ITIBedrockChat — LangChain BaseChatModel wrapper for the ITI Bedrock proxy API.
The API key is loaded from settings (SBG_API_KEY in .env).
"""

import requests
from typing import Any, List, Optional

# pyrefly: ignore [missing-import]
from langchain_core.language_models.chat_models import BaseChatModel

# pyrefly: ignore [missing-import]
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage

# pyrefly: ignore [missing-import]
from langchain_core.outputs import ChatResult, ChatGeneration

from app.core.config import settings


class ITIBedrockChat(BaseChatModel):
    """LangChain-compatible chat model that calls the ITI Bedrock proxy."""

    model_id: str = "us.meta.llama3-3-70b-instruct-v1:0"
    base_url: str = "http://apiaccess.iti.net.eg/api/v1"
    timeout: int = 60
    temperature: float = 0.9

    @property
    def _llm_type(self) -> str:
        return "iti_bedrock_chat"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        system_prompt = "You are a helpful assistant."
        formatted_messages: list[dict] = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_prompt = msg.content
            elif isinstance(msg, HumanMessage):
                formatted_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted_messages.append({"role": "assistant", "content": msg.content})

        # Guard: the proxy returns 502 on empty message lists
        if not formatted_messages:
            formatted_messages.append({"role": "user", "content": "Hello"})

        payload = {
            "model_id": self.model_id,
            "messages": formatted_messages,
            "system_prompt": system_prompt,
            "max_tokens": kwargs.get("max_tokens", 8192),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        api_key = settings.sbg_api_key
        if not api_key:
            raise ValueError("SBG_API_KEY is not set. Please add it to your .env file.")

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

        if response.status_code != 200:
            print(f"❌ Server returned status {response.status_code}")
            print(f"📋 Response body: {response.text}")
            response.raise_for_status()  # raises with status code in message

        response.raise_for_status()

        response_json = response.json()
        ai_text = (
            response_json.get("output_text")   # ITI Bedrock proxy primary key
            or response_json.get("text")
            or response_json.get("response")
            or response_json.get("message")
            or str(response_json)
        )

        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=ai_text))]
        )
