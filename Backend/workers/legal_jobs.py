"""Top-level workers/legal_jobs.py — DEPRECATED stub.

All real worker logic has moved to ``app/workers/legal_jobs.py``.
This file is kept for backward compatibility with any external references
but simply re-exports from the canonical location.
"""
from app.workers.legal_jobs import (  # noqa: F401
    legal_ingest,
    legal_parse,
    legal_extract,
    legal_diff,
)
