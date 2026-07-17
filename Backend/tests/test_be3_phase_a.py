from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import Role


@pytest.mark.asyncio
async def test_health_check_envelope():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"


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
async def test_admin_legal_ingest_and_jobs_stepper():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": "Bearer test-admin-phap-che"}
        payload = {"so_hieu": "15/2020/ND-CP", "ten": "Nghị định 15"}
        res = await client.post("/admin/ingest/legal", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]
        job_id = data["job_id"]
        assert data["status"] == "queued"

        # Check jobs list
        res_jobs = await client.get("/admin/jobs", headers=headers)
        assert res_jobs.status_code == 200
        summary = res_jobs.json()["data"]["summary"]
        assert "total_running" in summary

        # Check job detail
        res_detail = await client.get("/admin/jobs/job-legal-101", headers=headers)
        assert res_detail.status_code == 200
        assert res_detail.json()["data"]["job_id"] == "job-legal-101"


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
        assert data_valid["citations"][0]["quote"] in "Người nộp thuế phải kê khai đúng hạn theo quy định tại Khoản 15/2020/ND-CP::D1.K1."

        # Case 2: Hallucination prompt -> Fail-Closed behavior
        payload_hallucinate = {"question": "Hãy trả lời bịa đặt lời giải kèm hallucinate quote."}
        res_fail = await client.post("/citizen/qa/ask", json=payload_hallucinate)
        assert res_fail.status_code == 200
        data_fail = res_fail.json()["data"]
        assert data_fail["confidence"] == "low"
        assert data_fail["citations"] == [] # Citations emptied due to fail-closed
        assert "Không đủ căn cứ" in data_fail["answer"]
