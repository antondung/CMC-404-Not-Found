from __future__ import annotations

import asyncio
from typing import Any
import httpx
from pydantic import TypeAdapter
from app.config import BE2Config, get_config
from app.exceptions import ExternalServiceError, ValidationError

_MODEL_CACHE: dict[str, Any] = {}


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


class Embedder:
    def __init__(self, config: BE2Config | None = None, model: Any | None = None, http_client: httpx.AsyncClient | None = None) -> None:
        self.config = config or get_config()
        self._model = model
        self._http = http_client
        self._dimension: int | None = self.config.embedding_dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            raise ValidationError("texts must not be empty")
        normalized = [normalize_text(t) for t in texts]
        if any(not t for t in normalized):
            raise ValidationError("text item must not be empty")
        vectors: list[list[float]] = []
        for start in range(0, len(normalized), self.config.embedding_batch_size):
            batch = normalized[start : start + self.config.embedding_batch_size]
            batch_vectors = await asyncio.wait_for(self._embed_batch(batch), timeout=self.config.embedding_timeout_s)
            vectors.extend(batch_vectors)
        self._validate_vectors(vectors, len(normalized))
        return vectors

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        if self.config.embedding_provider == "tei":
            return await self._embed_tei(batch)
        return await self._embed_local(batch)

    async def _embed_tei(self, batch: list[str]) -> list[list[float]]:
        if self.config.tei_url is None:
            raise ValidationError("BE2_TEI_URL is required for TEI embedding provider")
        client = self._http or httpx.AsyncClient(timeout=self.config.embedding_timeout_s)
        close = self._http is None
        try:
            response = await client.post(str(self.config.tei_url), json={"inputs": batch})
            response.raise_for_status()
            data = response.json()
            raw = data.get("embeddings", data)
            return TypeAdapter(list[list[float]]).validate_python(raw)
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            raise ExternalServiceError("TEI embedding request failed", details={"provider": "tei"}) from exc
        finally:
            if close:
                await client.aclose()

    async def _embed_local(self, batch: list[str]) -> list[list[float]]:
        model = self._model or self._get_cached_model()
        vectors = await asyncio.to_thread(model.encode, batch, normalize_embeddings=True)
        return TypeAdapter(list[list[float]]).validate_python(vectors.tolist() if hasattr(vectors, "tolist") else vectors)

    def _get_cached_model(self) -> Any:
        if self.config.embedding_model not in _MODEL_CACHE:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ExternalServiceError("sentence-transformers is not installed") from exc
            _MODEL_CACHE[self.config.embedding_model] = SentenceTransformer(self.config.embedding_model)
        return _MODEL_CACHE[self.config.embedding_model]

    def _validate_vectors(self, vectors: list[list[float]], expected_count: int) -> None:
        if len(vectors) != expected_count:
            raise ValidationError("embedding vector count mismatch", details={"expected": expected_count, "actual": len(vectors)})
        dims = {len(v) for v in vectors}
        if len(dims) != 1:
            raise ValidationError("embedding vector dimension mismatch within batch", details={"dimensions": sorted(dims)})
        dim = dims.pop()
        if self._dimension is None:
            self._dimension = dim
        elif self._dimension != dim:
            raise ValidationError("embedding vector dimension mismatch", details={"expected": self._dimension, "actual": dim})

    async def health(self) -> dict[str, Any]:
        probe = await self.embed_texts(["health check"])
        return {"ok": True, "provider": self.config.embedding_provider, "dimension": len(probe[0])}


_default_embedder: Embedder | None = None


async def embed_texts(texts: list[str]) -> list[list[float]]:
    global _default_embedder
    if _default_embedder is None:
        _default_embedder = Embedder()
    return await _default_embedder.embed_texts(texts)
