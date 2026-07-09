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
    """sub_agents: typically [EXERCISE_RECOMMENDER, PLAN_ASSEMBLER] from agents/subagents.py."""
    return create_deep_agent(
        model=get_llm(temperature=0.3),
        tools=SUPERVISOR_TOOLS,
        subagents=sub_agents,
        system_prompt=load_prompt("supervisor"),
        name="tamreena-supervisor",
    )
