"""
Tests for auth/dependencies.py's get_current_user / get_current_user_for_stream.

Since the BFF handoff (docs/superpowers/specs/2026-07-25-bff-auth-handoff-design.md),
this service no longer owns user identity — it only verifies the JWT
(signed with a secret shared with the BFF) and trusts the `sub` claim as
the user_id. There is no local `users` lookup anymore: a token for a
user_id that was never written to this service's database must still
resolve successfully (proven implicitly here too — conftest.py's
`dynamo_tables` fixture gives every test a fresh, empty set of DynamoDB
tables, so if the old DB-lookup behavior were still present, every test
below would fail with "User no longer exists" instead of passing).
"""

import os
import sys
import uuid

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import dependencies, tokens


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    monkeypatch.setattr(tokens, "JWT_SECRET", "test-secret-do-not-use-in-real-envs")


def test_resolve_user_returns_id_from_token_with_no_matching_db_record():
    user_id = str(uuid.uuid4())
    token = tokens.create_access_token(user_id=user_id)

    result = dependencies._resolve_user(token)

    assert result == {"id": user_id}


def test_resolve_user_rejects_invalid_token():
    with pytest.raises(HTTPException) as exc_info:
        dependencies._resolve_user("not-a-real-token")
    assert exc_info.value.status_code == 401


def test_resolve_user_accepts_any_non_empty_sub_as_user_id():
    # This service no longer validates the JWT `sub` claim's shape (e.g. as
    # a Mongo ObjectId) — the BFF issues opaque string/uuid user ids, and
    # any non-empty sub is a valid user id now.
    token = tokens.create_access_token(user_id="not-an-objectid")

    result = dependencies._resolve_user(token)

    assert result == {"id": "not-an-objectid"}
