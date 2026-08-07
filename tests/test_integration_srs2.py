"""
Automated Integration Tests for Tamrena-AI Microservices Integration (srs2.md)
"""

import uuid

from fastapi.testclient import TestClient
from api.main import app
from auth.tokens import create_access_token

client = TestClient(app)


def test_inbody_onboarding_pipeline():
    payload = {
        "user_id": "usr_test_984",
        "onboarding_survey": {
            "fitness_goal": "hypertrophy",
            "experience_level": "intermediate",
            "available_equipment": ["barbell", "dumbbells", "cable_machine"],
            "days_per_week": 4,
            "session_duration_minutes": 60,
            "medical_disclaimers": ["mild_lower_back_tightness"]
        },
        "inbody_data": {
            "scan_date": "2026-07-01T00:00:00Z",
            "weight_kg": 82.5,
            "skeletal_muscle_mass_kg": 38.2,
            "body_fat_mass_kg": 15.1,
            "body_fat_percentage": 18.3,
            "visceral_fat_level": 6,
            "basal_metabolic_rate_kcal": 1820.0
        }
    }

    # Test POST /inbody/parse
    response = client.post("/inbody/parse", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["user_id"] == "usr_test_984"

    # Test GET /inbody/{user_id}/latest
    get_res = client.get("/inbody/usr_test_984/latest")
    assert get_res.status_code == 200
    assert get_res.json()["inbody"]["weight_kg"] == 82.5


def test_workout_generation_pipeline():
    payload = {
        "user_id": "usr_test_984",
        "onboarding_survey": {
            "fitness_goal": "hypertrophy",
            "experience_level": "intermediate",
            "available_equipment": ["barbell", "dumbbells"],
            "days_per_week": 4,
            "session_duration_minutes": 60,
            "medical_disclaimers": []
        },
        "pain_locations": ["lower_back"]
    }

    # Test POST /workout/generate
    response = client.post("/workout/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["split_type"] == "Upper / Lower Split"
    session_id = data["session_id"]

    # Test GET /workout/{session_id}
    get_res = client.get(f"/workout/{session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["user_id"] == "usr_test_984"


def test_nutrition_plan_generation():
    payload = {
        "survey": {
            "user_id": "usr_test_984",
            "dietary_preference": "high_protein",
            "allergies": ["peanuts"],
            "disliked_foods": ["mushrooms"],
            "meals_per_day": 3,
            "target_goal": "recomposition"
        },
        "bmr_kcal": 1820.0,
        "weight_kg": 82.5
    }

    # Test POST /nutrition/generate
    response = client.post("/nutrition/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "usr_test_984"
    assert "breakfast" in data["daily_meals"]
    assert "lunch" in data["daily_meals"]
    assert "dinner" in data["daily_meals"]

    # Test GET /nutrition/{user_id}
    get_res = client.get("/nutrition/usr_test_984")
    assert get_res.status_code == 200
    assert get_res.json()["target_calories_kcal"] > 0


def test_cv_telemetry_sync():
    payload = {
        "user_id": "usr_test_984",
        "session_id": "sess_10293",
        "exercise_id": "ex_barbell_squat",
        "timestamp": "2026-07-25T18:30:00Z",
        "good_reps": 8,
        "bad_reps": 2,
        "total_reps": 10,
        "form_faults": [
            {
                "fault_type": "knee_valgus",
                "occurrences": 2,
                "rep_numbers": [7, 8]
            }
        ],
        "mean_tempo_seconds": 2.4,
        "completion_progress_pct": 100.0
    }

    # Test POST /telemetry/sync
    response = client.post("/telemetry/sync", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["form_efficiency_pct"] == 80.0

    # Test GET /telemetry/{user_id}
    get_res = client.get("/telemetry/usr_test_984")
    assert get_res.status_code == 200
    assert len(get_res.json()) >= 1


def test_daily_feedback_and_safety():
    payload = {
        "user_id": "usr_test_984",
        "workout_session_id": "sess_10293",
        "date": "2026-07-25T19:00:00Z",
        "perceived_difficulty": "hard",
        "completion_rate": 1.0,
        "feedback_notes": [
            {
                "exercise_id": "ex_barbell_squat",
                "rating": "hard",
                "pain_flag": True,
                "pain_location": "lower_back",
                "comment": "Sharp pinch in lower back"
            }
        ]
    }

    # Test POST /feedback/submit
    response = client.post("/feedback/submit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["pain_flags_count"] == 1
    assert len(data["safety_adjustments"]) > 0

    # Test GET /feedback/{user_id}
    get_res = client.get("/feedback/usr_test_984")
    assert get_res.status_code == 200
    assert len(get_res.json()) >= 1


def test_monthly_report_aggregator():
    payload = {
        "user_id": "usr_test_984",
        "current_smm_kg": 38.2,
        "baseline_smm_kg": 37.4,
        "current_bf_pct": 17.1,
        "baseline_bf_pct": 18.3
    }

    # Test POST /reports/monthly
    response = client.post("/reports/monthly", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "usr_test_984"
    assert data["inbody_deltas"]["muscle_mass_delta_kg"] == 0.8
    report_id = data["report_id"]

    # Test GET /reports/{report_id}
    get_res = client.get(f"/reports/{report_id}")
    assert get_res.status_code == 200
    assert get_res.json()["report_id"] == report_id


def test_coach_assistant_chat(monkeypatch):
    # Create a valid token for the test user
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "message": "Why do my knees cave in during squats?"
    }

    # Mock the coach service to avoid requiring MongoDB
    import api.routes.coach as coach_route
    async def fake_process(user_id, message, nutrition_plan_snapshot):
        return "Knee valgus during squats often indicates weak hip abductors. Focus on lateral band walks and clamshells."

    monkeypatch.setattr(coach_route, "process_coach_message", fake_process)

    # Test POST /coach/chat
    response = client.post("/coach/chat", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0
