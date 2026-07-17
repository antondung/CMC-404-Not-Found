from __future__ import annotations

import json
import logging
import time
from typing import Any, Literal
import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError as PydanticValidationError
from app.config import BE2Config, get_config
from app.exceptions import ContractMissingError, ExternalServiceError, ValidationError

logger = logging.getLogger(__name__)
RouteName = Literal["local", "large"]

LOCAL_TASKS = {"parse_light", "extract_short"}
LARGE_TASKS = {"ner_re_complex", "rerank", "qa", "brief", "suggest"}
CONTEXT_REQUIRED_TASKS = {"qa", "brief", "suggest"}


def decide_route(task: str, complexity: str) -> RouteName:
    if task in LOCAL_TASKS or complexity == "low":
        return "local"
    if task in LARGE_TASKS or complexity in {"medium", "high"}:
        return "large"
    return "large"


def _schema_adapter(schema: type[BaseModel] | dict) -> TypeAdapter[Any] | None:
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return TypeAdapter(schema)
    return None


def _validate_output(data: Any, schema: type[BaseModel] | dict) -> dict:
    adapter = _schema_adapter(schema)
    if adapter is not None:
        value = adapter.validate_python(data)
        return value.model_dump() if isinstance(value, BaseModel) else dict(value)
    if not isinstance(data, dict):
        raise ValidationError("LLM output must be JSON object")
    required = schema.get("required", []) if isinstance(schema, dict) else []
    missing = [key for key in required if key not in data]
    if missing:
        raise ValidationError("LLM output missing required fields", details={"missing": missing})
    return data


class LLMRouter:
    def __init__(self, config: BE2Config | None = None, client: Any | None = None) -> None:
        self.config = config or get_config()
        self.client = client

    async def complete(self, task: str, prompt: str, schema: type[BaseModel] | dict, complexity: str) -> dict:
        if not task or not prompt:
            raise ValidationError("task and prompt are required")
        if task in CONTEXT_REQUIRED_TASKS and "retrieved_context" not in prompt:
            raise ContractMissingError("retrieved_context is required for QA/brief/suggest tasks")
        route = decide_route(task, complexity)
        model = self.config.llm_local_model if route == "local" else self.config.llm_large_model
        timeout = self.config.llm_local_timeout_s if route == "local" else self.config.llm_large_timeout_s
        retry_count = 0
        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(self.config.llm_retry_count + 1):
            retry_count = attempt
            try:
                raw = await self._call_gateway(route=route, model=model, task=task, prompt=prompt, timeout_s=timeout)
                payload = raw.get("output", raw)
                if isinstance(payload, str):
                    payload = json.loads(payload)
                result = _validate_output(payload, schema)
                self._audit(task, model, route, started, retry_count, "ok", raw)
                return result
            except (json.JSONDecodeError, PydanticValidationError, ValidationError) as exc:
                last_error = exc
                if attempt >= self.config.llm_retry_count:
                    self._audit(task, model, route, started, retry_count, "needs_review", {})
                    return {"status": "needs_review", "needs_review": True, "error": "schema_validation_failed"}
                prompt = f"Repair output to match schema only. Do not add facts. Original task: {task}.\n{prompt}"
        raise ExternalServiceError("LLM router failed", details={"error": str(last_error)})

    async def _call_gateway(self, *, route: str, model: str, task: str, prompt: str, timeout_s: float) -> dict[str, Any]:
        if self.client is not None:
            return await self.client.complete(route=route, model=model, task=task, prompt=prompt, timeout_s=timeout_s)
        if self.config.llm_gateway_url is None:
            raise ContractMissingError("BE2_LLM_GATEWAY_URL is required without injected LLM client")
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            try:
                response = await client.post(str(self.config.llm_gateway_url), json={"route": route, "model": model, "task": task, "prompt": prompt})
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                raise ExternalServiceError("LLM gateway request failed", details={"route": route, "task": task}) from exc

    async def health(self) -> dict[str, Any]:
        if self.client is not None:
            return await self.client.health()
        if self.config.llm_gateway_url is None:
            return {"ok": False, "reason": "missing_gateway_url"}
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(str(self.config.llm_gateway_url).rstrip("/") + "/health")
            return {"ok": response.is_success, "status_code": response.status_code}

    def _audit(self, task: str, model: str, route: str, started: float, retry_count: int, status: str, raw: dict[str, Any]) -> None:
        logger.info("llm_audit", extra={"task": task, "model": model, "route": route, "latency_ms": int((time.perf_counter() - started) * 1000), "retry_count": retry_count, "result_status": status, "token_usage": raw.get("token_usage")})


_default_router: LLMRouter | None = None


async def llm_complete(task: str, prompt: str, schema: type[BaseModel] | dict, complexity: str) -> dict:
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter()
    return await _default_router.complete(task, prompt, schema, complexity)
