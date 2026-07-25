from typing import Literal
from pydantic import BaseModel, Field
from dataclasses import dataclass
from pathlib import Path


Goal = Literal[
    "all",
    "hypertrophy",
    "strength",
    "fat_loss",
    #"endurance"
]

PrinciplesTopic = Literal[
    "program_design",
    "periodization",
    "progressive_overload",
    "volume",
    "frequency",
    "intensity",
    "load",
    "exercise_selection",
    "recovery",
    "fatigue",
    "warmup",
    "energy_systems",
]

PlannerStage = Literal[
    "goal_selection",
    "program_design",
    "exercise_selection",
    "progression",
    "recovery",
]

AppliesTo = Literal[
    "all",
    "hypertrophy",
    "strength",
    "fat_loss",
    #"endurance"
]

KnowledgeType = Literal[
    "definition",
    "principle",
    "recommendation",
    "warning",
    "protocol",
]

Muscle = Literal[
    "all",
    "chest",
    "back",
    "shoulders",
    "biceps",
    "triceps",
    "forearms",
    "quads",
    "hamstrings",
    "glutes",
    "calves",
    "abs",
]

GoalTopic = Literal[
    # Science
    "muscle_physiology",
    "neuromuscular_system",
    "muscle_activation",
    "biomechanics",

    # Goal-specific
    "muscle_growth_mechanisms",
    "hypertrophy_programming",
    "maximal_strength",
    "force_production",
    "power_development",
    "neural_adaptation",

    # Programming
    "volume",
    "frequency",
    "intensity",
    "load",
    "exercise_selection",
    "exercise_order",
    "periodization",
    "recovery",
    "fatigue_management",
    "advanced_techniques",
]

ExperienceLevel = Literal[
    "all",
    "beginner",
    "intermediate",
    "advanced",
]

CollectionName = Literal[
    "principles",
    "hypertrophy",
    "strength",
]

COLLECTIONS = [
    "principles",
    "hypertrophy",
    "strength",
]

class PrinciplesMetadata(BaseModel):
    topic: list[PrinciplesTopic] = Field(min_length=1)
    planner_stage: list[PlannerStage] = Field(min_length=1)
    goals: list[Goal] = Field(min_length=1)
    applies_to: list[AppliesTo] = Field(min_length=1)
    knowledge_type: list[KnowledgeType] = Field(min_length=1)

class GoalNamespaceMetadata(BaseModel):
    muscle: list[Muscle] = Field(min_length=1)
    topic: list[GoalTopic] = Field(min_length=1)
    experience_level: ExperienceLevel
    goals: list[Goal] = Field(min_length=1)


class CollectionRoute(BaseModel):
    collection: CollectionName

class Section(BaseModel):
    title: str = Field(description="Current section title")
    level: int = Field(description="Markdown heading level (1-6)")
    parent_titles: list[str] = Field(default_factory=list)
    content: str = Field(description="Section content")



@dataclass
class ChapterInfo:
    title: str
    start_page: int
    end_page: int


@dataclass
class BookInfo:
    title: str
    author: str
    slug: str

@dataclass
class BookPaths:
    book_dir: Path
    chapters_dir: Path
    markdown_dir: Path
    chunks_dir: Path


class Chunk(BaseModel):
    id: str
    
    text: str

    book: str
    chapter: str
    collection: CollectionName

    chunk_index: int

    metadata: PrinciplesMetadata | GoalNamespaceMetadata | None = None


class ChunkingConfig(BaseModel):
    chunk_size: int = 800
    chunk_overlap: int = 150
    min_chunk_chars: int = 120
    
    separators: list[str] = Field(
        default_factory=lambda: [
            "\n\n",
            "\n",
            " ",
            "",
        ]
    )



class ScoredChunk(Chunk):
    score: float


class PrinciplesQueryFilter(BaseModel):

    topic: list[PrinciplesTopic]| None = None

    planner_stage: list[PlannerStage] | None = None

    goals: list[Goal] | None = None

    applies_to: list[AppliesTo] | None = None

    knowledge_type: list[KnowledgeType ] | None = None


class GoalQueryFilter(BaseModel):

    muscle: list[Muscle] | None = None

    topic: list[GoalTopic ] | None = None

    experience_level: ExperienceLevel | None = None

    goals: list[Goal ] | None = None


class RAGResponse(BaseModel):
    answer: str
    chunks: list[ScoredChunk]

