"""Railway / Docker entry for BE3.

Importing ``app.main`` can fail if env is incomplete. This wrapper always exposes
``/health`` so the edge proxy has something to talk to, then mounts the real API.
"""
from __future__ import annotations

import logging
import os
import traceback

from fastapi import FastAPI
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("railway_entry")

app = FastAPI(title="LexSocial BE3 boot", version="1.0.0")
_boot_error: str | None = None


@app.get("/health")
@app.get("/healthz")
async def health() -> dict:
    return {
        "status": "ok" if _boot_error is None else "degraded",
        "service": "be3-gateway",
        "boot_error": _boot_error,
    }


try:
    from app.main import app as real_app

    # Mount full API at root by replacing routes — prefer replacing the ASGI app.
    app = real_app
    log.info("BE3 app.main loaded successfully")
except Exception as exc:  # noqa: BLE001
    _boot_error = f"{type(exc).__name__}: {exc}"
    log.error("Failed to load app.main — serving health-only app\n%s", traceback.format_exc())

    @app.get("/")
    async def root_fail() -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "message": "BE3 failed to boot", "error": _boot_error},
        )


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT") or "8000")
    log.info("Starting uvicorn on 0.0.0.0:%s", port)
    uvicorn.run(
        "railway_entry:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
