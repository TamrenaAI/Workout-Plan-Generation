"""
User accounts — MongoDB `users` collection (same database as everything
else, see tools/mongo.py).

Google is the only sign-in method wired up for now (google_sub is
required). If email/password or another provider is added later,
google_sub should become optional and a `provider` field should
distinguish documents.
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId

from tools.mongo import get_db


def _serialize(doc: dict) -> dict:
    """Mongo's _id (ObjectId) becomes "id" (str) — every caller in this
    codebase (auth/tokens.py, api/routes/auth.py's _public_user, etc.)
    already treats the user id as an opaque string."""
    return {
        "id": str(doc["_id"]),
        "google_sub": doc["google_sub"],
        "email": doc["email"],
        "name": doc.get("name"),
        "picture_url": doc.get("picture_url"),
        "created_at": doc["created_at"],
    }


def get_user_by_id(user_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return None
    doc = get_db().users.find_one({"_id": oid})
    return _serialize(doc) if doc else None


def get_or_create_user_by_google(sub: str, email: str, name: Optional[str], picture_url: Optional[str]) -> dict:
    """Looks up a user by their stable Google subject ID, creating the
    document on first sign-in. `sub` (not email) is the identity key —
    Google's own docs warn email addresses can be reassigned, sub never
    is."""
    db = get_db()
    doc = db.users.find_one({"google_sub": sub})
    if doc:
        return _serialize(doc)

    doc = {
        "google_sub": sub,
        "email": email,
        "name": name,
        "picture_url": picture_url,
        "created_at": datetime.now(timezone.utc),
    }
    result = db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)
