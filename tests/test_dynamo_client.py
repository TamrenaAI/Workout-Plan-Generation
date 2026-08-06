"""tests/test_dynamo_client.py"""
import tools.dynamo as dynamo


def test_get_resource_is_memoized():
    r1 = dynamo.get_resource()
    r2 = dynamo.get_resource()
    assert r1 is r2


def test_all_table_getters_return_tables_with_expected_names():
    from config import (
        COACH_MESSAGES_TABLE_NAME, CORRECTIVE_RESULTS_TABLE_NAME, EXERCISES_TABLE_NAME,
        INBODY_SCANS_TABLE_NAME, PLAN_ADJUSTMENTS_TABLE_NAME, PLAN_SESSIONS_TABLE_NAME,
        PROGRESS_REPORTS_TABLE_NAME, WORKOUT_FEEDBACK_TABLE_NAME,
    )
    assert dynamo.get_plan_sessions_table().table_name == PLAN_SESSIONS_TABLE_NAME
    assert dynamo.get_exercises_table().table_name == EXERCISES_TABLE_NAME
    assert dynamo.get_inbody_scans_table().table_name == INBODY_SCANS_TABLE_NAME
    assert dynamo.get_workout_feedback_table().table_name == WORKOUT_FEEDBACK_TABLE_NAME
    assert dynamo.get_corrective_results_table().table_name == CORRECTIVE_RESULTS_TABLE_NAME
    assert dynamo.get_progress_reports_table().table_name == PROGRESS_REPORTS_TABLE_NAME
    assert dynamo.get_plan_adjustments_table().table_name == PLAN_ADJUSTMENTS_TABLE_NAME
    assert dynamo.get_coach_messages_table().table_name == COACH_MESSAGES_TABLE_NAME
