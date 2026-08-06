"""
One-off data migration: copies every document in the current Mongo
`exercises` collection into the new DynamoDB `workout_exercises` table,
generating a fresh exercise_id per item (Dynamo has no auto-id; Mongo's
ObjectId is not carried over). Run once per environment, after
scripts/create_dynamo_tables.py, before cutting the app over to Dynamo
reads: python scripts/migrate_exercises_to_dynamo.py
"""

import uuid

from tools.dynamo import get_exercises_table
from tools.mongo import get_db


def main() -> None:
    src = list(get_db().exercises.find({}))
    table = get_exercises_table()
    migrated = 0
    with table.batch_writer() as batch:
        for doc in src:
            doc.pop("_id", None)
            doc["exercise_id"] = str(uuid.uuid4())
            batch.put_item(Item=doc)
            migrated += 1
    print(f"Migrated {migrated} exercises from Mongo to DynamoDB table '{table.table_name}'.")


if __name__ == "__main__":
    main()
