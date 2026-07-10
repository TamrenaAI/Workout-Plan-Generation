"""
Translates deepagents' astream_events() output into human-readable progress
events for the frontend's live "which agent is working" display
(processing.js), replacing the old fixed-timer fake ticker.

Nested sub-agent invocations DO propagate through astream_events — deepagents
forwards the parent run's callbacks/config into the nested subagent.invoke()
call (see deepagents.middleware.subagents.task(), which relies on langgraph's
ensure_config to merge ambient parent config, callbacks included). So this
sees not just "the Supervisor dispatched task()" but the exercise-recommender's
own internal tool calls (search_rag, search_exercise_db, write_plan_memory,
mark_step_done, ...) as they happen inside that dispatch, in real time.

This relies on dispatch actually being sequential — see prompts/supervisor.md's
"call task() for exactly ONE muscle_group ID per turn" rule. The "current
agent" is tracked as a simple stack (push on sub-agent chain start, pop on
chain end); that's only correct if sub-agent runs never overlap. If that rule
is ever violated, events from two concurrent sub-agents would incorrectly
appear to belong to whichever agent is on top of the stack at that moment.
"""

import re

from services import live_progress

AGENT_DISPLAY_NAMES = {
    "exercise-recommender": "Exercise Recommender",
    "plan-assembler": "Plan Assembler",
}
KNOWN_SUBAGENT_GRAPH_NAMES = set(AGENT_DISPLAY_NAMES)

MUSCLE_LABELS = {
    "chest": "Chest",
    "back": "Back",
    "shoulders": "Shoulders",
    "arms": "Arms",
    "legs_a": "Legs (Day A)",
    "legs_b": "Legs (Day B)",
    "legs": "Legs",
}

TOOL_START_LABELS = {
    "parse_inbody_text": "Reading InBody analysis",
    "read_plan_memory": "Reading plan memory",
    "write_plan_memory": "Writing to plan memory",
    "init_plan_progress": "Initializing progress tracker",
    "get_plan_progress": "Checking dispatch progress",
    "search_rag": "Searching training knowledge base",
    "search_exercise_db": "Searching exercise database",
    "mark_step_done": "Marking muscle group complete",
    "validate_plan_completeness": "Validating plan completeness",
    "validate_session_duration": "Validating session duration budget",
}

TOOL_END_LABELS = {
    "search_rag": "Training knowledge retrieved",
    "search_exercise_db": "Exercise matches found",
    "write_plan_memory": "Saved to plan memory",
    "mark_step_done": "Muscle group marked complete",
}

# prompts/supervisor.md mandates "MUSCLE_GROUP: {id}" as the literal first line of every
# task() description so this can be tracked reliably; the looser pattern is a fallback for
# whenever the model doesn't comply with that formatting exactly.
_MUSCLE_ID_RE = re.compile(r"MUSCLE_GROUP:\s*(\S+)|Muscle Group ID:\s*(\S+)", re.IGNORECASE)


def _muscle_label(muscle_id: str) -> str:
    return MUSCLE_LABELS.get(muscle_id, muscle_id)


async def run_and_stream(supervisor, user_message: str, session_id: str) -> str:
    """Runs the Supervisor graph via astream_events, publishing a live progress
    event for every meaningful step. Returns the Supervisor's final synthesized
    reply — equivalent to the old `result["messages"][-1].content` from the
    blocking `.invoke()` path, just captured from within the same event stream
    instead of a second pass. Exceptions propagate to the caller — this
    function only narrates, it doesn't decide how failures get reported."""
    active_stack = ["Supervisor"]
    pending_label = None
    final_message = ""

    async for event in supervisor.astream_events(
        {"messages": [{"role": "user", "content": user_message}]},
        version="v2",
        config={"recursion_limit": 150},
    ):
        kind = event.get("event")
        name = event.get("name", "")
        current_agent = active_stack[-1]

        if kind == "on_chat_model_end":
            # Only the top-level Supervisor's own turns count as candidates for
            # the final reply — a nested sub-agent's last turn is its own
            # internal synthesis, not what gets returned to the user.
            if len(active_stack) == 1:
                output = event.get("data", {}).get("output")
                content = getattr(output, "content", None)
                if content:
                    final_message = content
            continue

        if kind == "on_chat_model_start":
            await live_progress.publish(session_id, {
                "type": "progress", "agent": current_agent, "label": "Thinking...",
            })

        elif kind == "on_tool_start":
            tool_input = event.get("data", {}).get("input") or {}

            if name == "task":
                subagent_type = tool_input.get("subagent_type", "")
                description = tool_input.get("description", "") or ""
                muscle_match = _MUSCLE_ID_RE.search(description)
                muscle_id = (muscle_match.group(1) or muscle_match.group(2)) if muscle_match else None
                display = AGENT_DISPLAY_NAMES.get(subagent_type, subagent_type or "Sub-agent")
                pending_label = f"{display} ({_muscle_label(muscle_id)})" if muscle_id else display
                await live_progress.publish(session_id, {
                    "type": "progress", "agent": current_agent, "label": f"Dispatching {pending_label}...",
                })
            else:
                label = TOOL_START_LABELS.get(name, f"Running {name}")
                await live_progress.publish(session_id, {
                    "type": "progress", "agent": current_agent, "label": label,
                })

        elif kind == "on_tool_end":
            if name != "task":
                label = TOOL_END_LABELS.get(name)
                if label:
                    await live_progress.publish(session_id, {
                        "type": "progress", "agent": current_agent, "label": label,
                    })

        elif kind == "on_chain_start" and name in KNOWN_SUBAGENT_GRAPH_NAMES:
            label = pending_label or AGENT_DISPLAY_NAMES.get(name, name)
            pending_label = None
            active_stack.append(label)
            await live_progress.publish(session_id, {
                "type": "progress", "agent": label, "label": "Starting...",
            })

        elif kind == "on_chain_end" and name in KNOWN_SUBAGENT_GRAPH_NAMES:
            if len(active_stack) > 1:
                finished = active_stack.pop()
                await live_progress.publish(session_id, {
                    "type": "progress", "agent": finished, "label": "Finished",
                })

    return final_message
