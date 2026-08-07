"""
search_exercise_db must never dump an entire muscle group's raw catalog into
a tool result — some muscle groups have 150-330 exercises, and a flat,
uncapped result reliably overruns a sub-agent's ability to reason over it in
one step (observed live: the chest exercise-recommender agent stalling/
looping instead of completing). These tests lock in the per-movement-type
cap and the exclusion of untyped (stretch/mobility) docs from "all" queries.
"""

import uuid

from tools.database import search_exercise_db
from tools.dynamo import get_exercises_table


def _insert_chest_exercises(count_by_type):
    # movement_type is a GSI range key (String) — DynamoDB rejects a NULL
    # value there, so "untyped" (stretch/mobility) docs are seeded WITHOUT
    # the attribute at all. An item missing a GSI key attribute simply
    # isn't projected into that index, which is exactly the real-world
    # shape search_exercise_db's "all" query relies on to exclude them.
    table = get_exercises_table()
    i = 0
    for movement_type, count in count_by_type.items():
        for _ in range(count):
            item = {
                "exercise_id": str(uuid.uuid4()),
                "name": f"chest exercise {i}",
                "primary_muscle": "chest",
                "equipment": "barbell",
                "difficulty": "intermediate",
            }
            if movement_type is not None:
                item["movement_type"] = movement_type
            table.put_item(Item=item)
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
