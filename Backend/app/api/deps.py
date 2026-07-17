from __future__ import annotations

import os
from typing import Any
from fastapi import Depends
from app.config import BE2Config, get_config
from app.core.security import Role, UserToken, get_current_user, require_admin, require_roles
from app.adapters.neo4j_social import Neo4jSocialRepository
from app.adapters.postgres_content import PostgresContentRepository
from app.adapters.qdrant_vector import QdrantVectorClient
from app.intelligence.llm_router import LLMRouter

# Global lazy connections / pools
_db_pool: Any | None = None
_neo4j_driver: Any | None = None
_qdrant_client: Any | None = None
_redis_pool: Any | None = None
_llm_router: LLMRouter | None = None


class FakeAsyncConnection:
    """Fallback connection for testing/dev when Postgres is offline."""
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        if "INSERT INTO briefs" in query:
            return {"id": "brief-fake-001"}
        if "INSERT INTO suggestions" in query:
            return {"id": "suggest-fake-001"}
        if "SELECT id, payload_json FROM alerts" in query:
            return {"id": args[0][0] if args and args[0] else "alert-fake-001", "payload_json": '{"alert_id": "a-1", "severity": "high", "status": "open"}'}
        return None
    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        return []
    async def execute(self, query: str, *args: Any) -> str:
        return "OK"


class FakeAsyncPool:
    """Mock asyncpg pool for dev/test when DB is not reachable."""
    def acquire(self):
        return FakeAsyncConnection()
    async def execute(self, query: str, *args: Any) -> str:
        return "OK"
    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        return []
    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        return None


class FakeNeo4jSession:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    async def run(self, query: str, **kwargs: Any):
        class FakeCursor:
            async def single(self):
                if "MATCH (k:Khoan" in query and "RETURN k.noi_dung" in query:
                    kid = kwargs.get("khoan_id", "15/2020/ND-CP::D1.K1")
                    return {"noi_dung": f"Người nộp thuế phải kê khai đúng hạn theo quy định tại Khoản {kid}."}
                if "MATCH path = (seed)-[" in query:
                    return None
                return {"bai_dang_id": f"{kwargs.get('platform', 'fb')}:{kwargs.get('external_id', '1')}", "alert_id": kwargs.get("alert_id", "alert-1")}
            async def consume(self):
                pass
            async def __aiter__(self):
                if "MATCH (k:Khoan" in query:
                    yield {"k": {"khoan_id": kwargs.get("khoan_id", "k1"), "noi_dung": "Quy định nguyên văn mẫu trong Neo4j."}}
        return FakeCursor()


class FakeNeo4jDriver:
    def session(self, **kwargs: Any):
        return FakeNeo4jSession()
    async def close(self):
        pass


class FakeQdrantClient:
    async def get_collection(self, collection: str) -> dict[str, Any]:
        return {"vectors": {"size": 1024, "distance": "Cosine"}}
    async def search(self, collection_name: str, query_vector: list[float], limit: int, query_filter: Any | None = None) -> list[Any]:
        class Hit:
            def __init__(self, id_val: str, score: float, payload: dict[str, Any]):
                self.id = id_val
                self.score = score
                self.payload = payload
        return [
            Hit("15/2020/ND-CP::D1.K1", 0.92, {"khoan_id": "15/2020/ND-CP::D1.K1", "van_ban_id": "vb-15-2020", "dieu": "1", "noi_dung": "Người nộp thuế phải kê khai đúng hạn."}),
            Hit("15/2020/ND-CP::D1.K2", 0.85, {"khoan_id": "15/2020/ND-CP::D1.K2", "van_ban_id": "vb-15-2020", "dieu": "1", "noi_dung": "Cơ quan quản lý thuế có trách nhiệm kiểm tra."}),
        ][:limit]
    async def upsert(self, collection_name: str, points: list[Any]) -> None:
        pass


class FakeLLMClient:
    async def complete(self, *, route: str, model: str, task: str, prompt: str, timeout_s: float) -> dict[str, Any]:
        if task == "qa":
            return {
                "answer": "Theo quy định hiện hành, người nộp thuế phải thực hiện kê khai đầy đủ và đúng thời hạn được quy định trong văn bản pháp luật liên quan.",
                "confidence": "high",
                "graph_paths": ["Khoan(15/2020/ND-CP::D1.K1) -> ChuThe(NguoiNopThue)", "Khoan(15/2020/ND-CP::D1.K1) <- THAO_LUAN_VE <- ChuDe(Thue)"],
            }
        return {"result": "ok"}
    async def health(self) -> dict[str, Any]:
        return {"ok": True}


async def get_db_pool() -> Any:
    global _db_pool
    if _db_pool is None:
        pg_url = os.getenv("DATABASE_URL")
        if pg_url:
            try:
                import asyncpg
                _db_pool = await asyncpg.create_pool(pg_url)
            except Exception:
                _db_pool = FakeAsyncPool()
        else:
            _db_pool = FakeAsyncPool()
    return _db_pool


async def get_neo4j_driver() -> Any:
    global _neo4j_driver
    if _neo4j_driver is None:
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        try:
            from neo4j import AsyncGraphDatabase
            _neo4j_driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        except Exception:
            _neo4j_driver = FakeNeo4jDriver()
    return _neo4j_driver


async def get_qdrant_client() -> QdrantVectorClient:
    global _qdrant_client
    if _qdrant_client is None:
        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        try:
            from qdrant_client import AsyncQdrantClient
            raw_client = AsyncQdrantClient(url=url, timeout=5.0)
            _qdrant_client = QdrantVectorClient(raw_client)
        except Exception:
            _qdrant_client = QdrantVectorClient(FakeQdrantClient())
    return _qdrant_client


async def get_llm_router(config: BE2Config = Depends(get_config)) -> LLMRouter:
    global _llm_router
    if _llm_router is None:
        _llm_router = LLMRouter(config=config, client=FakeLLMClient())
    return _llm_router


async def get_postgres_repo(pool: Any = Depends(get_db_pool)) -> PostgresContentRepository:
    return PostgresContentRepository(pool=pool)


async def get_neo4j_repo(driver: Any = Depends(get_neo4j_driver)) -> Neo4jSocialRepository:
    return Neo4jSocialRepository(driver=driver)


# Re-export security dependencies for convenience
__all__ = [
    "Role",
    "UserToken",
    "get_current_user",
    "require_admin",
    "require_roles",
    "get_db_pool",
    "get_neo4j_driver",
    "get_qdrant_client",
    "get_llm_router",
    "get_postgres_repo",
    "get_neo4j_repo",
]
