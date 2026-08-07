"""
One-off setup script: creates all 8 workout-agent DynamoDB tables in the
target AWS account/region. Safe to re-run — skips any table that already
exists. Run from the repo root: python scripts/create_dynamo_tables.py
"""

import boto3
from botocore.exceptions import ClientError

from config import (
    AWS_REGION,
    COACH_MESSAGES_TABLE_NAME,
    CORRECTIVE_RESULTS_TABLE_NAME,
    EXERCISES_TABLE_NAME,
    INBODY_SCANS_TABLE_NAME,
    PLAN_ADJUSTMENTS_TABLE_NAME,
    PLAN_SESSIONS_TABLE_NAME,
    PROGRESS_REPORTS_TABLE_NAME,
    WORKOUT_FEEDBACK_TABLE_NAME,
)

def _create_if_missing(client, **kwargs) -> None:
    name = kwargs["TableName"]
    try:
        client.describe_table(TableName=name)
        print(f"Table '{name}' already exists — skipping.")
        return
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
    client.create_table(BillingMode="PAY_PER_REQUEST", **kwargs)
    print(f"Created table '{name}'.")


def main() -> None:
    # Constructed here (not at module scope) so importing this module never
    # attempts AWS credential resolution as a side effect.
    client = boto3.client("dynamodb", region_name=AWS_REGION)

    _create_if_missing(
        client,
        TableName=PLAN_SESSIONS_TABLE_NAME,
        KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "session_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
            {"AttributeName": "previous_session_id", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "previous-session-index",
                "KeySchema": [{"AttributeName": "previous_session_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )

    _create_if_missing(
        client,
        TableName=EXERCISES_TABLE_NAME,
        KeySchema=[{"AttributeName": "exercise_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "exercise_id", "AttributeType": "S"},
            {"AttributeName": "primary_muscle", "AttributeType": "S"},
            {"AttributeName": "movement_type", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "muscle-index",
                "KeySchema": [
                    {"AttributeName": "primary_muscle", "KeyType": "HASH"},
                    {"AttributeName": "movement_type", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )

    _create_if_missing(
        client,
        TableName=INBODY_SCANS_TABLE_NAME,
        KeySchema=[{"AttributeName": "scan_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "scan_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
            {"AttributeName": "session_id", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "session-index",
                "KeySchema": [{"AttributeName": "session_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )

    _create_if_missing(
        client,
        TableName=WORKOUT_FEEDBACK_TABLE_NAME,
        KeySchema=[{"AttributeName": "feedback_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "feedback_id", "AttributeType": "S"},
            {"AttributeName": "session_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "submitted_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "session-index",
                "KeySchema": [
                    {"AttributeName": "session_id", "KeyType": "HASH"},
                    {"AttributeName": "submitted_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "user-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "submitted_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )

    _create_if_missing(
        client,
        TableName=CORRECTIVE_RESULTS_TABLE_NAME,
        KeySchema=[{"AttributeName": "result_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "result_id", "AttributeType": "S"},
            {"AttributeName": "session_id", "AttributeType": "S"},
            {"AttributeName": "exercise_name", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "recorded_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "session-index",
                "KeySchema": [
                    {"AttributeName": "session_id", "KeyType": "HASH"},
                    {"AttributeName": "exercise_name", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "user-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "recorded_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )

    # new_session_id is the primary key (not a generated report_id) so the
    # table itself enforces one report per monthly review — mirrors the old
    # Mongo `db.progress_reports.create_index("new_session_id", unique=True)`.
    # A random report_id + non-unique GSI let a retried/double-submitted
    # review silently create a second report and made get_progress_report's
    # GSI query (Limit=1) return an arbitrary one of the two.
    _create_if_missing(
        client,
        TableName=PROGRESS_REPORTS_TABLE_NAME,
        KeySchema=[{"AttributeName": "new_session_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "new_session_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )

    _create_if_missing(
        client,
        TableName=PLAN_ADJUSTMENTS_TABLE_NAME,
        KeySchema=[{"AttributeName": "adjustment_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "adjustment_id", "AttributeType": "S"},
            {"AttributeName": "session_day_key", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "session-day-index",
                "KeySchema": [
                    {"AttributeName": "session_day_key", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )

    _create_if_missing(
        client,
        TableName=COACH_MESSAGES_TABLE_NAME,
        KeySchema=[{"AttributeName": "message_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "message_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )


if __name__ == "__main__":
    main()
