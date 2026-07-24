"""
Exercise database — MongoDB `exercises` collection (per
tamrena_architecture_2.md Section 8). `search_exercise_db` is the only
contract the agents depend on — its filter shape and return format are
unchanged from the SQLite version, only the backing store moved.
"""

from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from langchain_core.tools import tool

from tools.mongo import get_db


def get_exercise_by_id(exercise_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(exercise_id)
    except InvalidId:
        return None
    doc = get_db().exercises.find_one({"_id": oid})
    if not doc:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


# Per-movement-type cap on a single "all" query — some muscle groups have
# 150-330 exercises total (e.g. arms, legs, chest), and dumping every one as
# text into a sub-agent's tool result reliably overruns its ability to
# reason over the output in one step, which manifests as the agent stalling
# / retrying without ever completing (see agents/supervisor.py's raised
# recursion_limit). Capping per movement_type (rather than one flat cap on
# the combined list) keeps compound/isolation/unilateral all represented
# instead of one category crowding out the others.
RESULTS_PER_MOVEMENT_TYPE = 6
PROJECTION = {"name": 1, "equipment": 1, "difficulty": 1, "movement_type": 1, "contraindications": 1}


@tool
def search_exercise_db(
    muscle_group: str,
    movement_type: str = "all",
    exclude_contraindication: Optional[str] = None,
) -> str:
    """
    Query the exercise database for exercises matching a muscle group.
    movement_type: compound | isolation | unilateral | all
    exclude_contraindication: body part to avoid (e.g. 'knee_pain')
    """
    if movement_type == "all":
        # Untyped docs (movement_type absent/null) are stretches/mobility
        # drills, not prescribable strength exercises — only surfaced when a
        # specific movement_type is requested that happens to match them.
        docs = []
        for mt in ("compound", "isolation", "unilateral"):
            docs.extend(list(get_db().exercises.find(
                {"primary_muscle": muscle_group, "movement_type": mt}, PROJECTION,
            ).limit(RESULTS_PER_MOVEMENT_TYPE)))
    else:
        docs = list(get_db().exercises.find(
            {"primary_muscle": muscle_group, "movement_type": movement_type}, PROJECTION,
        ).limit(RESULTS_PER_MOVEMENT_TYPE * 3))

    if exclude_contraindication:
        docs = [d for d in docs if not (d.get("contraindications") and exclude_contraindication in d["contraindications"])]

    if not docs:
        return f"No exercises found for [{muscle_group}] [{movement_type}]"

    lines = [
        f"  • {d['name']} ({d.get('equipment') or '?'}, {d.get('difficulty') or '?'}, {d.get('movement_type') or '?'})"
        for d in docs
    ]
    return f"DB results — muscle: [{muscle_group}] | type: [{movement_type}]\n" + "\n".join(lines)
