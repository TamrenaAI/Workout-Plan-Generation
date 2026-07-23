"""
Shared pytest fixtures. `mongo_db` (autouse) gives every test an isolated
in-memory MongoDB via mongomock, so no test ever touches the real Mongo
instance this app connects to in dev/prod.
"""

import mongomock
import pytest

import tools.mongo as mongo_module


@pytest.fixture(autouse=True)
def mongo_db(monkeypatch):
    client = mongomock.MongoClient()
    monkeypatch.setattr(mongo_module, "_client", client)
    yield client
