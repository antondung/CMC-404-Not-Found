"""Guard: non-legal meta + topic anchors (TNCN ≠ thuế nhập khẩu example)."""
from __future__ import annotations

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
