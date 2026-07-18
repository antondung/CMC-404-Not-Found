"""Guard: non-legal meta + topic anchors (TNCN ≠ thuế nhập khẩu example)."""
from __future__ import annotations

import pytest

from app.services.qa_service import QAService
import be2_service


def test_meta_model_question_detected():
    assert QAService._is_non_legal_meta_question("bạn là model gì")
    assert QAService._is_non_legal_meta_question("Ban la model gi?")
    assert QAService._is_non_legal_meta_question("what model are you")
    assert QAService._is_non_legal_meta_question("xin chào")
    assert not QAService._is_non_legal_meta_question("mức phạt nồng độ cồn")
    assert not QAService._is_non_legal_meta_question("model năm sản xuất xe nhập khẩu")


def test_be2_meta_gate_and_select_context():
    assert be2_service._is_non_legal_meta_question("bạn là model gì")
    ctx = [
        ("116/2011/TT-BTC::D2.K1", "phải khai báo chi tiết ... model năm, các ký hiệu model khác"),
        ("116/2011/TT-BTC::D4.K1", "không phân biệt ... model năm ..."),
    ]
    assert be2_service._select_context(ctx, "bạn là model gì") == []


def test_meta_assistant_answer_has_no_citations():
    out = QAService._meta_assistant_answer(
        question="bạn là model gì", audience="citizen", as_of="2026-07-18"
    )
    assert out["citations"] == []
    assert "LexSocial" in out["answer"]
    assert out["refuse_reason"] == ["non_legal_meta_question"]


def test_gambling_tncn_does_not_match_import_tax_example():
    q = "tôi chơi cờ bạc 100 triệu cần nộp thuế thu nhập cá nhân không"
    bad = (
        "Máy móc... đã nộp 100 triệu đồng tiền thuế nhập khẩu, sau 03 năm... "
        "60% x 100 triệu đồng = 60 triệu đồng."
    )
    good = "Thu nhập từ hoạt động kinh doanh trò chơi có thưởng thuộc thuế thu nhập cá nhân."
    assert QAService._anchor_phrases(q)
    assert QAService._topic_relevance(q, bad) == 0.0
    assert QAService._topic_relevance(q, f"xx {good}") >= 0.34
    assert be2_service._topic_relevance(q, bad) == 0.0
    assert be2_service._select_context([("38/2015/TT-BTC::D114.K9", bad)], q) == []


def test_ca_do_tax_principle_is_criminal_not_admin_procedure():
    q = "tôi chơi cá độ được 100 triệu cần nộp thuế gì"
    ans = QAService._principle_fallback_answer(q)
    low = ans.lower()
    assert "hình sự" in ans or "hành chính" in ans
    assert "tncn" in low or "thu nhập cá nhân" in low
    assert "thủ tục hành chính công dân" not in low
    assert "hồ sơ theo mẫu" not in low
    # Still block unrelated import-tax example figures
    bad = (
        "Máy móc... đã nộp 100 triệu đồng tiền thuế nhập khẩu, sau 03 năm... "
        "60% x 100 triệu đồng = 60 triệu đồng."
    )
    assert QAService._topic_relevance(q, bad) == 0.0
    good_tncn = "Thu nhập chịu thuế thu nhập cá nhân bao gồm các khoản thu nhập từ kinh doanh và tiền lương."
    assert QAService._topic_relevance(q, good_tncn) > 0.0


def test_cccd_principle_fallback_not_empty():
    q = "Thủ tục làm CCCD gắn chip?"
    ans = QAService._principle_fallback_answer(q)
    assert "CCCD" in ans or "Căn cước" in ans
    assert "Công an" in ans
    assert "Giới hạn" in ans
    tax = "Mức thu lệ phí trước bạ đối với nhà đất theo Thông tư thuế..."
    assert QAService._topic_relevance(q, tax) == 0.0
    assert be2_service._anchor_phrases(q)


@pytest.mark.asyncio
async def test_unverified_without_router_returns_cccd_guidance():
    svc = QAService(llm_router=None)
    out = await svc._unverified_ai_answer(
        question="Thủ tục làm CCCD gắn chip?",
        audience="citizen",
        as_of="2026-07-18",
        notices=[],
        reason="No legal candidates",
    )
    assert out["unverified"] is True
    assert out["citations"] == []
    assert "Công an" in out["answer"]
    assert "Chưa có dữ liệu pháp lý được hệ thống xác thực" not in out["answer"]
