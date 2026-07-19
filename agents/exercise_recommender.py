"""
Exercise Recommender sub-agent definition, dispatched by the Supervisor via
deepagents' task() tool.

Called once per muscle_group ID with a different task prompt each time
(chest, back, legs_a, legs_b, ...), not once per agent identity.
See prompts/exercise_recommender.md.
"""

from agents.llm import get_llm
from config import load_prompt
from tools.database import search_exercise_db
from tools.memory import mark_step_done, read_plan_memory, write_plan_memory
from tools.rag import search_rag

EXERCISE_RECOMMENDER = {
    "model": get_llm(temperature=0.3),
    "tools": [read_plan_memory, write_plan_memory, search_rag, search_exercise_db, mark_step_done],
    "system_prompt": load_prompt("exercise_recommender"),
    "name": "exercise-recommender",
    "description": (
        "Recommends 3-5 exercises with full prescription (sets/reps/rest/RPE) for a single "
        "muscle_group ID, using the intensity table matching the plan's paradigm, RAG guidance, "
        "and the exercise DB. Marks its own completion via mark_step_done."
    ),
}
