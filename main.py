"""
Single entry point for the Tamreena AI API.

Run:
    python main.py

Equivalent to:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Binds 0.0.0.0 (all network interfaces) by default, not just loopback --
needed for the mobile app (physical device, or `expo start --web` in a
browser, a different origin/port) to reach this over the LAN. Override via
HOST/PORT in .env if you want it restricted to loopback-only.
"""

import os

import uvicorn

import config  # noqa: F401 -- side effect: loads .env, so HOST/PORT below can actually come from it, not just a real OS env var set before this process started

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8001")),
        reload=True,
    )
