"""Shared legal-ingest orchestration used by BOTH the synchronous API path
(`LegalDiffFacade.ingest_document`) and the async Arq worker (`workers.legal_jobs.legal_ingest`).

Flow: raw text/URL -> LegalParser (Điều/Khoản/Điểm) -> canonical IDs -> Neo4j upsert.
Keeping it in one place guarantees the sync and async paths stay identical.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.adapters.neo4j_legal import Neo4jLegalRepository
from app.pipelines.legal.parser import LegalParser
from app.pipelines.legal.normalize import normalize_so_hieu, generate_van_ban_id, generate_khoan_id

logger = logging.getLogger(__name__)


async def _resolve_text(url_or_content: str | None) -> str:
    """Return raw legal text: fetch it if a URL was given, else treat the value as the text."""
    if not url_or_content:
        return ""
    value = url_or_content.strip()
    if value.lower().startswith(("http://", "https://")):
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(value)
                resp.raise_for_status()
                return resp.text
        except Exception as exc:  # noqa: BLE001 - network failures degrade to "no content"
            logger.warning("legal_ingest: failed to fetch URL %s: %s", value, exc)
            return ""
    return value


def _build_tree(so_hieu_norm: str, parsed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach canonical dieu_id/khoan_id to the parser tree for Neo4j MERGE."""
    dieu_list: list[dict[str, Any]] = []
    for dieu in parsed:
        dieu_so = dieu.get("so", "")
        dieu_id = f"{so_hieu_norm}::D{dieu_so}"
        khoan_list = []
        for khoan in dieu.get("khoan_list", []):
            khoan_so = khoan.get("so", "")
            khoan_list.append(
                {
                    "khoan_id": generate_khoan_id(so_hieu_norm, dieu_so, khoan_so),
                    "so": str(khoan_so),
                    "noi_dung": khoan.get("noi_dung", "").strip(),
                }
            )
        dieu_list.append(
            {
                "dieu_id": dieu_id,
                "so": str(dieu_so),
                "tieu_de": dieu.get("tieu_de", "").strip(),
                "khoan_list": khoan_list,
            }
        )
    return dieu_list


async def run_legal_ingest(driver: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Parse the document text and upsert its Điều/Khoản structure into Neo4j.

    Returns a status dict: {status, vb_id, dieu_count, khoan_count, needs_review, message}.
    - status="success" when at least one Điều was written,
    - status="needs_review" when text was present but no structure could be parsed,
    - status="queued" when no content was supplied (awaiting file upload / async fetch).
    """
    so_hieu = payload.get("so_hieu", "")
    so_hieu_norm = normalize_so_hieu(so_hieu) if so_hieu else ""
    ngay_ban_hanh = payload.get("ngay_ban_hanh", "") or ""
    vb_id = generate_van_ban_id(so_hieu_norm, ngay_ban_hanh)

    text = await _resolve_text(payload.get("url_or_content"))
    if not text.strip():
        return {
            "status": "queued",
            "vb_id": vb_id,
            "dieu_count": 0,
            "khoan_count": 0,
            "needs_review": False,
            "message": "Chưa có nội dung để bóc tách; job ở hàng đợi chờ file/worker.",
        }

    parser = LegalParser()
    parsed_tree, needs_review = parser.parse_text(text)
    dieu_list = _build_tree(so_hieu_norm, parsed_tree)

    doc = {
        "vb_id": vb_id,
        "so_hieu": so_hieu_norm,
        "ten": payload.get("ten"),
        "loai": payload.get("loai"),
        "ngay_ban_hanh": ngay_ban_hanh or None,
        "ngay_hieu_luc": payload.get("ngay_hieu_luc") or None,
        "trang_thai": payload.get("trang_thai", "hieu_luc"),
        "visibility": payload.get("visibility", "public"),
        "co_quan_ban_hanh": payload.get("co_quan_ban_hanh"),
        "dieu_list": dieu_list,
    }

    write_res = await Neo4jLegalRepository(driver).upsert_van_ban(doc)
    khoan_count = write_res.get("khoan_count", 0)

    if not dieu_list:
        return {
            "status": "needs_review",
            "vb_id": vb_id,
            "dieu_count": 0,
            "khoan_count": 0,
            "needs_review": True,
            "message": "Không bóc tách được Điều nào (layout lỗi hoặc cần LLM fallback).",
        }

    return {
        "status": "success",
        "vb_id": vb_id,
        "dieu_count": len(dieu_list),
        "khoan_count": khoan_count,
        "needs_review": needs_review,
        "message": f"Đã số hóa {len(dieu_list)} Điều / {khoan_count} Khoản vào đồ thị.",
    }
