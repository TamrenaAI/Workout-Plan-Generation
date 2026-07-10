"""
Single entry point for the Tamreena AI API.

Run:
    python main.py

Equivalent to:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8001")),
        reload=True,
    )
