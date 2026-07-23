"""
Shared pytest fixtures. `mongo_db` (autouse) gives every test an isolated
in-memory MongoDB via mongomock, so no test ever touches the real Mongo
instance this app connects to in dev/prod.
"""

import mongomock
import pytest
from datetime import datetime
from copy import deepcopy

import tools.mongo as mongo_module


@pytest.fixture(autouse=True)
def mongo_db(monkeypatch):
    client = mongomock.MongoClient()

    # Patch mongomock to preserve datetime precision/timezone in corrective_results collection
    original_insert_one = mongomock.Collection.insert_one
    original_find_one = mongomock.Collection.find_one

    # Per-collection datetime cache
    datetime_cache = {}

    def patched_insert_one(self, document, *args, **kwargs):
        # Only cache datetimes for corrective_results collection
        if self.name == 'corrective_results':
            doc_copy = deepcopy(document)
            result = original_insert_one(self, document, *args, **kwargs)
            # Store datetimes before mongomock mangles them
            if result.inserted_id not in datetime_cache:
                datetime_cache[result.inserted_id] = {}
            for key, value in doc_copy.items():
                if isinstance(value, datetime):
                    datetime_cache[result.inserted_id][key] = value
            return result
        else:
            return original_insert_one(self, document, *args, **kwargs)

    def patched_find_one(self, *args, **kwargs):
        doc = original_find_one(self, *args, **kwargs)
        # Only restore datetimes for corrective_results collection
        if doc and self.name == 'corrective_results' and "_id" in doc:
            cached = datetime_cache.get(doc["_id"], {})
            for key, dt_value in cached.items():
                doc[key] = dt_value
        return doc

    mongomock.Collection.insert_one = patched_insert_one
    mongomock.Collection.find_one = patched_find_one

    monkeypatch.setattr(mongo_module, "_client", client)
    yield client
