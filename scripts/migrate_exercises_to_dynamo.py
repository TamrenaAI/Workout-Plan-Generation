"""
One-off: migrates the exercises table from the legacy SQLite database
(data/tamreena.db) directly into the workout_exercises DynamoDB table.

This is the current source of truth for how the production `workout_exercises`
table was actually populated. The original Mongo->Dynamo migration script
(dc51ed2, deleted in 138a1d6 during Mongo removal since it imported
tools.mongo) is NOT what ran for real: the real cutover of exercise-catalog
data went straight from this service's legacy SQLite database, bypassing
Mongo entirely. Mongo was retired during the DynamoDB cutover and is no
longer in the picture — this script exists purely for reproducibility (e.g.
standing up a new environment from scratch), it does not need to be re-run
against the existing production table.

Run once per environment: python scripts/migrate_exercises_to_dynamo.py
"""

import sqlite3
import uuid

from config import DB_PATH
from tools.dynamo import get_exercises_table


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM exercises").fetchall()

    table = get_exercises_table()
    migrated = 0
    with table.batch_writer() as batch:
        for row in rows:
            doc = dict(row)
            doc.pop("id", None)
            doc = {k: v for k, v in doc.items() if v is not None}
            doc["exercise_id"] = str(uuid.uuid4())
            batch.put_item(Item=doc)
            migrated += 1
    print(f"Migrated {migrated} exercises from SQLite ({DB_PATH}) to DynamoDB table '{table.table_name}'.")


if __name__ == "__main__":
    main()
