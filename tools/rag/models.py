"""
Pydantic models for RAG chunks and metadata, matching the data already
ingested into rag_data/qdrant by notebooks/chunking.ipynb +
notebooks/vectordb_retrieval.ipynb. Do not change field names or literal
values here without re-ingesting — this schema must match the stored
payloads exactly.
"""

from typing import Literal

from pydantic import BaseModel, Field


class PrinciplesMetadata(BaseModel):
    topic: list[
        Literal[
            "program_design", "periodization", "progressive_overload", "volume",
            "frequency", "intensity", "load", "exercise_selection", "recovery",
            "fatigue", "warmup", "energy_systems",
        ]
    ] = Field(min_length=1)

    planner_stage: list[
        Literal[
            "goal_selection", "program_design", "exercise_selection",
            "progression", "recovery",
        ]
    ] = Field(min_length=1)

    goals: list[
        Literal["hypertrophy", "strength", "fat_loss", "endurance"]
    ] = Field(min_length=1)

    applies_to: list[
        Literal["all", "hypertrophy", "strength", "fat_loss"]
    ] = Field(min_length=1)

    knowledge_type: list[
        Literal["definition", "principle", "recommendation", "warning", "protocol"]
    ] = Field(min_length=1)


class GoalNamespaceMetadata(BaseModel):
    muscle: list[
        Literal[
            "all", "chest", "back", "shoulders", "biceps", "triceps", "forearms",
            "quads", "hamstrings", "glutes", "calves", "abs",
        ]
    ] = Field(min_length=1)

    topic: list[
        Literal[
            "muscle_physiology", "neuromuscular_system", "muscle_activation",
            "biomechanics", "muscle_growth_mechanisms", "hypertrophy_programming",
            "maximal_strength", "force_production", "power_development",
            "neural_adaptation", "volume", "frequency", "intensity", "load",
            "exercise_selection", "exercise_order", "periodization", "recovery",
            "fatigue_management", "advanced_techniques",
        ]
    ] = Field(min_length=1)

    experience_level: Literal["all", "beginner", "intermediate", "advanced"]

    goals: list[
        Literal["hypertrophy", "strength", "fat_loss"]
    ] = Field(min_length=1)


class Chunk(BaseModel):
    id: str
    text: str
    book: str
    chapter: str
    collection: Literal["principles", "hypertrophy", "strength"]
    chunk_index: int
    metadata: PrinciplesMetadata | GoalNamespaceMetadata | None = None


class ScoredChunk(Chunk):
    score: float


class PrinciplesQueryFilter(BaseModel):
    topic: list[
        Literal[
            "program_design", "periodization", "progressive_overload", "volume",
            "frequency", "intensity", "load", "exercise_selection", "recovery",
            "fatigue", "warmup", "energy_systems",
        ]
    ] | None = None

    planner_stage: list[
        Literal[
            "goal_selection", "program_design", "exercise_selection",
            "progression", "recovery",
        ]
    ] | None = None

    goals: list[
        Literal["hypertrophy", "strength", "fat_loss", "endurance"]
    ] | None = None

    applies_to: list[
        Literal["all", "hypertrophy", "strength", "fat_loss"]
    ] | None = None

    knowledge_type: list[
        Literal["definition", "principle", "recommendation", "warning", "protocol"]
    ] | None = None


class GoalQueryFilter(BaseModel):
    muscle: list[
        Literal[
            "all", "chest", "back", "shoulders", "biceps", "triceps", "forearms",
            "quads", "hamstrings", "glutes", "calves", "abs",
        ]
    ] | None = None

    topic: list[
        Literal[
            "muscle_physiology", "neuromuscular_system", "muscle_activation",
            "biomechanics", "muscle_growth_mechanisms", "hypertrophy_programming",
            "maximal_strength", "force_production", "power_development",
            "neural_adaptation", "volume", "frequency", "intensity", "load",
            "exercise_selection", "exercise_order", "periodization", "recovery",
            "fatigue_management", "advanced_techniques",
        ]
    ] | None = None

    experience_level: Literal["all", "beginner", "intermediate", "advanced"] | None = None

    goals: list[
        Literal["hypertrophy", "strength", "fat_loss"]
    ] | None = None
