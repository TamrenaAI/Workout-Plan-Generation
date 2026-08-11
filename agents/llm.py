"""
Shared LLM client factory.

All agents (supervisor, exercise-recommender, plan-assembler, coach) and
the InBody/RAG pipelines use the Google GenAI / Gemini client configured via .env.
"""

import asyncio
import json
import os
import random
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Union

from google import genai
from google.genai import types
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompt_values import PromptValue
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel

import config

# Retry configuration for rate limiting / transient API issues
_MAX_RETRIES: int = 8
_BASE_BACKOFF_S: float = 1.5
_MAX_BACKOFF_S: float = 30.0
_JITTER_S: float = 0.5


def _backoff(attempt: int) -> float:
    wait = min(_BASE_BACKOFF_S * (2**attempt), _MAX_BACKOFF_S)
    return wait + random.uniform(0, _JITTER_S)


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if an exception is caused by Gemini/Google GenAI rate limiting (HTTP 429 / RESOURCE_EXHAUSTED)."""
    exc_str = str(exc).lower()
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code == 429:
        return True
    indicators = [
        "429",
        "resource_exhausted",
        "resource has been exhausted",
        "quota exceeded",
        "rate limit",
        "too many requests",
        "rate_limit_exceeded",
        "exceeded your current quota",
    ]
    return any(ind in exc_str for ind in indicators)


def _get_retry_wait_time(attempt: int, exc: Optional[Exception]) -> float:
    """Determine wait duration: 62s for 15 RPM quota limit window reset, exponential backoff for others."""
    if exc and _is_rate_limit_error(exc):
        # 60s + 2-4s jitter to ensure 15 requests/minute quota bucket completely clears
        return 62.0 + random.uniform(0.5, 3.0)
    return _backoff(attempt)


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


def _parse_tool_calls(ai_text: str) -> Optional[List[Dict[str, Any]]]:
    """Detects the `{"tool_calls": [...]}` envelope the model is instructed to
    emit and converts it into LangChain's ToolCall dict shape."""
    try:
        data = _clean_and_parse_json(ai_text)
    except ValueError:
        return None

    if not isinstance(data, dict) or not isinstance(data.get("tool_calls"), list):
        return None

    calls: List[Dict[str, Any]] = []
    for tc in data["tool_calls"]:
        if isinstance(tc, dict) and isinstance(tc.get("name"), str):
            args = tc.get("arguments", tc.get("args", {}))
            calls.append(
                {
                    "name": tc["name"],
                    "args": args if isinstance(args, dict) else {},
                    "id": f"call_{uuid.uuid4().hex[:16]}",
                    "type": "tool_call",
                }
            )
    return calls or None


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


class _GoogleStructuredOutputRunnable(Runnable):
    """Wraps GoogleGenAIChat to provide structured output via prompt formatting and JSON parsing."""

    def __init__(self, llm: "GoogleGenAIChat", schema: Any, include_raw: bool = False, **kwargs: Any):
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


class GoogleGenAIChat(BaseChatModel):
    """LangChain-compatible chat model that calls Google GenAI / Gemini."""

    model_name: str = "gemma-4-31b-it"
    api_key: Optional[str] = None
    temperature: float = 0.3
    max_retries: int = _MAX_RETRIES
    timeout: int = 3600

    @property
    def model_id(self) -> str:
        return self.model_name

    @property
    def _llm_type(self) -> str:
        return "google_genai_chat"

    def _get_client(self) -> genai.Client:
        key = self.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or config.GEMINI_API_KEY
        if not key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is not set. Please add it to your .env file.")
        return genai.Client(api_key=key)

    def _format_contents(self, messages: List[BaseMessage], **kwargs: Any) -> tuple[str, list[types.Content]]:
        system_instruction = "You are a helpful fitness and workout assistant."
        contents: list[types.Content] = []

        tools = kwargs.get("tools")
        tool_instructions = ""
        if tools:
            tool_instructions = (
                "\n\nYou have access to the following tools:\n"
                f"```json\n{json.dumps(tools, indent=2)}\n```\n"
                "To call a tool, respond with ONLY this JSON and nothing else "
                '(no markdown fences, no extra text): '
                '{"tool_calls": [{"name": "<tool_name>", "arguments": {<args as an object>}}]}\n'
                "To give a final answer instead of calling a tool, respond with plain text, "
                "not JSON.\n\n"
                "IMPORTANT: once you start a multi-step task, do not stop to explain your "
                "reasoning in plain text between steps — after a tool result comes back, "
                "immediately continue with the next required tool call in the exact JSON "
                "format above. Only respond with plain text when the ENTIRE task is fully "
                "complete and no further tool calls are needed."
            )

        for msg in messages:
            if isinstance(msg, SystemMessage):
                content_str = msg.content if isinstance(msg.content, str) else str(msg.content)
                system_instruction = content_str
            elif isinstance(msg, HumanMessage):
                if isinstance(msg.content, str):
                    text = msg.content
                elif isinstance(msg.content, list):
                    text = " ".join(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in msg.content
                    )
                else:
                    text = str(msg.content)
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=text)]))
            elif isinstance(msg, AIMessage):
                if msg.tool_calls:
                    content_str = json.dumps(
                        {
                            "tool_calls": [
                                {"name": tc["name"], "arguments": tc.get("args", {})}
                                for tc in msg.tool_calls
                            ]
                        }
                    )
                else:
                    content_str = msg.content if isinstance(msg.content, str) else str(msg.content)
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=content_str)]))
            elif isinstance(msg, ToolMessage):
                result_text = msg.content if isinstance(msg.content, str) else str(msg.content)
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=f"[Result of tool '{msg.name}']: {result_text}")],
                    )
                )

        if tool_instructions:
            system_instruction += tool_instructions
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=(
                                "Reminder: if this task isn't fully complete yet, respond with ONLY "
                                'the {"tool_calls": [...]} JSON now — do not explain your reasoning '
                                "first. Plain text is only for a fully finished task."
                            )
                        )
                    ],
                )
            )

        if not contents:
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text="Hello")]))

        return system_instruction, contents

    def _build_payload(self, messages: List[BaseMessage], **kwargs: Any) -> tuple[dict, dict]:
        """Convert messages to payload dictionary for inspection / compatibility."""
        system_instruction, contents = self._format_contents(messages, **kwargs)
        payload_messages = []
        for c in contents:
            role = "user" if c.role == "user" else "assistant"
            part_text = " ".join(p.text for p in c.parts if getattr(p, "text", None))
            payload_messages.append({"role": role, "content": part_text})
        return {"messages": payload_messages, "system_prompt": system_instruction, "model_id": self.model_name}, {}

    @staticmethod
    def _to_ai_message(ai_text: str, tools_bound: bool) -> AIMessage:
        tool_calls = _parse_tool_calls(ai_text) if tools_bound else None
        if tool_calls:
            return AIMessage(content="", tool_calls=tool_calls)
        return AIMessage(content=ai_text)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        client = self._get_client()
        system_instruction, contents = self._format_contents(messages, **kwargs)
        tools_bound = bool(kwargs.get("tools"))
        temp = kwargs.get("temperature", self.temperature)
        if tools_bound:
            temp = min(temp, 0.15)

        generate_config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temp,
            max_output_tokens=kwargs.get("max_tokens", 8192),
            stop_sequences=stop,
        )

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=generate_config,
                )
                ai_text = response.text or ""
                message = self._to_ai_message(ai_text, tools_bound)
                return ChatResult(generations=[ChatGeneration(message=message)])
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    wait_seconds = _get_retry_wait_time(attempt, exc)
                    if _is_rate_limit_error(exc):
                        print(
                            f"[GoogleGenAIChat] Gemini rate limit reached (15 RPM quota). "
                            f"Waiting {wait_seconds:.1f}s for quota bucket reset before retry {attempt + 2}/{self.max_retries}..."
                        )
                    time.sleep(wait_seconds)

        raise last_exc or RuntimeError(f"Google GenAI request failed after {self.max_retries} attempts")

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._generate(messages, stop=stop, run_manager=run_manager, **kwargs),
        )

    def with_structured_output(
        self,
        schema: Any,
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Runnable:
        """Returns a Runnable that prompts for structured JSON and validates the response."""
        return _GoogleStructuredOutputRunnable(self, schema, include_raw=include_raw, **kwargs)

    def bind_tools(
        self,
        tools: Sequence[Union[Dict[str, Any], type, "BaseTool", Any]],
        *,
        tool_choice: Optional[str] = None,
        **kwargs: Any,
    ) -> Runnable:
        """Prompt-injects tool schemas and parses response tool calls for ReAct compatibility."""
        formatted_tools = [convert_to_openai_tool(t) for t in tools]
        return self.bind(tools=formatted_tools, **kwargs)


# Alias for backward compatibility across existing references/tests
ITIBedrockChat = GoogleGenAIChat


def get_llm(temperature: float = 0.3) -> GoogleGenAIChat:
    """Build a fresh GoogleGenAIChat client using the centrally configured model in .env."""
    model_name = os.getenv("GEMINI_MODEL") or os.getenv("MODEL_NAME") or config.GEMINI_MODEL or "gemma-4-31b-it"
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or config.GEMINI_API_KEY
    return GoogleGenAIChat(model_name=model_name, api_key=api_key, temperature=temperature)


def get_coach_llm(temperature: float = 0.4) -> GoogleGenAIChat:
    """Build the Coach Agent's LLM client using the centrally configured model in .env."""
    model_name = os.getenv("GEMINI_MODEL") or os.getenv("MODEL_NAME") or config.GEMINI_MODEL or "gemma-4-31b-it"
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or config.GEMINI_API_KEY
    return GoogleGenAIChat(model_name=model_name, api_key=api_key, temperature=temperature)
