"""
Module 5: Daily Feedback & Safety Engine
Processes daily post-workout feedback, ratings, and pain flags to trigger deloads or exercise substitutions.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from api.schemas.integration_schemas import DailyFeedbackPayload


class FeedbackSafetyEngine:
    def __init__(self):
        self._feedback_db: Dict[str, List[Dict[str, Any]]] = {}

    def process_feedback(self, payload: DailyFeedbackPayload) -> Dict[str, Any]:
        """Analyzes daily post-workout feedback, checks pain flags, and returns safety adjustments."""
        user_id = payload.user_id
        if user_id not in self._feedback_db:
            self._feedback_db[user_id] = []

        data = payload.model_dump()
        data["processed_at"] = datetime.now(timezone.utc).isoformat()
        self._feedback_db[user_id].append(data)

        adjustments: List[Dict[str, Any]] = []
        pain_locations: List[str] = []

        # Evaluate pain flags and ratings
        for note in payload.feedback_notes:
            if note.pain_flag:
                loc = note.pain_location or "unspecified"
                pain_locations.append(loc)
                adjustments.append({
                    "type": "exercise_substitution",
                    "exercise_id": note.exercise_id,
                    "reason": f"Pain reported at {loc}",
                    "action": f"Substitute {note.exercise_id} with low-impact alternative in next cycle."
                })

        # Evaluate overall difficulty
        if payload.perceived_difficulty.lower() in ["hard", "extreme", "very hard"]:
            adjustments.append({
                "type": "volume_deload",
                "reason": "Perceived difficulty was rated high",
                "action": "Reduce set volume by 10-15% for upcoming sessions."
            })

        return {
            "status": "success",
            "workout_session_id": payload.workout_session_id,
            "pain_flags_count": len(pain_locations),
            "pain_locations": pain_locations,
            "safety_adjustments": adjustments
        }

    def get_user_feedback_history(self, user_id: str) -> List[Dict[str, Any]]:
        return self._feedback_db.get(user_id, [])


feedback_safety_engine = FeedbackSafetyEngine()
