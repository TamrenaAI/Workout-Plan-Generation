"""
search_exercise_db must never dump an entire muscle group's raw catalog into
a tool result — some muscle groups have 150-330 exercises, and a flat,
uncapped result reliably overruns a sub-agent's ability to reason over it in
one step (observed live: the chest exercise-recommender agent stalling/
looping instead of completing). These tests lock in the per-movement-type
cap and the exclusion of untyped (stretch/mobility) docs from "all" queries.
"""

from tools.database import search_exercise_db
from tools.mongo import get_db


def _insert_chest_exercises(count_by_type):
    db = get_db()
    i = 0
    for movement_type, count in count_by_type.items():
        for _ in range(count):
            db.exercises.insert_one({
                "name": f"chest exercise {i}",
                "primary_muscle": "chest",
                "movement_type": movement_type,
                "equipment": "barbell",
                "difficulty": "intermediate",
            })
            i += 1


def test_all_query_caps_results_per_movement_type():
    _insert_chest_exercises({"compound": 92, "isolation": 20, "unilateral": 32, None: 19})

    result = search_exercise_db.invoke({"muscle_group": "chest", "movement_type": "all"})

    lines = [line for line in result.splitlines() if line.strip().startswith("•")]
    assert len(lines) <= 18


def test_all_query_excludes_untyped_stretch_entries():
    _insert_chest_exercises({None: 5})

    result = search_exercise_db.invoke({"muscle_group": "chest", "movement_type": "all"})

    assert "No exercises found" in result


def test_specific_movement_type_query_is_also_capped():
    _insert_chest_exercises({"compound": 92})

    result = search_exercise_db.invoke({"muscle_group": "chest", "movement_type": "compound"})

    lines = [line for line in result.splitlines() if line.strip().startswith("•")]
    assert len(lines) <= 18
