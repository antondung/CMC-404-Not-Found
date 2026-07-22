from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata
from uuid import NAMESPACE_URL, uuid5
from typing import Any

from app.config import BE2Config, get_config
from app.domain.misconception import (
    ClaimOccurrenceEvidence,
    MisconceptionAssignment,
    MisconceptionClusterCandidate,
)
from app.schemas import NliLabel


_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*|[^\W_]+", re.UNICODE)
_NEGATION_TOKENS = frozenset({"không", "chưa", "chẳng", "cấm", "miễn", "ngoại", "trừ"})
_CLUSTER_THRESHOLD = 0.84


def normalize_claim_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(_TOKEN_RE.findall(normalized))


def claim_signatures(normalized_claim: str) -> tuple[list[str], list[str]]:
    tokens = normalized_claim.split()
    numbers = sorted({token for token in tokens if token[0].isdigit()})
    negations = sorted({token for token in tokens if token in _NEGATION_TOKENS})
    return numbers, negations


def claim_similarity(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    token_f1 = 2 * overlap / (len(left_tokens) + len(right_tokens))
    sequence = SequenceMatcher(None, left, right, autojunk=False).ratio()
    return round(0.7 * token_f1 + 0.3 * sequence, 6)


class MisconceptionService:
    """Conservative, source-neutral clustering for grounded contradiction claims."""

    def __init__(self, repository: Any, config: BE2Config | None = None) -> None:
        self.repository = repository
        self.config = config or get_config()

    async def assign_occurrence(
        self,
        evidence: ClaimOccurrenceEvidence,
    ) -> MisconceptionAssignment | None:
        if not self.config.misconception_cluster_v2:
            return None
        if evidence.nli_label != NliLabel.MAU_THUAN:
            return None
        if evidence.nli_score < self.config.nli_confidence_threshold:
            return None

        normalized = normalize_claim_text(evidence.claim_text)
        numbers, negations = claim_signatures(normalized)
        candidates = await self.repository.find_misconception_candidates(
            topic=evidence.topic,
            legal_anchor_id=evidence.legal_anchor_id,
            limit=50,
        )
        selected: MisconceptionClusterCandidate | None = None
        selected_score = 0.0
        for raw_candidate in candidates:
            candidate = MisconceptionClusterCandidate.model_validate(raw_candidate)
            if candidate.number_signature != numbers:
                continue
            if candidate.negation_signature != negations:
                continue
            score = claim_similarity(normalized, candidate.normalized_claim)
            if score >= _CLUSTER_THRESHOLD and score > selected_score:
                selected = candidate
                selected_score = score

        created = selected is None
        misconception_id = (
            selected.misconception_id
            if selected is not None
            else str(
                uuid5(
                    NAMESPACE_URL,
                    f"cmc:misconception:{evidence.topic}:{evidence.legal_anchor_id}:{normalized}",
                )
            )
        )
        canonical_claim = selected.canonical_claim if selected else evidence.claim_text
        persisted = await self.repository.assign_misconception_occurrence(
            misconception_id=misconception_id,
            canonical_claim=canonical_claim,
            normalized_claim=normalized if selected is None else selected.normalized_claim,
            number_signature=numbers if selected is None else selected.number_signature,
            negation_signature=negations if selected is None else selected.negation_signature,
            similarity=1.0 if selected is None else selected_score,
            evidence=evidence,
        )
        assignment = MisconceptionAssignment.model_validate(persisted)
        if assignment.misconception_id != misconception_id:
            raise ValueError("repository returned another misconception assignment")
        return assignment.model_copy(update={"created_cluster": created})


__all__ = [
    "MisconceptionService",
    "claim_signatures",
    "claim_similarity",
    "normalize_claim_text",
]
