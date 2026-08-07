"""
GET /health — liveness + readiness probe.

Checks the dependencies this stage of the system actually has: a real
DynamoDB round-trip (a describe_table call against a single known table),
the Azure OpenAI configuration, and that the RAG Qdrant data is present on
disk. The Azure OpenAI and RAG checks don't trigger a real Qdrant
connection or load the embedding/reranker models — tools/rag/pipeline.py
lazily loads those on first real search_rag() call, not on every health
probe, so those only check that config/the directory is present (not a
live call).

The DynamoDB check intentionally uses a single-table describe_table (via
get_exercises_table().table_status, which triggers a lazy .load() under
the boto3 resource API) rather than an account-wide list_tables call —
a least-privilege production task role scoped to GetItem/PutItem/Query/
DescribeTable on the app's named tables would not grant dynamodb:ListTables,
which would make an account-wide check falsely report unhealthy in
production even though real reads/writes work fine.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME, AZURE_OPENAI_ENDPOINT, QDRANT_PATH
from tools.dynamo import get_exercises_table

router = APIRouter()


@router.get("/health")
async def health_check():
    results = {}
    overall = "healthy"

    # DynamoDB — single-table describe_table (see module docstring for why
    # this isn't an account-wide list_tables call).
    try:
        get_exercises_table().table_status
        results["dynamodb"] = "healthy"
    except Exception as e:
        results["dynamodb"] = f"unhealthy: {e}"
        overall = "unhealthy"

    # Azure OpenAI configuration (env vars present — not a live call on every health check)
    if AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT_NAME:
        results["azure_openai"] = "healthy"
    else:
        results["azure_openai"] = "unhealthy: missing AZURE_OPENAI_* environment variables"
        overall = "unhealthy"

    # RAG Qdrant data present (path exists — not a live Qdrant connection or
    # model load on every health check)
    if QDRANT_PATH.exists():
        results["rag"] = "healthy"
    else:
        results["rag"] = f"unhealthy: Qdrant data not found at {QDRANT_PATH}"
        overall = "unhealthy"

    status_code = 200 if overall == "healthy" else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "dependencies": results,
        },
    )
