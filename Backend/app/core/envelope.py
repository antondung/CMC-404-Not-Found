from __future__ import annotations

from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseMeta(BaseModel):
    request_id: str = Field(..., description="Unique request correlation ID")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Processing latency in milliseconds")


class ApiResponse(BaseModel, Generic[T]):
    ok: bool = Field(default=True, description="Success status")
    data: T | None = Field(default=None, description="Payload data")
    meta: ResponseMeta = Field(..., description="Metadata including request_id and latency")
    warnings: list[str] = Field(default_factory=list, description="List of non-fatal warning messages")


def success_response(
    data: Any = None,
    *,
    request_id: str = "unknown",
    latency_ms: float = 0.0,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Create a standardized success response dictionary."""
    return {
        "ok": True,
        "data": data if data is not None else {},
        "meta": {
            "request_id": request_id,
            "latency_ms": round(latency_ms, 2),
        },
        "warnings": warnings or [],
    }


def error_response(
    message: str,
    *,
    request_id: str = "unknown",
    latency_ms: float = 0.0,
    details: dict[str, Any] | None = None,
    code: str = "error",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Create a standardized error response dictionary."""
    err_data = {
        "code": code,
        "message": message,
    }
    if details:
        err_data["details"] = details

    return {
        "ok": False,
        "data": err_data,
        "meta": {
            "request_id": request_id,
            "latency_ms": round(latency_ms, 2),
        },
        "warnings": warnings or [],
    }
