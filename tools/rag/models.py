"""
Pydantic models for RAG chunks and metadata, matching the data already
ingested into rag_data/qdrant by notebooks/chunking.ipynb +
notebooks/vectordb_retrieval.ipynb. Do not change field names or literal
values here without re-ingesting — this schema must match the stored
payloads exactly.
"""

from typing import Literal

from pydantic import BaseModel, Field

# Shared Literal type aliases for metadata and query filter consistency
PrinciplesTopic = Literal[
    "program_design", "periodization", "progressive_overload", "volume",
    "frequency", "intensity", "load", "exercise_selection", "recovery",
    "fatigue", "warmup", "energy_systems",
]

PlannerStage = Literal[
    "goal_selection", "program_design", "exercise_selection",
    "progression", "recovery",
]

PrinciplesGoal = Literal["all", "hypertrophy", "strength", "fat_loss", "endurance"]

AppliesTo = Literal["all", "hypertrophy", "strength", "fat_loss"]

KnowledgeType = Literal["definition", "principle", "recommendation", "warning", "protocol"]

Muscle = Literal[
    "all", "chest", "back", "shoulders", "biceps", "triceps", "forearms",
    "quads", "hamstrings", "glutes", "calves", "abs",
]

GoalTopic = Literal[
    "muscle_physiology", "neuromuscular_system", "muscle_activation",
    "biomechanics", "muscle_growth_mechanisms", "hypertrophy_programming",
    "maximal_strength", "force_production", "power_development",
    "neural_adaptation", "volume", "frequency", "intensity", "load",
    "exercise_selection", "exercise_order", "periodization", "recovery",
    "fatigue_management", "advanced_techniques",
]

ExperienceLevel = Literal["all", "beginner", "intermediate", "advanced"]

TrainingGoal = Literal["all", "hypertrophy", "strength", "fat_loss"]


class PrinciplesMetadata(BaseModel):
    topic: list[PrinciplesTopic] = Field(min_length=1)
    planner_stage: list[PlannerStage] = Field(min_length=1)
    goals: list[PrinciplesGoal] = Field(min_length=1)
    applies_to: list[AppliesTo] = Field(min_length=1)
    knowledge_type: list[KnowledgeType] = Field(min_length=1)


class GoalNamespaceMetadata(BaseModel):
    muscle: list[Muscle] = Field(min_length=1)
    topic: list[GoalTopic] = Field(min_length=1)
    experience_level: ExperienceLevel
    goals: list[TrainingGoal] = Field(min_length=1)


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
    topic: list[PrinciplesTopic] | None = None
    planner_stage: list[PlannerStage] | None = None
    goals: list[PrinciplesGoal] | None = None
    applies_to: list[AppliesTo] | None = None
    knowledge_type: list[KnowledgeType] | None = None


class GoalQueryFilter(BaseModel):
    muscle: list[Muscle] | None = None
    topic: list[GoalTopic] | None = None
    experience_level: ExperienceLevel | None = None
    goals: list[TrainingGoal] | None = None
