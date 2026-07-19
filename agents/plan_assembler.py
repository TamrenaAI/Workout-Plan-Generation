"""
Plan Assembler sub-agent definition, dispatched by the Supervisor via
deepagents' task() tool once every muscle group is confirmed complete.
See prompts/plan_assembler.md.
"""

from agents.llm import get_llm
from config import load_prompt
from tools.memory import (
    read_plan_memory,
    validate_plan_completeness,
    validate_session_duration,
    write_plan_memory,
)

PLAN_ASSEMBLER = {
    "model": get_llm(temperature=0.3),
    "tools": [read_plan_memory, write_plan_memory, validate_plan_completeness, validate_session_duration],
    "system_prompt": load_prompt("plan_assembler"),
    "name": "plan-assembler",
    "description": (
        "Arranges all completed muscle-group prescriptions into a full weekly training schedule, "
        "following split and recovery rules. Refuses to run if muscle groups are missing, and "
        "enforces the session-duration budget from the DAY MAP."
    ),
}
