"""
Shared LLM client factory.

All agents (supervisor, exercise-recommender, plan-assembler, coach) and
the InBody/RAG pipelines use the ITI Bedrock proxy API with the same models
used by the nutrition plan service.
"""

import asyncio
import json
import random
import re
import time
from typing import Any, Dict, List, Optional, Union

import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompt_values import PromptValue
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel

from config import SBG_API_KEY, SBG_MODEL_ID

# HTTP status codes that warrant an automatic retry (mirrors the nutrition
# service's app/core/llm.py::ITIBedrockChat — same proxy, same failure modes).
_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
_MAX_RETRIES: int = 5
_BASE_BACKOFF_S: float = 1.0
_MAX_BACKOFF_S: float = 30.0
_JITTER_S: float = 0.5


def _backoff(attempt: int) -> float:
    wait = min(_BASE_BACKOFF_S * (2**attempt), _MAX_BACKOFF_S)
    return wait + random.uniform(0, _JITTER_S)


def _clean_and_parse_json(text: str) -> Any:
    """Extract and parse JSON from an LLM response string."""
    text = text.strip()

    # 1. Strip markdown code fence if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        candidate = match.group(1).strip()
    else:
        # 2. Look for outermost { ... } or [ ... ]
        start_brace = text.find("{")
        start_bracket = text.find("[")
        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
            end_brace = text.rfind("}")
            candidate = text[start_brace : end_brace + 1] if end_brace != -1 else text
        elif start_bracket != -1:
            end_bracket = text.rfind("]")
            candidate = text[start_bracket : end_bracket + 1] if end_bracket != -1 else text
        else:
            candidate = text

    # Try direct parse
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 3. Clean common issues: trailing commas before } or ]
    fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse LLM output as JSON: {text}") from exc


def _validate_schema(data: Any, schema: Any) -> Any:
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        if hasattr(schema, "model_validate"):
            return schema.model_validate(data)
        elif hasattr(schema, "parse_obj"):
            return schema.parse_obj(data)
        return schema(**data)
    return data


def _get_schema_instructions(schema: Any) -> str:
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        if hasattr(schema, "model_json_schema"):
            schema_dict = schema.model_json_schema()
        elif hasattr(schema, "schema"):
            schema_dict = schema.schema()
        else:
            schema_dict = {}
        schema_json = json.dumps(schema_dict, indent=2)
    elif isinstance(schema, dict):
        schema_json = json.dumps(schema, indent=2)
    else:
        schema_json = str(schema)

    return (
        f"\n\nYou MUST respond with ONLY a valid JSON object conforming strictly to this JSON Schema:\n"
        f"```json\n{schema_json}\n```\n"
        f"Output ONLY the raw JSON object and nothing else. Do not include any markdown fences or explanations outside the JSON."
    )


def _inject_instructions(input_val: Any, instructions: str) -> list[BaseMessage]:
    if isinstance(input_val, PromptValue):
        msgs = input_val.to_messages()
    elif isinstance(input_val, list):
        msgs = list(input_val)
    elif isinstance(input_val, str):
        return [HumanMessage(content=input_val + instructions)]
    elif isinstance(input_val, BaseMessage):
        msgs = [input_val]
    else:
        return [HumanMessage(content=str(input_val) + instructions)]

    out_msgs: list[BaseMessage] = []
    for m in msgs:
        if isinstance(m, HumanMessage):
            if isinstance(m.content, str):
                out_msgs.append(HumanMessage(content=m.content))
            elif isinstance(m.content, list):
                out_msgs.append(HumanMessage(content=m.content))
            else:
                out_msgs.append(m)
        else:
            out_msgs.append(m)

    if out_msgs and isinstance(out_msgs[-1], HumanMessage) and isinstance(out_msgs[-1].content, str):
        out_msgs[-1] = HumanMessage(content=out_msgs[-1].content + instructions)
    else:
        out_msgs.append(HumanMessage(content=instructions.strip()))

    return out_msgs


class _BedrockStructuredOutputRunnable(Runnable):
    """Wraps ITIBedrockChat to provide structured output via prompt formatting and JSON parsing."""

    def __init__(self, llm: "ITIBedrockChat", schema: Any, include_raw: bool = False, **kwargs: Any):
        self.llm = llm
        self.schema = schema
        self.include_raw = include_raw
        self.kwargs = kwargs
        self.instructions = _get_schema_instructions(schema)

    def invoke(self, input: Any, config: Optional[RunnableConfig] = None) -> Any:
        messages = _inject_instructions(input, self.instructions)
        res = self.llm.invoke(messages, config=config, **self.kwargs)
        raw_text = res.content if isinstance(res, BaseMessage) else str(res)
        try:
            parsed_data = _clean_and_parse_json(raw_text)
            validated = _validate_schema(parsed_data, self.schema)
            if self.include_raw:
                return {"raw": res, "parsed": validated, "parsing_error": None}
            return validated
        except Exception as exc:
            if self.include_raw:
                return {"raw": res, "parsed": None, "parsing_error": exc}
            raise

    async def ainvoke(self, input: Any, config: Optional[RunnableConfig] = None) -> Any:
        messages = _inject_instructions(input, self.instructions)
        res = await self.llm.ainvoke(messages, config=config, **self.kwargs)
        raw_text = res.content if isinstance(res, BaseMessage) else str(res)
        try:
            parsed_data = _clean_and_parse_json(raw_text)
            validated = _validate_schema(parsed_data, self.schema)
            if self.include_raw:
                return {"raw": res, "parsed": validated, "parsing_error": None}
            return validated
        except Exception as exc:
            if self.include_raw:
                return {"raw": res, "parsed": None, "parsing_error": exc}
            raise


class ITIBedrockChat(BaseChatModel):
    """LangChain-compatible chat model that calls the ITI Bedrock proxy —
    the same proxy/model the nutrition service's meal-composition agents use
    (see Nutrition-Plan-Generation/app/core/llm.py)."""

    model_id: str = SBG_MODEL_ID
    base_url: str = "http://apiaccess.iti.net.eg/api/v1"
    timeout: int = 300
    temperature: float = 0.3
    max_retries: int = _MAX_RETRIES

    @property
    def _llm_type(self) -> str:
        return "iti_bedrock_chat"

    def _build_payload(self, messages: List[BaseMessage], **kwargs: Any) -> tuple[dict, dict]:
        system_prompt = "You are a helpful assistant."
        formatted_messages: list[dict] = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_prompt = msg.content if isinstance(msg.content, str) else str(msg.content)
            elif isinstance(msg, HumanMessage):
                if isinstance(msg.content, str):
                    formatted_messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg.content, list):
                    text_parts = []
                    for item in msg.content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            elif item.get("type") == "image_url":
                                text_parts.append("[Image attachment provided]")
                            else:
                                text_parts.append(str(item))
                        else:
                            text_parts.append(str(item))
                    formatted_messages.append({"role": "user", "content": "\n".join(text_parts)})
                else:
                    formatted_messages.append({"role": "user", "content": str(msg.content)})
            elif isinstance(msg, AIMessage):
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                formatted_messages.append({"role": "assistant", "content": content})

        if not formatted_messages:
            formatted_messages.append({"role": "user", "content": "Hello"})

        payload = {
            "model_id": self.model_id,
            "messages": formatted_messages,
            "system_prompt": system_prompt,
            "max_tokens": kwargs.get("max_tokens", 8192),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        api_key = SBG_API_KEY or "dummy-key-for-build"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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

    async def _agenerate(
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
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(url, headers=headers, json=payload, timeout=self.timeout),
                )

                if response.status_code == 200:
                    ai_text = self._parse_response(response)
                    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=ai_text))])

                if response.status_code in _RETRYABLE_STATUSES:
                    last_exc = requests.exceptions.HTTPError(
                        f"{response.status_code} retryable error", response=response
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(_backoff(attempt))
                    continue

                response.raise_for_status()

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(_backoff(attempt))

        raise last_exc or RuntimeError("ITI Bedrock async request failed with unknown error")

    def with_structured_output(
        self,
        schema: Any,
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Runnable:
        """Returns a Runnable that prompts for structured JSON and validates the response."""
        return _BedrockStructuredOutputRunnable(self, schema, include_raw=include_raw, **kwargs)


def get_llm(temperature: float = 0.3) -> ITIBedrockChat:
    """Build a fresh ITIBedrockChat client using the configured Bedrock key and model
    (matching Nutrition-Plan-Generation).
    """
    model_name = SBG_MODEL_ID or "us.meta.llama3-3-70b-instruct-v1:0"
    return ITIBedrockChat(model_id=model_name, temperature=temperature, timeout=90)


def get_coach_llm(temperature: float = 0.4) -> ITIBedrockChat:
    """Build the Coach Agent's LLM client — ITI Bedrock."""
    model_name = SBG_MODEL_ID or "us.meta.llama3-3-70b-instruct-v1:0"
    return ITIBedrockChat(model_id=model_name, temperature=temperature, timeout=90)

