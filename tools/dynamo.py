"""
Shared DynamoDB client — one boto3 resource, reused across every table
(mirrors tamreena-web/backend/app/db.py's get_resource()). Each
get_*_table() accessor is a thin Table() wrapper so call sites never
construct table names themselves.
"""

from typing import Optional

import boto3

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

_resource: Optional["boto3.resources.base.ServiceResource"] = None


def get_resource():
    global _resource
    if _resource is None:
        _resource = boto3.resource("dynamodb", region_name=AWS_REGION)
    return _resource


def get_plan_sessions_table():
    return get_resource().Table(PLAN_SESSIONS_TABLE_NAME)


def get_exercises_table():
    return get_resource().Table(EXERCISES_TABLE_NAME)


def get_inbody_scans_table():
    return get_resource().Table(INBODY_SCANS_TABLE_NAME)


def get_workout_feedback_table():
    return get_resource().Table(WORKOUT_FEEDBACK_TABLE_NAME)


def get_corrective_results_table():
    return get_resource().Table(CORRECTIVE_RESULTS_TABLE_NAME)


def get_progress_reports_table():
    return get_resource().Table(PROGRESS_REPORTS_TABLE_NAME)


def get_plan_adjustments_table():
    return get_resource().Table(PLAN_ADJUSTMENTS_TABLE_NAME)


def get_coach_messages_table():
    return get_resource().Table(COACH_MESSAGES_TABLE_NAME)
