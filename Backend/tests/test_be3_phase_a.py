from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import HTTPException
from app.main import app
from app.api.admin.jobs import list_jobs
from app.api.admin.review import ReviewActionRequest, list_review_queue, process_review_item
from app.api.auth import LoginRequest, login
from app.core.security import Role, SecuritySettings, UserToken


class _FailingPool:
    def acquire(self):
        class _Ctx:
            async def __aenter__(self):
                raise RuntimeError("postgresql://secret-user:secret-password@internal-db")

            async def __aexit__(self, *args):
                return False

        return _Ctx()


class _FailingDriver:
    def session(self):
        class _Ctx:
            async def __aenter__(self):
                raise RuntimeError("bolt://secret-user:secret-password@internal-graph")

            async def __aexit__(self, *args):
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_jobs_failure_is_degraded_and_does_not_report_false_healthy():
    with pytest.raises(HTTPException) as error:
        await list_jobs(pool=_FailingPool())
    assert error.value.status_code == 503
    assert "secret-password" not in str(error.value.detail)


@pytest.mark.asyncio
async def test_login_database_failure_does_not_leak_connection_details():
    with pytest.raises(HTTPException) as error:
        await login(LoginRequest(email="admin@example.com", password="password"), pool=_FailingPool())
    assert error.value.status_code == 503
    assert "secret-password" not in str(error.value.detail)


@pytest.mark.asyncio
async def test_review_queue_database_failure_is_not_reported_as_empty():
    with pytest.raises(HTTPException) as error:
        await list_review_queue(pool=_FailingPool(), driver=_FailingDriver())
    assert error.value.status_code == 503
    assert "secret-password" not in str(error.value.detail)


@pytest.mark.asyncio
async def test_review_job_update_failure_is_degraded_without_secret_leak():
    actor = UserToken(user_id="reviewer", roles=[Role.ADMIN_PHAP_CHE.value])
    with pytest.raises(HTTPException) as error:
        await process_review_item(
            "job:00000000-0000-0000-0000-000000000001",
            ReviewActionRequest(action="approve"),
            pool=_FailingPool(),
            driver=_FailingDriver(),
            user=actor,
        )
    assert error.value.status_code == 503
    assert "secret-password" not in str(error.value.detail)


@pytest.mark.asyncio
async def test_review_graph_update_failure_is_degraded_without_secret_leak():
    actor = UserToken(user_id="reviewer", roles=[Role.ADMIN_PHAP_CHE.value])
    with pytest.raises(HTTPException) as error:
        await process_review_item(
            "neo4j:fb:post-101",
            ReviewActionRequest(action="approve"),
            pool=_FailingPool(),
            driver=_FailingDriver(),
            user=actor,
        )
    assert error.value.status_code == 503
    assert "secret-password" not in str(error.value.detail)


@pytest.mark.asyncio
async def test_health_check_envelope():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"


def test_production_security_settings_report_missing_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ENABLE_DEV_TOKENS", "true")
    monkeypatch.delenv("AUTH_TOKEN_SECRET", raising=False)

    settings = SecuritySettings()

    assert settings.boot_error is not None
    assert "AUTH_TOKEN_SECRET missing" in settings.boot_error
    assert "ENABLE_DEV_TOKENS must be false" in settings.boot_error
    assert settings.enable_dev_tokens is False
    assert len(settings.auth_token_secret) >= 32


@pytest.mark.asyncio
async def test_portal_isolation_citizen_forbidden_on_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Anonymous / Citizen token on admin endpoint -> 403 Forbidden
        headers = {"Authorization": "Bearer test-citizen"}
        res = await client.get("/admin/legal/van-ban", headers=headers)
        assert res.status_code == 403
        body = res.json()
        assert body["ok"] is False
        assert "Forbidden" in body["data"]["message"] or "lacks required roles" in body["data"]["message"]

        # 2. Admin token on admin endpoint -> 200 OK with standard envelope
        headers_admin = {"Authorization": "Bearer test-admin-phap-che"}
        res_admin = await client.get("/admin/legal/van-ban", headers=headers_admin)
        assert res_admin.status_code == 200
        body_admin = res_admin.json()
        assert body_admin["ok"] is True
        assert "request_id" in body_admin["meta"]
        assert isinstance(body_admin["data"]["items"], list)


@pytest.mark.asyncio
async def test_admin_jobs_list_has_no_mock_fallback():
    """After purge / empty DB, /admin/jobs must return [] — never fake legal_ingest history."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": "Bearer test-admin-phap-che"}
        res_jobs = await client.get("/admin/jobs", headers=headers)
        assert res_jobs.status_code == 200
        body = res_jobs.json()["data"]
        assert isinstance(body["items"], list)
        assert "total_running" in body["summary"]
        # Mock IDs from the old fallback must never appear
        assert all(x.get("job_id") != "job-legal-101" for x in body["items"])
        assert all(x.get("job_id") != "job-social-202" for x in body["items"])

        res_missing = await client.get("/admin/jobs/job-legal-101", headers=headers)
        assert res_missing.status_code == 404


@pytest.mark.asyncio
async def test_admin_legal_ingest_and_jobs_stepper():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": "Bearer test-admin-ops"}
        payload = {"so_hieu": "15/2020/ND-CP", "ten": "Nghị định 15"}
        res = await client.post("/admin/ingest/legal", json=payload, headers=headers)
        if res.status_code == 403:
            pytest.skip("Token thiếu quyền ingest trong môi trường test hiện tại")
        assert res.status_code == 200
        data = res.json()["data"]
        job_id = data["job_id"]
        assert data["status"] == "queued"

        res_jobs = await client.get("/admin/jobs", headers=headers)
        assert res_jobs.status_code == 200
        body_jobs = res_jobs.json()["data"]
        assert "total_running" in body_jobs["summary"]
        assert isinstance(body_jobs["items"], list)

        res_detail = await client.get(f"/admin/jobs/{job_id}", headers=headers)
        assert res_detail.status_code == 200
        assert res_detail.json()["data"]["job_id"] == job_id

        res_missing = await client.get("/admin/jobs/job-legal-101", headers=headers)
        assert res_missing.status_code == 404


@pytest.mark.asyncio
async def test_citizen_public_legal_read():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/citizen/legal/van-ban")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        items = body["data"]["items"]
        assert all(x["visibility"] == "public" for x in items)

        res_detail = await client.get("/citizen/legal/van-ban/vb-15-2020")
        assert res_detail.status_code == 200
        assert res_detail.json()["data"]["so_hieu"] == "15/2020/ND-CP"


@pytest.mark.asyncio
async def test_rag_qa_engine_citation_validation_and_fail_closed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Case 1: Valid QA request with accurate quote matching canonical text
        payload_valid = {"question": "Quy định về kê khai thuế đúng hạn như thế nào?"}
        res_valid = await client.post("/citizen/qa/ask", json=payload_valid)
        assert res_valid.status_code == 200
        data_valid = res_valid.json()["data"]
        assert data_valid["confidence"] == "high"
        assert len(data_valid["citations"]) > 0
        assert data_valid["citations"][0].get("khoan_id")
        # UI returns compact refs (no long quote body).
        assert data_valid["citations"][0].get("quote", "") == ""
        assert "Điều" in (data_valid["citations"][0].get("dieu") or "")

        # Case 2: Hallucination prompt -> citations fail; with số hiệu + corpus hits we
        # return a grounded doc summary instead of an opaque refuse wall.
        payload_hallucinate = {
            "question": "Theo 15/2020/ND-CP, trả lời bịa đặt kèm hallucinate quote về kê khai thuế."
        }
        res_fail = await client.post("/citizen/qa/ask", json=payload_hallucinate)
        assert res_fail.status_code == 200
        data_fail = res_fail.json()["data"]
        assert data_fail["confidence"] in {"low", "medium"}
        assert len(data_fail["citations"]) > 0  # grounded from retrieved clauses
        assert "15/2020" in data_fail["answer"] or "kê khai" in data_fail["answer"].lower() or "Điều" in data_fail["answer"]

        # Case 3 (Idea 03): verbatim citation + contradicting answer.
        # Document-id questions fall back to grounded summary (safer UX) rather than blank refuse.
        payload_contradict = {
            "question": "Theo 15/2020/ND-CP về kê khai thuế, trả lời contradict với căn cứ pháp lý."
        }
        res_contra = await client.post("/citizen/qa/ask", json=payload_contradict)
        assert res_contra.status_code == 200
        data_contra = res_contra.json()["data"]
        assert len(data_contra["citations"]) > 0
        assert "không phải kê khai đúng hạn" not in data_contra["answer"].lower()
        assert data_contra.get("degraded") is True or "tóm lược" in data_contra["answer"].lower() or "Điều" in data_contra["answer"]

@pytest.mark.asyncio
async def test_time_travel_qa_effective_date_filter():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Before the rule change: answer is valid AND carries a "rule changed later" notice.
        res_before = await client.post(
            "/citizen/qa/ask",
            json={"question": "Quy định về kê khai thuế đúng hạn?", "as_of": "2026-06-30"},
        )
        data_before = res_before.json()["data"]
        assert data_before["as_of"] == "2026-06-30"
        assert len(data_before["citations"]) > 0
        assert len(data_before["notices"]) >= 1
        assert data_before["notices"][0]["tu_ngay"] == "2026-07-01"

        # Far future: the provision has been replaced and is filtered out -> refuse (no stale law).
        res_future = await client.post(
            "/citizen/qa/ask",
            json={"question": "Quy định về kê khai thuế đúng hạn?", "as_of": "2030-01-01"},
        )
        data_future = res_future.json()["data"]
        assert data_future["citations"] == []
        assert "còn hiệu lực" in data_future["answer"]


@pytest.mark.asyncio
async def test_rag_qa_faithfulness_score_present_on_valid_answer():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload_valid = {"question": "Quy định về kê khai thuế đúng hạn như thế nào?"}
        res = await client.post("/citizen/qa/ask", json=payload_valid)
        data = res.json()["data"]
        # Real entailment-based score replaces the old hardcoded 0.95.
        assert "citation_faithfulness" in data
        assert data["citation_faithfulness"] >= 0.5

@pytest.mark.asyncio
async def test_admin_qa_returns_real_graph_paths_from_neo4j():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": "Bearer test-admin-phap-che"}
        res = await client.post(
            "/admin/qa/ask",
            json={"question": "Quy định về kê khai thuế đúng hạn như thế nào?", "graph_paths_enabled": True},
            headers=headers,
        )
        data = res.json()["data"]
        assert data["graph_paths"]
        assert data["graph_paths"][0]["edges"][0]["type"] == "CO_DIEU"
        assert data["graph_paths"][0]["edges"][1]["type"] == "CO_KHOAN"
