"""
Turns an extracted query filter into a Qdrant Filter, and (see the
extractor classes added below) turns a raw query into that extracted
filter via an LLM structured-output call.

GoalFilterBuilder / GoalQueryFilter cover the hypertrophy/strength
collections (GoalNamespaceMetadata: muscle, topic, experience_level,
goals). PrinciplesFilterBuilder / PrinciplesQueryFilter cover the
principles collection (PrinciplesMetadata: topic, planner_stage, goals,
applies_to, knowledge_type) — a different schema, so a separate builder.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from qdrant_client.models import FieldCondition, Filter, MatchAny

from tools.rag.models import GoalQueryFilter, PrinciplesQueryFilter

T = TypeVar("T")


class BaseFilterBuilder(ABC, Generic[T]):
    @abstractmethod
    def build(self, query_filter: T) -> Filter:
        pass


class GoalFilterBuilder(BaseFilterBuilder[GoalQueryFilter]):
    def build(self, query_filter: GoalQueryFilter) -> Filter:
        must = []

        if query_filter.muscle:
            must.append(
                FieldCondition(
                    key="metadata.muscle",
                    match=MatchAny(any=[*query_filter.muscle, "all"]),
                )
            )

        if query_filter.topic:
            must.append(
                FieldCondition(
                    key="metadata.topic",
                    match=MatchAny(any=query_filter.topic),
                )
            )

        if query_filter.experience_level:
            must.append(
                FieldCondition(
                    key="metadata.experience_level",
                    match=MatchAny(any=[query_filter.experience_level, "all"]),
                )
            )

        if query_filter.goals:
            must.append(
                FieldCondition(
                    key="metadata.goals",
                    match=MatchAny(any=query_filter.goals),
                )
            )

        return Filter(must=must)


class PrinciplesFilterBuilder(BaseFilterBuilder[PrinciplesQueryFilter]):
    def build(self, query_filter: PrinciplesQueryFilter) -> Filter:
        must = []

        if query_filter.topic:
            must.append(
                FieldCondition(
                    key="metadata.topic",
                    match=MatchAny(any=query_filter.topic),
                )
            )

        if query_filter.planner_stage:
            must.append(
                FieldCondition(
                    key="metadata.planner_stage",
                    match=MatchAny(any=query_filter.planner_stage),
                )
            )

        if query_filter.goals:
            must.append(
                FieldCondition(
                    key="metadata.goals",
                    match=MatchAny(any=query_filter.goals),
                )
            )

        if query_filter.applies_to:
            must.append(
                FieldCondition(
                    key="metadata.applies_to",
                    match=MatchAny(any=[*query_filter.applies_to, "all"]),
                )
            )

        if query_filter.knowledge_type:
            must.append(
                FieldCondition(
                    key="metadata.knowledge_type",
                    match=MatchAny(any=query_filter.knowledge_type),
                )
            )

        return Filter(must=must)
