"""Railway / Docker entry for BE2 intelligence gateway."""
from __future__ import annotations

import logging
import os
import traceback

from fastapi import FastAPI
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("railway_entry_be2")

app = FastAPI(title="LexSocial BE2 boot", version="1.0.0")
_boot_error: str | None = None


@app.get("/health")
@app.get("/healthz")
async def health() -> dict:
    return {
        "ok": True,
        "status": "ok" if _boot_error is None else "degraded",
        "service": "be2-intelligence",
        "boot_error": _boot_error,
    }


try:
    from be2_service import app as real_app

    app = real_app
    log.info("be2_service loaded successfully")
except Exception as exc:  # noqa: BLE001
    _boot_error = f"{type(exc).__name__}: {exc}"
    log.error("Failed to load be2_service — serving health-only\n%s", traceback.format_exc())

    @app.get("/")
    async def root_fail() -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "message": "BE2 failed to boot", "error": _boot_error},
        )
