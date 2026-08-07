"""
Exercise database — DynamoDB `workout_exercises` table (per
tamrena_architecture_2.md Section 8). `search_exercise_db` is the only
contract the agents depend on — its filter shape and return format are
unchanged, only the backing store moved.
"""

from typing import Optional

from langchain_core.tools import tool

from tools.dynamo import get_exercises_table


def get_exercise_by_id(exercise_id: str) -> Optional[dict]:
    resp = get_exercises_table().get_item(Key={"exercise_id": exercise_id})
    doc = resp.get("Item")
    if not doc:
        return None
    doc["id"] = doc["exercise_id"]
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
PROJECTION_EXPR = "#nm, equipment, difficulty, movement_type, contraindications"
PROJECTION_NAMES = {"#nm": "name"}


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
    table = get_exercises_table()
    if movement_type == "all":
        docs = []
        for mt in ("compound", "isolation", "unilateral"):
            resp = table.query(
                IndexName="muscle-index",
                KeyConditionExpression="primary_muscle = :m AND movement_type = :mt",
                ExpressionAttributeValues={":m": muscle_group, ":mt": mt},
                ProjectionExpression=PROJECTION_EXPR,
                ExpressionAttributeNames=PROJECTION_NAMES,
                Limit=RESULTS_PER_MOVEMENT_TYPE,
            )
            docs.extend(resp["Items"])
    else:
        resp = table.query(
            IndexName="muscle-index",
            KeyConditionExpression="primary_muscle = :m AND movement_type = :mt",
            ExpressionAttributeValues={":m": muscle_group, ":mt": movement_type},
            ProjectionExpression=PROJECTION_EXPR,
            ExpressionAttributeNames=PROJECTION_NAMES,
            Limit=RESULTS_PER_MOVEMENT_TYPE * 3,
        )
        docs = resp["Items"]

    if exclude_contraindication:
        docs = [d for d in docs if not (d.get("contraindications") and exclude_contraindication in d["contraindications"])]

    if not docs:
        return f"No exercises found for [{muscle_group}] [{movement_type}]"

    lines = [
        f"  • {d['name']} ({d.get('equipment') or '?'}, {d.get('difficulty') or '?'}, {d.get('movement_type') or '?'})"
        for d in docs
    ]
    return f"DB results — muscle: [{muscle_group}] | type: [{movement_type}]\n" + "\n".join(lines)
