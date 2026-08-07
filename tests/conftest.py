"""
Shared pytest fixtures. `dynamo_tables` (autouse) gives every test an
isolated in-memory DynamoDB instance via moto, so no test ever touches the
real database this app connects to in dev/prod.
"""

import boto3
import pytest
from moto import mock_aws

import tools.dynamo as dynamo_module
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


@pytest.fixture(autouse=True)
def dynamo_tables(monkeypatch):
    # Standard moto hardening: stub fake credentials so that if mock_aws()
    # ever fails to intercept a call for some reason, boto3 has no real
    # ambient credentials (e.g. a developer's ~/.aws/credentials) to fall
    # back to and reach the actual AWS account with.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")

    with mock_aws():
        dynamo_module._resource = None
        resource = boto3.resource("dynamodb", region_name=AWS_REGION)

        resource.create_table(
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
            BillingMode="PAY_PER_REQUEST",
        )

        resource.create_table(
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
            BillingMode="PAY_PER_REQUEST",
        )

        resource.create_table(
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
            BillingMode="PAY_PER_REQUEST",
        )

        resource.create_table(
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
            BillingMode="PAY_PER_REQUEST",
        )

        resource.create_table(
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
            BillingMode="PAY_PER_REQUEST",
        )

        resource.create_table(
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
            BillingMode="PAY_PER_REQUEST",
        )

        resource.create_table(
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
            BillingMode="PAY_PER_REQUEST",
        )

        resource.create_table(
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
            BillingMode="PAY_PER_REQUEST",
        )

        yield resource
        dynamo_module._resource = None
