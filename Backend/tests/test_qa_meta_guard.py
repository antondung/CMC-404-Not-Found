"""Guard: non-legal meta questions must not cite law (e.g. 'bạn là model gì' ≠ TT xe)."""
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
    # Even if somehow reached, "model" alone must not keep car-tax clauses.
    assert be2_service._select_context(ctx, "bạn là model gì") == []


def test_meta_assistant_answer_has_no_citations():
    out = QAService._meta_assistant_answer(
        question="bạn là model gì", audience="citizen", as_of="2026-07-18"
    )
    assert out["citations"] == []
    assert "LexSocial" in out["answer"]
    assert out["refuse_reason"] == ["non_legal_meta_question"]
