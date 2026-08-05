"""
Coach Agent -- a standalone agent (not a Supervisor sub-agent) invoked
directly by api/routes/coach.py on every chat turn. See prompts/coach.md.

Unlike other agents in this repo (e.g. agents/plan_adjuster.py's static
PLAN_ADJUSTER_TOOLS list), this agent's tools are built fresh per request
by build_coach_tools() rather than defined as a module-level list: the
tools must be closed over a server-verified user_id and a BFF-supplied
nutrition snapshot rather than accepting them as LLM-controllable
arguments, so the model can never select whose data gets read -- the same
reasoning behind auth/ownership.py's user_owns_session check elsewhere in
this codebase.
"""

from langchain_core.tools import tool
from deepagents import create_deep_agent

from agents.llm import get_llm
from auth.ownership import list_sessions_for_user
from config import load_prompt
from tools.memory import read_weekly_schedule


def build_coach_tools(user_id: str, nutrition_snapshot: str | None):
    @tool
    def get_workout_history() -> str:
        """Returns the user's most recent workout plan (weekly schedule), or
        a message saying none exists yet. Call this for any question about
        training, exercises, sets/reps, or the workout split."""
        sessions = list_sessions_for_user(user_id)
        ready = next((s for s in sessions if s["status"] == "ready"), None)
        if ready is None:
            return "(no workout plan yet)"
        schedule = read_weekly_schedule(ready["session_id"])
        return schedule or "(no workout plan yet)"

    @tool
    def get_nutrition_plan() -> str:
        """Returns the user's most recently generated nutrition plan
        (macros, calories, meals), or a message saying none exists yet.
        Call this for any question about food, diet, meals, macros, or
        calories."""
        return nutrition_snapshot or "(no nutrition plan yet)"

    return [get_workout_history, get_nutrition_plan]


def build_coach_agent(user_id: str, nutrition_snapshot: str | None = None):
    graph = create_deep_agent(
        model=get_llm(temperature=0.4),
        tools=build_coach_tools(user_id, nutrition_snapshot),
        system_prompt=load_prompt("coach"),
        name="tamreena-coach",
    )
    return graph
