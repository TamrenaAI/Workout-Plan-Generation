"""
Plan Adjuster — a standalone agent (not a Supervisor sub-agent) invoked
directly by the API route when post-workout feedback flags an exercise as
too_easy, too_hard, or painful. See prompts/plan_adjuster.md.

Unlike the Exercise Recommender / Plan Assembler, this never runs as part
of the main plan-generation pipeline — it runs later, on demand, once a
user has actually trained a session and reported back.
"""

from deepagents import create_deep_agent

from agents.llm import get_llm
from config import load_prompt
from tools.memory import (
    read_plan_memory,
    read_workout_feedback,
    record_exercise_adjustment,
    write_plan_memory,
)

PLAN_ADJUSTER_TOOLS = [
    read_plan_memory,
    read_workout_feedback,
    record_exercise_adjustment,
    write_plan_memory,
]


def build_plan_adjuster():
    graph = create_deep_agent(
        model=get_llm(temperature=0.3),
        tools=PLAN_ADJUSTER_TOOLS,
        system_prompt=load_prompt("plan_adjuster"),
        name="tamreena-plan-adjuster",
    )
    return graph
