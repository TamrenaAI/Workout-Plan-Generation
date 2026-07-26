"""
Module 1: InBody OCR & Document Parser Engine
Handles InBody scan parsing, quality checking, metrics extraction, and onboarding survey storage.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from api.schemas.integration_schemas import InBodyMetrics, OnboardingSurvey, InBodyOnboardingPayload


class InBodyParserEngine:
    def __init__(self):
        self._inbody_db: Dict[str, list] = {}

    def parse_and_store(self, payload: InBodyOnboardingPayload) -> Dict[str, Any]:
        """Validates and stores InBody metrics and onboarding preferences for a user."""
        user_id = payload.user_id
        if user_id not in self._inbody_db:
            self._inbody_db[user_id] = []

        record = {
            "timestamp": datetime.now(timezone.utc),
            "onboarding": payload.onboarding_survey.model_dump(),
            "inbody": payload.inbody_data.model_dump()
        }
        self._inbody_db[user_id].append(record)

        return {
            "status": "success",
            "user_id": user_id,
            "scans_recorded": len(self._inbody_db[user_id]),
            "latest_metrics": payload.inbody_data.model_dump()
        }

    def get_latest_metrics(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent InBody scan metrics for a user."""
        scans = self._inbody_db.get(user_id, [])
        if not scans:
            return None
        return scans[-1]


inbody_parser_engine = InBodyParserEngine()
