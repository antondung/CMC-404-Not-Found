from __future__ import annotations

from app.exceptions import ValidationError
from app.schemas import Citation, CandidateKhoan


def validate_citations(citations: list[Citation], sources: list[CandidateKhoan]) -> None:
    source_map = {s.khoan_id: s.noi_dung for s in sources}
    for citation in citations:
        text = source_map.get(citation.khoan_id)
        if text is None:
            raise ValidationError("citation references unknown khoan_id", details={"khoan_id": citation.khoan_id})
        if citation.quote not in text:
            raise ValidationError("citation quote is not substring of source", details={"khoan_id": citation.khoan_id})
