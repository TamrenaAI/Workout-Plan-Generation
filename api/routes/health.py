"""
GET /health — liveness + readiness probe.

Checks the dependencies this stage of the system actually has: a real
DynamoDB round-trip (list_tables), the Azure OpenAI configuration, and
that the RAG Qdrant data is present on disk. The Azure OpenAI and RAG
checks don't trigger a real Qdrant connection or load the
embedding/reranker models — tools/rag/pipeline.py lazily loads those on
first real search_rag() call, not on every health probe, so those only
check that config/the directory is present (not a live call).
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME, AZURE_OPENAI_ENDPOINT, QDRANT_PATH
from tools.dynamo import get_resource

router = APIRouter()


@router.get("/health")
async def health_check():
    results = {}
    overall = "healthy"

    # DynamoDB
    try:
        get_resource().meta.client.list_tables(Limit=1)
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
