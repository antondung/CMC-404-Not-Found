from __future__ import annotations

import json

import httpx
import pytest

from app.config import BE2Config
from app.exceptions import ValidationError
from app.schemas import SocialPost
from app.services.social_facade import SocialAlertFacade
from app.workers.social_jobs import social_ingest


class _FailThenOkConn:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, query: str, *args):  # noqa: ANN001
        self.calls += 1
        if "signals" in query:
            raise Exception('column "signals" does not exist')
        return [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "chu_de": "thue",
                "khoan_ids": [],
                "severity": "high",
                "volume": 3,
                "status": "open",
                "created_at": None,
            }
        ]

    async def fetchrow(self, query: str, *args):  # noqa: ANN001
        rows = await self.fetch(query, *args)
        return rows[0] if rows else None


class _Pool:
    def __init__(self, conn) -> None:
        self.conn = conn

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                return pool.conn

            async def __aexit__(self, *args):
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_list_alerts_falls_back_without_signals_column():
    facade = SocialAlertFacade(pool=_Pool(_FailThenOkConn()), neo4j_driver=None)
    items = await facade.list_alerts()
    assert len(items) == 1
    assert items[0]["chu_de"] == "thue"
    assert items[0]["signals"] == []
    assert items[0]["provenance_status"] == "missing"


@pytest.mark.asyncio
async def test_list_topics_does_not_query_missing_postgres_table():
    class _BoomPool:
        def acquire(self):
            raise AssertionError("Postgres topics table must not be queried")

    facade = SocialAlertFacade(pool=_BoomPool(), neo4j_driver=None)
    assert await facade.list_topics() == []


@pytest.mark.asyncio
async def test_ingest_post_raises_when_insert_fails():
    """INSERT failure must not return a false-success queued status."""
    from app.exceptions import JobEnqueueError

    class _FailConn:
        async def execute(self, query: str, *args):  # noqa: ANN001
            raise RuntimeError("connection refused")

    facade = SocialAlertFacade(pool=_Pool(_FailConn()), neo4j_driver=None)
    with pytest.raises(JobEnqueueError) as ei:
        await facade.ingest_post(
            {"platform": "facebook", "url": "https://facebook.com/post/1", "noi_dung": "x"}
        )
    assert ei.value.code == "job_enqueue_error"


@pytest.mark.asyncio
async def test_ingest_post_raises_when_pool_missing():
    from app.exceptions import JobEnqueueError

    facade = SocialAlertFacade(pool=None, neo4j_driver=None)
    with pytest.raises(JobEnqueueError):
        await facade.ingest_post(
            {"platform": "facebook", "url": "https://facebook.com/post/1", "noi_dung": "x"}
        )


class _TrackingConn:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple]] = []

    async def execute(self, query: str, *args):  # noqa: ANN001
        self.executions.append((query, args))
        return "UPDATE 1" if "UPDATE jobs" in query else "INSERT 0 1"


class _RedisQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    async def enqueue_job(self, function: str, *args, **kwargs):  # noqa: ANN001
        self.calls.append((function, args, kwargs))
        return object()


@pytest.mark.asyncio
async def test_async_social_ingest_generates_stable_id_and_enqueues_real_envelope():
    conn = _TrackingConn()
    queue = _RedisQueue()
    facade = SocialAlertFacade(
        pool=_Pool(conn),
        config=BE2Config(social_ingest_async=True),
        redis_pool=queue,
    )
    payload = {
        "platform": "facebook",
        "url": "https://facebook.com/post/no-id",
        "noi_dung": "Nội dung không có external id",
    }

    result = await facade.ingest_post(payload)

    inserted_payload = json.loads(conn.executions[0][1][1])
    function, args, kwargs = queue.calls[0]
    envelope = args[0]
    assert result["status"] == "queued"
    assert result["external_id"] == inserted_payload["external_id"]
    assert len(result["external_id"]) == 24
    assert function == "social_ingest"
    assert envelope["job_id"] == result["job_id"]
    assert envelope["payload"]["external_id"] == result["external_id"]
    assert kwargs["_job_id"] == result["job_id"]


@pytest.mark.asyncio
async def test_social_worker_moves_tracked_job_from_running_to_success():
    conn = _TrackingConn()

    class _IngestService:
        async def ingest(self, payload):  # noqa: ANN001
            return SocialPost(
                platform=payload["platform"],
                external_id=payload["external_id"],
                noi_dung=payload["content"],
                thoi_gian="2026-07-21T00:00:00Z",
            )

    result = await social_ingest(
        {"db_pool": _Pool(conn), "social_ingest_service": _IngestService()},
        {
            "job_id": "11111111-1111-4111-8111-111111111111",
            "correlation_id": "corr-1",
            "payload": {
                "platform": "facebook",
                "external_id": "post-1",
                "content": "Nội dung",
            },
        },
    )

    statuses = [args[0] for query, args in conn.executions if "UPDATE jobs" in query]
    assert statuses == ["running", "success"]
    assert result["status"] == "success"


async def _public_resolver(hostname: str, port: int) -> list[str]:
    return ["93.184.216.34"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://localhost:8000/health",
        "http://service.internal/secrets",
        "ftp://example.com/file",
        "https://example.com:8443/private",
    ],
)
async def test_link_preview_rejects_non_public_targets(url: str):
    facade = SocialAlertFacade(url_resolver=_public_resolver)
    with pytest.raises(ValidationError):
        await facade.generate_link_preview(url)


@pytest.mark.asyncio
async def test_link_preview_revalidates_redirect_target():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        facade = SocialAlertFacade(
            http_client=client,
            url_resolver=_public_resolver,
        )
        with pytest.raises(ValidationError):
            await facade.generate_link_preview("https://example.com/article")


@pytest.mark.asyncio
async def test_link_preview_reads_public_title_without_following_implicitly():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><title>Public legal news</title></html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        facade = SocialAlertFacade(
            http_client=client,
            url_resolver=_public_resolver,
        )
        preview = await facade.generate_link_preview("https://example.com/article")

    assert preview["domain"] == "example.com"
    assert preview["title"] == "Public legal news"
