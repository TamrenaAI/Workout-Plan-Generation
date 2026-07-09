"""
GET /health — liveness + readiness probe.

Checks the dependencies this stage of the system actually has: SQLite and
the Azure OpenAI configuration. RAG (Qdrant + local embedding/reranker
models) is a hardcoded stub right now, so it's reported as such rather than
probed — there's nothing external to fail.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME, AZURE_OPENAI_ENDPOINT
from tools.database import get_db_connection

router = APIRouter()


@router.get("/health")
async def health_check():
    results = {}
    overall = "healthy"

    # SQLite
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        results["sqlite"] = "healthy"
    except Exception as e:
        results["sqlite"] = f"unhealthy: {e}"
        overall = "unhealthy"

    # Azure OpenAI configuration (env vars present — not a live call on every health check)
    if AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT_NAME:
        results["azure_openai"] = "healthy"
    else:
        results["azure_openai"] = "unhealthy: missing AZURE_OPENAI_* environment variables"
        overall = "unhealthy"

    results["rag"] = "stub — hardcoded principles/muscle notes, pending RAG team ingestion pipeline"

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
