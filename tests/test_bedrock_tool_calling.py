import asyncio

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableBinding
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from agents.llm import ITIBedrockChat, get_llm


@tool
def get_weather(city: str) -> str:
    """Look up the current weather for a city."""
    return f"Sunny in {city}"


class _MockBedrockChat(ITIBedrockChat):
    """Mock ITIBedrockChat that replays a scripted sequence of responses
    without any network calls — each call to _generate/_agenerate consumes
    the next entry in `responses`."""

    responses: list[str] = []
    calls: list[dict] = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(kwargs)
        ai_text = self.responses[len(self.calls) - 1]
        message = self._to_ai_message(ai_text, bool(kwargs.get("tools")))
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def test_bind_tools_returns_runnable_binding_with_formatted_tools():
    llm = ITIBedrockChat()
    bound = llm.bind_tools([get_weather])

    assert isinstance(bound, RunnableBinding)
    assert bound.kwargs["tools"][0]["type"] == "function"
    assert bound.kwargs["tools"][0]["function"]["name"] == "get_weather"


def test_generate_parses_tool_call_envelope_when_tools_bound():
    mock = _MockBedrockChat(responses=['{"tool_calls": [{"name": "get_weather", "arguments": {"city": "Cairo"}}]}'])
    bound = mock.bind_tools([get_weather])

    result = bound.invoke([HumanMessage(content="What's the weather in Cairo?")])

    assert isinstance(result, AIMessage)
    assert result.tool_calls
    assert result.tool_calls[0]["name"] == "get_weather"
    assert result.tool_calls[0]["args"] == {"city": "Cairo"}
    assert result.content == ""


def test_generate_returns_plain_content_when_model_gives_final_answer():
    mock = _MockBedrockChat(responses=["It's sunny in Cairo today."])
    bound = mock.bind_tools([get_weather])

    result = bound.invoke([HumanMessage(content="What's the weather in Cairo?")])

    assert isinstance(result, AIMessage)
    assert not result.tool_calls
    assert result.content == "It's sunny in Cairo today."


def test_tool_call_json_ignored_when_no_tools_bound():
    # Without tools bound, a JSON-shaped answer is just content, never parsed
    # as a tool call — avoids misfiring on a plain-text response that happens
    # to look like JSON.
    mock = _MockBedrockChat(responses=['{"tool_calls": [{"name": "get_weather", "arguments": {}}]}'])

    result = mock.invoke([HumanMessage(content="hi")])

    assert isinstance(result, AIMessage)
    assert not result.tool_calls
    assert "tool_calls" in result.content


def test_tool_message_round_trips_through_build_payload():
    llm = ITIBedrockChat()
    messages = [
        HumanMessage(content="What's the weather in Cairo?"),
        AIMessage(content="", tool_calls=[{"name": "get_weather", "args": {"city": "Cairo"}, "id": "call_1", "type": "tool_call"}]),
        ToolMessage(content="Sunny in Cairo", name="get_weather", tool_call_id="call_1"),
    ]
    payload, _ = llm._build_payload(messages, tools=[{"type": "function", "function": {"name": "get_weather"}}])

    roles = [m["role"] for m in payload["messages"]]
    # Trailing entry is the anti-drift reminder appended whenever tools are
    # bound (see _build_payload) — not part of the original conversation.
    assert roles == ["user", "assistant", "user", "user"]
    assert "Sunny in Cairo" in payload["messages"][2]["content"]
    assert "tool_calls" in payload["messages"][1]["content"]
    assert "Reminder" in payload["messages"][3]["content"]


def test_create_react_agent_builds_without_bind_tools_error():
    """The actual regression this whole file guards against: before
    ITIBedrockChat implemented bind_tools, deepagents.create_deep_agent (built
    on langgraph's create_react_agent) raised NotImplementedError the moment
    any agent (supervisor, plan_adjuster, progress_analyst) was built, since
    BaseChatModel.bind_tools raises by default and none of those call sites
    ever get a chance to make a network request before hitting it."""
    mock = _MockBedrockChat(responses=["Cairo is sunny."])
    graph = create_react_agent(model=mock, tools=[get_weather])

    result = graph.invoke({"messages": [HumanMessage(content="What's the weather in Cairo?")]})
    assert result["messages"][-1].content == "Cairo is sunny."


def test_full_tool_call_round_trip_through_react_agent():
    mock = _MockBedrockChat(
        responses=[
            '{"tool_calls": [{"name": "get_weather", "arguments": {"city": "Cairo"}}]}',
            "It's sunny in Cairo.",
        ]
    )
    graph = create_react_agent(model=mock, tools=[get_weather])

    result = graph.invoke({"messages": [HumanMessage(content="What's the weather in Cairo?")]})

    final = result["messages"][-1]
    assert final.content == "It's sunny in Cairo."
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].content == "Sunny in Cairo"
