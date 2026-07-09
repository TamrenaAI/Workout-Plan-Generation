"""
Sub-agent definitions dispatched by the Supervisor via deepagents' task() tool.

One agent definition per role — the Exercise Recommender is called once per
muscle_group ID with a different task prompt each time (chest, back, legs_a,
legs_b, ...), not once per agent identity. See prompts/exercise_recommender.md.
"""

from agents.llm import get_llm
from config import load_prompt
from tools.database import search_exercise_db
from tools.memory import (
    read_plan_memory,
    validate_plan_completeness,
    validate_session_duration,
    write_plan_memory,
    mark_step_done,
)
from tools.rag import search_rag

_llm = get_llm(temperature=0.3)

EXERCISE_RECOMMENDER = {
    "model": _llm,
    "tools": [read_plan_memory, write_plan_memory, search_rag, search_exercise_db, mark_step_done],
    "system_prompt": load_prompt("exercise_recommender"),
    "name": "exercise-recommender",
    "description": (
        "Recommends 3-5 exercises with full prescription (sets/reps/rest/RPE) for a single "
        "muscle_group ID, using the intensity table matching the plan's paradigm, RAG guidance, "
        "and the exercise DB. Marks its own completion via mark_step_done."
    ),
}

PLAN_ASSEMBLER = {
    "model": _llm,
    "tools": [read_plan_memory, write_plan_memory, validate_plan_completeness, validate_session_duration],
    "system_prompt": load_prompt("plan_assembler"),
    "name": "plan-assembler",
    "description": (
        "Arranges all completed muscle-group prescriptions into a full weekly training schedule, "
        "following split and recovery rules. Refuses to run if muscle groups are missing, and "
        "enforces the session-duration budget from the DAY MAP."
    ),
}
