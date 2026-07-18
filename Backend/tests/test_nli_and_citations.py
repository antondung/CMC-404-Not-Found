"""NLI numeric consistency + citation partial validation."""
from __future__ import annotations

import pytest

from app.intelligence.nli import NLIService, _numeric_consistency
from app.services.citation_validator import CitationValidator
from app.schemas import CandidateKhoan


def test_numeric_mismatch_is_contradiction():
    assert _numeric_consistency("phạt tiền đến 5 triệu đồng", "phạt 50 triệu đồng") == "mismatch_soft"
    assert _numeric_consistency("không nêu mức tiền", "phạt 50 triệu đồng") == "contradiction"
    assert _numeric_consistency("phạt 5 triệu đồng", "mức phạt 5 triệu") == "ok"


@pytest.mark.asyncio
async def test_heuristic_rejects_invented_amount():
    nli = NLIService(model=None)
    out = await nli.nli_pair(
        premise="Người vi phạm có thể bị xử phạt hành chính theo quy định.",
        hypothesis="Mức phạt là 100 triệu đồng.",
    )
    assert out["label"] in {"mau_thuan", "khong_ro"}


@pytest.mark.asyncio
async def test_citation_validator_keeps_valid_drops_bad():
    sources = [
        CandidateKhoan(khoan_id="15/2020/ND-CP::D1.K1", noi_dung="Phải kê khai đúng hạn theo quy định.", score=1.0),
    ]
    validator = CitationValidator(neo4j_driver=None)
    ok, validated, errors = await validator.validate_quotes(
        [
            {"khoan_id": "15/2020/ND-CP::D1.K1", "quote": "kê khai đúng hạn"},
            {"khoan_id": "15/2020/ND-CP::D1.K1", "quote": "đoạn bịa đặt hoàn toàn"},
        ],
        preloaded_sources=sources,
    )
    assert ok is True
    assert len(validated) == 1
    assert len(errors) == 1
