from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar, Token
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="unknown")


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_var.get()


def set_request_id(req_id: str | None = None) -> Token[str]:
    """Set a request ID into context var and return the token."""
    if not req_id:
        req_id = str(uuid.uuid4())
    return request_id_var.set(req_id)


def reset_request_id(token: Token[str]) -> None:
    """Reset the request ID context var using token."""
    request_id_var.reset(token)


def setup_logging(level: str = "INFO") -> None:
    """Configure basic structured logging for the backend."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except (OSError, ValueError):
                pass
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] [req:%(request_id)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    # Add a filter or factory to inject request_id into records if not present
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old_factory(*args, **kwargs)
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return record

    logging.setLogRecordFactory(record_factory)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with injected context capabilities."""
    return logging.getLogger(name)
