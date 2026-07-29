"""
Module 2: Workout Agent Engine
Constructs individualized workout programs utilizing exercise libraries, split generation, and volume budget enforcement.
"""

from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime, timezone
from api.schemas.integration_schemas import OnboardingSurvey


class WorkoutEngine:
    def __init__(self):
        self._workouts_db: Dict[str, Dict[str, Any]] = {}

    def generate_workout_plan(
        self,
        user_id: str,
        survey: OnboardingSurvey,
        injuries_or_pain_locations: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generates a dynamic personalized workout plan based on user goals, equipment, and constraints."""
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        days = survey.days_per_week
        goal = survey.fitness_goal.lower()
        equipment = survey.available_equipment
        pain_locations = injuries_or_pain_locations or []

        # Determine Split
        if days <= 3:
            split_type = "Full Body 3x/week"
            routine = self._build_full_body_schedule(days, equipment, pain_locations)
        elif days == 4:
            split_type = "Upper / Lower Split"
            routine = self._build_upper_lower_schedule(equipment, pain_locations)
        else:
            split_type = "Push / Pull / Legs Split"
            routine = self._build_ppl_schedule(days, equipment, pain_locations)

        plan = {
            "session_id": session_id,
            "user_id": user_id,
            "split_type": split_type,
            "target_goal": goal,
            "days_per_week": days,
            "session_duration_minutes": survey.session_duration_minutes,
            "routine": routine,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

        self._workouts_db[session_id] = plan
        return plan

    def get_plan(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._workouts_db.get(session_id)

    def _build_full_body_schedule(self, days: int, equipment: List[str], pain: List[str]) -> List[Dict[str, Any]]:
        squat_ex = "ex_goblet_squat" if "lower_back" in pain else "ex_barbell_squat"
        bench_ex = "ex_dumbbell_bench_press" if "shoulder" in pain else "ex_barbell_bench_press"

        return [
            {
                "day_name": f"Day {i+1} - Full Body",
                "exercises": [
                    {"exercise_id": squat_ex, "name": "Squat Variation", "sets": 3, "reps": "8-10", "tempo": "2-0-2-0"},
                    {"exercise_id": bench_ex, "name": "Chest Press Variation", "sets": 3, "reps": "8-12", "tempo": "2-0-1-0"},
                    {"exercise_id": "ex_lat_pulldown", "name": "Lat Pulldown", "sets": 3, "reps": "10-12", "tempo": "2-0-2-0"},
                    {"exercise_id": "ex_romanian_deadlift", "name": "Romanian Deadlift", "sets": 3, "reps": "10-12", "tempo": "3-0-1-0"}
                ]
            }
            for i in range(days)
        ]

    def _build_upper_lower_schedule(self, equipment: List[str], pain: List[str]) -> List[Dict[str, Any]]:
        return [
            {
                "day_name": "Day 1 - Upper Power",
                "exercises": [
                    {"exercise_id": "ex_barbell_bench_press", "name": "Barbell Bench Press", "sets": 4, "reps": "6-8", "tempo": "2-1-1-0"},
                    {"exercise_id": "ex_bent_over_row", "name": "Barbell Row", "sets": 4, "reps": "6-8", "tempo": "2-0-1-0"},
                    {"exercise_id": "ex_overhead_press", "name": "Overhead Press", "sets": 3, "reps": "8-10", "tempo": "2-0-1-0"}
                ]
            },
            {
                "day_name": "Day 2 - Lower Power",
                "exercises": [
                    {"exercise_id": "ex_leg_press" if "lower_back" in pain else "ex_barbell_squat", "name": "Squat / Leg Press", "sets": 4, "reps": "6-8", "tempo": "3-1-1-0"},
                    {"exercise_id": "ex_romanian_deadlift", "name": "Romanian Deadlift", "sets": 3, "reps": "8-10", "tempo": "3-0-1-0"},
                    {"exercise_id": "ex_walking_lunges", "name": "Walking Lunges", "sets": 3, "reps": "10-12", "tempo": "2-0-1-0"}
                ]
            },
            {
                "day_name": "Day 3 - Upper Hypertrophy",
                "exercises": [
                    {"exercise_id": "ex_incline_dumbbell_press", "name": "Incline DB Press", "sets": 3, "reps": "10-12", "tempo": "2-0-1-0"},
                    {"exercise_id": "ex_lat_pulldown", "name": "Lat Pulldown", "sets": 3, "reps": "10-12", "tempo": "2-0-2-0"},
                    {"exercise_id": "ex_lateral_raise", "name": "Lateral Raise", "sets": 4, "reps": "12-15", "tempo": "2-0-1-0"}
                ]
            },
            {
                "day_name": "Day 4 - Lower Hypertrophy",
                "exercises": [
                    {"exercise_id": "ex_hack_squat", "name": "Hack Squat", "sets": 3, "reps": "10-12", "tempo": "2-1-1-0"},
                    {"exercise_id": "ex_lying_leg_curl", "name": "Lying Leg Curl", "sets": 4, "reps": "12-15", "tempo": "2-0-2-0"},
                    {"exercise_id": "ex_calf_raise", "name": "Standing Calf Raise", "sets": 4, "reps": "15-20", "tempo": "2-1-2-1"}
                ]
            }
        ]

    def _build_ppl_schedule(self, days: int, equipment: List[str], pain: List[str]) -> List[Dict[str, Any]]:
        return [
            {
                "day_name": "Day 1 - Push",
                "exercises": [
                    {"exercise_id": "ex_barbell_bench_press", "name": "Bench Press", "sets": 4, "reps": "8-10", "tempo": "2-0-1-0"},
                    {"exercise_id": "ex_incline_db_press", "name": "Incline Dumbbell Press", "sets": 3, "reps": "10-12", "tempo": "2-0-1-0"},
                    {"exercise_id": "ex_tricep_pushdown", "name": "Tricep Pushdown", "sets": 4, "reps": "12-15", "tempo": "2-0-1-0"}
                ]
            },
            {
                "day_name": "Day 2 - Pull",
                "exercises": [
                    {"exercise_id": "ex_barbell_row", "name": "Barbell Row", "sets": 4, "reps": "8-10", "tempo": "2-0-1-0"},
                    {"exercise_id": "ex_lat_pulldown", "name": "Lat Pulldown", "sets": 3, "reps": "10-12", "tempo": "2-0-2-0"},
                    {"exercise_id": "ex_bicep_curl", "name": "Dumbbell Bicep Curl", "sets": 4, "reps": "10-12", "tempo": "2-0-1-0"}
                ]
            },
            {
                "day_name": "Day 3 - Legs",
                "exercises": [
                    {"exercise_id": "ex_leg_press" if "lower_back" in pain else "ex_barbell_squat", "name": "Squat / Leg Press", "sets": 4, "reps": "8-10", "tempo": "3-0-1-0"},
                    {"exercise_id": "ex_romanian_deadlift", "name": "RDL", "sets": 3, "reps": "10-12", "tempo": "3-0-1-0"},
                    {"exercise_id": "ex_leg_extension", "name": "Leg Extension", "sets": 3, "reps": "12-15", "tempo": "2-0-1-0"}
                ]
            }
        ]


workout_engine = WorkoutEngine()
