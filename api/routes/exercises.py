"""
GET /exercises/lookup — look up an exercise by name and return its GIF,
thumbnail, and instructions, so the mobile app can show a preview before
the user starts a set (see WorkoutScreen.tsx's "Start Set" flow).

Plan-generated exercise names come from the LLM's markdown table and carry
no exercise ID — they won't always match this dataset's naming exactly
("Flat Barbell Bench Press" vs. this catalog's "barbell bench press").
Matching is by normalized substring + fuzzy ratio, not an exact key
lookup; below-threshold matches 404 rather than returning the wrong
exercise's media.
"""

import re
from difflib import SequenceMatcher
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.dependencies import get_current_user
from tools.mongo import get_db

router = APIRouter()

MEDIA_URL_BASE = "/media/exercises"

# Below this Jaccard token-overlap score, treat it as no match rather than
# guess: char-level similarity (SequenceMatcher) alone turned out to rank
# "Barbell Back Squat" above "barbell hack squat" at 0.94 — a wrong
# exercise that just happens to share a lot of letters. Token overlap
# correctly separates real synonyms ("Tricep Pushdown" vs. "cable one arm
# tricep pushdown", 0.40) from false-positive noise (0.2 and below), and
# it also means an exercise this catalog has no real match for (e.g.
# "Face Pull") correctly 404s instead of returning an unrelated GIF —
# showing the wrong movement is worse than showing none.
_MATCH_THRESHOLD = 0.4


def _tokens(name: str) -> set:
    return set(re.sub(r"[^a-z0-9 ]", " ", name.lower()).split())


def _score(query: str, candidate: str) -> tuple:
    q_tokens, c_tokens = _tokens(query), _tokens(candidate)
    if not q_tokens or not c_tokens:
        return (0.0, 0.0)
    jaccard = len(q_tokens & c_tokens) / len(q_tokens | c_tokens)
    ratio = SequenceMatcher(None, query.lower(), candidate.lower()).ratio()
    return (jaccard, ratio)


class ExerciseMedia(BaseModel):
    name: str
    target_muscle: Optional[str] = None
    equipment: Optional[str] = None
    instructions: Optional[str] = None
    image_url: Optional[str] = None
    gif_url: Optional[str] = None
    attribution: Optional[str] = None


@router.get("/exercises/lookup", response_model=ExerciseMedia)
async def lookup_exercise(name: str, user: dict = Depends(get_current_user)):
    docs = list(get_db().exercises.find(
        {"gif_path": {"$ne": None}},
        {"name": 1, "target_muscle": 1, "equipment": 1, "instructions": 1, "image_path": 1, "gif_path": 1, "attribution": 1},
    ))

    if not docs:
        raise HTTPException(404, f"No matching exercise found for '{name}'.")

    best = max(docs, key=lambda d: _score(name, d["name"]))
    if _score(name, best["name"])[0] < _MATCH_THRESHOLD:
        raise HTTPException(404, f"No matching exercise found for '{name}'.")

    return ExerciseMedia(
        name=best["name"],
        target_muscle=best.get("target_muscle"),
        equipment=best.get("equipment"),
        instructions=best.get("instructions"),
        image_url=f"{MEDIA_URL_BASE}/{best['image_path']}" if best.get("image_path") else None,
        gif_url=f"{MEDIA_URL_BASE}/{best['gif_path']}" if best.get("gif_path") else None,
        attribution=best.get("attribution"),
    )
