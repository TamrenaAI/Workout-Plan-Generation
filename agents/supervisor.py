"""
Supervisor agent — orchestrates the full plan-generation pipeline.
See prompts/supervisor.md for the full system prompt and tamrena_architecture_2.md
Section 4b for the design rationale.
"""

from deepagents import create_deep_agent

from agents.llm import get_llm
from config import load_prompt
from tools.inbody import parse_inbody_text
from tools.memory import get_plan_progress, init_plan_progress, read_plan_memory, write_plan_memory

SUPERVISOR_TOOLS = [
    parse_inbody_text,
    read_plan_memory,
    write_plan_memory,
    init_plan_progress,
    get_plan_progress,
]


def build_supervisor(sub_agents):
    """sub_agents: typically [EXERCISE_RECOMMENDER, PLAN_ASSEMBLER] from
    agents/exercise_recommender.py and agents/plan_assembler.py.

    recursion_limit is raised from LangGraph's default of 25 — each muscle-group
    dispatch cycle (decide to dispatch -> task() -> check progress -> decide next)
    costs several graph super-steps on its own, so a realistic 5-6 muscle-group
    plan (or 6 with legs_a/legs_b) plus the assembler and setup steps comfortably
    exceeds the default before the run ever gets to finish."""
    graph = create_deep_agent(
        model=get_llm(temperature=0.3),
        tools=SUPERVISOR_TOOLS,
        subagents=sub_agents,
        system_prompt=load_prompt("supervisor"),
        name="tamreena-supervisor",
    )
    return graph.with_config(recursion_limit=150)
