import asyncio
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

import config
from agents.llm import (
    ITIBedrockChat,
    _clean_and_parse_json,
    _get_schema_instructions,
    _inject_instructions,
    _validate_schema,
    get_llm,
)
from tools.inbody import InBodyValidation
from tools.rag.models import GoalQueryFilter, PrinciplesQueryFilter


class SampleModel(BaseModel):
    name: str
    count: int = 1
    tags: list[str] = Field(default_factory=list)


class _MockBedrockChat(ITIBedrockChat):
    """Mock ITIBedrockChat returning pre-programmed text without network calls."""

    response_text: str = ""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response_text))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response_text))])


def test_clean_and_parse_raw_json():
    text = '{"name": "Bench Press", "count": 3, "tags": ["chest", "push"]}'
    res = _clean_and_parse_json(text)
    assert res == {"name": "Bench Press", "count": 3, "tags": ["chest", "push"]}


def test_clean_and_parse_markdown_fence():
    text = """Here is the extracted information:
```json
{
  "name": "Squat",
  "count": 5,
  "tags": ["legs", "compound"]
}
```
Hope this helps!"""
    res = _clean_and_parse_json(text)
    assert res == {"name": "Squat", "count": 5, "tags": ["legs", "compound"]}


def test_clean_and_parse_trailing_commas():
    text = '{"name": "Deadlift", "count": 1, "tags": ["back", "pull",],}'
    res = _clean_and_parse_json(text)
    assert res == {"name": "Deadlift", "count": 1, "tags": ["back", "pull"]}


def test_clean_and_parse_invalid_json_raises():
    with pytest.raises(ValueError, match="Could not parse LLM output as JSON"):
        _clean_and_parse_json("Not a JSON object at all")


def test_schema_instructions_contains_json_schema():
    instructions = _get_schema_instructions(SampleModel)
    assert "JSON Schema" in instructions
    assert '"name"' in instructions
    assert '"count"' in instructions


def test_inject_instructions_appends_to_messages():
    instructions = "\n\nOutput ONLY raw JSON."
    msgs = _inject_instructions("Extract user info", instructions)
    assert len(msgs) == 1
    assert "Extract user info" in msgs[0].content
    assert instructions in msgs[0].content


def test_with_structured_output_sync_pydantic():
    mock_llm = _MockBedrockChat(
        response_text='```json\n{"muscle": ["chest"], "goals": ["hypertrophy"]}\n```'
    )
    structured_llm = mock_llm.with_structured_output(GoalQueryFilter)
    result = structured_llm.invoke("Give me chest hypertrophy filters")

    assert isinstance(result, GoalQueryFilter)
    assert result.muscle == ["chest"]
    assert result.goals == ["hypertrophy"]


def test_with_structured_output_async_pydantic():
    async def _run():
        mock_llm = _MockBedrockChat(
            response_text='{"is_inbody_scan": true, "confidence": "high", "issue": null}'
        )
        structured_llm = mock_llm.with_structured_output(InBodyValidation)
        return await structured_llm.ainvoke("Check InBody scan")

    result = asyncio.run(_run())
    assert isinstance(result, InBodyValidation)
    assert result.is_inbody_scan is True
    assert result.confidence == "high"
    assert result.issue is None


def test_with_structured_output_in_lcel_chain():
    mock_llm = _MockBedrockChat(
        response_text='{"topic": ["volume"], "applies_to": ["hypertrophy"]}'
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Extract training principles query filters."),
        ("human", "{query}"),
    ])
    chain = prompt | mock_llm.with_structured_output(PrinciplesQueryFilter)
    result = chain.invoke({"query": "What volume should I use for hypertrophy?"})

    assert isinstance(result, PrinciplesQueryFilter)
    assert result.topic == ["volume"]
    assert result.applies_to == ["hypertrophy"]


def test_with_structured_output_include_raw():
    mock_llm = _MockBedrockChat(response_text='{"name": "Lat Pulldown", "count": 4}')
    structured_llm = mock_llm.with_structured_output(SampleModel, include_raw=True)
    res = structured_llm.invoke("test")

    assert "raw" in res
    assert "parsed" in res
    assert isinstance(res["parsed"], SampleModel)
    assert res["parsed"].name == "Lat Pulldown"
    assert res["parsing_error"] is None


def test_get_llm_returns_itibedrockchat():
    llm = get_llm(temperature=0.2)
    assert isinstance(llm, ITIBedrockChat)
    assert llm.temperature == 0.2
    assert llm.model_id in ["gemma-4-31b-it", config.GEMINI_MODEL, "us.meta.llama3-3-70b-instruct-v1:0"]

