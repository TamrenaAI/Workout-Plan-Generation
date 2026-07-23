"""
Progress Analyst — single-shot agent that narrates a month's deterministically
computed summary (pipeline/monthly_progress.py). Never recomputes or restates
the numbers itself; see prompts/progress_analyst.md.

Unlike the Exercise Recommender / Plan Assembler, this is not a Supervisor
sub-agent and doesn't run as part of ordinary plan generation — it's
dispatched once, ahead of a monthly-review Supervisor run, from
api/routes/plan.py's monthly-review handler.
"""

from deepagents import create_deep_agent

from agents.llm import get_llm
from config import load_prompt
from tools.memory import read_plan_memory, write_plan_memory

PROGRESS_ANALYST_TOOLS = [
    read_plan_memory,
    write_plan_memory,
]


def build_progress_analyst():
    graph = create_deep_agent(
        model=get_llm(temperature=0.3),
        tools=PROGRESS_ANALYST_TOOLS,
        system_prompt=load_prompt("progress_analyst"),
        name="tamreena-progress-analyst",
    )
    return graph
