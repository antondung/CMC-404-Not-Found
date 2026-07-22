from __future__ import annotations

from datetime import date, datetime, timezone
import json
import re
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.config import BE2Config, get_config
from app.domain.legal_provision import LegalProvisionVersion
from app.domain.misconception import (
    MisconceptionEvaluationReport,
    MisconceptionRiskAssessment,
    RiskFactor,
    TemporalLegalCheck,
    TemporalMisconceptionVerdict,
    TemporalOccurrenceEvaluation,
)
from app.exceptions import BE2Error, TemporalLawNotFoundError, ValidationError
from app.schemas import NliLabel, NliResult


_MONEY_OR_DEADLINE_RE = re.compile(
    r"\b(phạt|cấm|xử phạt|truy thu|triệu|tỷ|đồng|%|thời hạn|ngày|tháng)\b",
    re.IGNORECASE,
)
_CRITICAL_LEGAL_RE = re.compile(
    r"\b(hình sự|phạt tù|đình chỉ|tước|cấm|truy cứu)\b",
    re.IGNORECASE,
)
_SOURCE_REACH = {
    "news": 0.70,
    "social_post": 0.55,
    "video": 0.60,
    "forum": 0.45,
    "comment": 0.35,
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class TemporalMisconceptionService:
    """Dual-time legal evaluation and explainable communications risk scoring."""

    def __init__(
        self,
        repository: Any,
        temporal_law_service: Any,
        nli_service: Any,
        config: BE2Config | None = None,
    ) -> None:
        self.repository = repository
        self.temporal = temporal_law_service
        self.nli = nli_service
        self.config = config or get_config()

    async def evaluate_cluster(
        self,
        misconception_id: str,
        *,
        current_as_of: date,
        actor_id: str,
        dry_run: bool = False,
    ) -> MisconceptionEvaluationReport:
        if not all((
            self.config.legal_provision_v2_read,
            self.config.temporal_law_v2,
            self.config.misconception_cluster_v2,
            self.config.misconception_temporal_v2,
        )):
            raise ValidationError("temporal misconception evaluation is disabled")
        if not isinstance(current_as_of, date):
            raise ValidationError("current_as_of must be a date")
        cluster = await self.repository.get_misconception_evaluation_inputs(
            misconception_id,
            limit=100,
        )
        if cluster is None:
            raise TemporalLawNotFoundError(
                "Misconception cluster was not found",
                details={"misconception_id": misconception_id},
            )
        occurrences = list(cluster.get("occurrences") or [])
        if not occurrences:
            raise ValidationError("misconception cluster has no source occurrences")
        if int(cluster.get("occurrence_count") or len(occurrences)) > len(occurrences):
            raise ValidationError("misconception cluster exceeds the safe evaluation batch limit")

        evaluated_at = datetime.now(timezone.utc)
        evaluations: list[TemporalOccurrenceEvaluation] = []
        for occurrence in occurrences:
            published_at = occurrence.get("published_at")
            if isinstance(published_at, str):
                published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            if not isinstance(published_at, datetime) or published_at.tzinfo is None:
                raise ValidationError("every occurrence requires a timezone-aware published_at")
            if current_as_of < published_at.date():
                raise ValidationError("current_as_of cannot precede an occurrence publication date")
            evaluations.append(
                await self._evaluate_occurrence(
                    misconception_id=misconception_id,
                    occurrence=occurrence,
                    published_at=published_at,
                    current_as_of=current_as_of,
                    evaluated_at=evaluated_at,
                )
            )

        cluster_verdict = self._cluster_verdict(evaluations)
        risk = self._risk_assessment(
            cluster=cluster,
            occurrences=occurrences,
            evaluations=evaluations,
            current_as_of=current_as_of,
            assessed_at=evaluated_at,
        )
        report = MisconceptionEvaluationReport(
            misconception_id=misconception_id,
            current_as_of=current_as_of,
            cluster_verdict=cluster_verdict,
            evaluations=evaluations,
            risk=risk,
            persisted=not dry_run,
        )
        if not dry_run:
            await self.repository.save_misconception_evaluation(
                report=report,
                actor_id=actor_id,
            )
        return report

    async def _evaluate_occurrence(
        self,
        *,
        misconception_id: str,
        occurrence: dict[str, Any],
        published_at: datetime,
        current_as_of: date,
        evaluated_at: datetime,
    ) -> TemporalOccurrenceEvaluation:
        ykien_id = str(occurrence.get("ykien_id") or "").strip()
        claim_text = str(occurrence.get("claim_text") or "").strip()
        legal_anchor_id = str(occurrence.get("legal_anchor_id") or "").strip()
        if not ykien_id or not claim_text or not legal_anchor_id:
            raise ValidationError("occurrence is missing claim or legal-anchor identity")

        historical: TemporalLegalCheck | None = None
        current: TemporalLegalCheck | None = None
        reason_codes: list[str] = []
        try:
            historical_version = await self.temporal.resolve_version(
                legal_anchor_id,
                published_at.date(),
                audience="admin",
            )
            current_version = await self.temporal.resolve_version(
                legal_anchor_id,
                current_as_of,
                audience="admin",
            )
            historical = await self._check(historical_version, claim_text, published_at.date())
            current = await self._check(current_version, claim_text, current_as_of)
            verdict, reason_codes = self._verdict(historical, current)
        except BE2Error as exc:
            verdict = TemporalMisconceptionVerdict.UNVERIFIABLE
            reason_codes = ["LEGAL_VERSION_UNAVAILABLE", exc.code.upper()]

        identity = json.dumps(
            {
                "misconception_id": misconception_id,
                "ykien_id": ykien_id,
                "claim_text": claim_text,
                "published_at": published_at.isoformat(),
                "current_as_of": current_as_of.isoformat(),
                "historical_lineage_id": historical.lineage_id if historical else None,
                "historical_checksum": historical.text_checksum if historical else None,
                "current_lineage_id": current.lineage_id if current else None,
                "current_checksum": current.text_checksum if current else None,
                "verdict": verdict.value,
            },
            sort_keys=True,
        )
        return TemporalOccurrenceEvaluation(
            evaluation_id=str(uuid5(NAMESPACE_URL, f"cmc:temporal-misconception:{identity}")),
            misconception_id=misconception_id,
            ykien_id=ykien_id,
            claim_text=claim_text,
            published_at=published_at,
            current_as_of=current_as_of,
            verdict=verdict,
            historical=historical,
            current=current,
            reason_codes=list(dict.fromkeys(reason_codes)),
            evaluated_at=evaluated_at,
        )

    async def _check(
        self,
        version: LegalProvisionVersion,
        claim_text: str,
        as_of: date,
    ) -> TemporalLegalCheck:
        result = NliResult.model_validate(await self.nli.nli_pair(version.text, claim_text))
        if result.model.startswith("heuristic-nli") and not result.needs_review:
            result = result.model_copy(update={"needs_review": True})
        return TemporalLegalCheck(
            as_of=as_of,
            provision_id=version.provision_id,
            lineage_id=version.lineage_id,
            legal_text=version.text,
            text_checksum=version.text_checksum,
            effective_from=version.effective_from,
            effective_to=version.effective_to,
            label=result.label,
            score=result.score,
            model=result.model,
            needs_review=result.needs_review,
        )

    def _verdict(
        self,
        historical: TemporalLegalCheck,
        current: TemporalLegalCheck,
    ) -> tuple[TemporalMisconceptionVerdict, list[str]]:
        threshold = self.config.nli_confidence_threshold
        if historical.lineage_id != current.lineage_id:
            return TemporalMisconceptionVerdict.NEEDS_REVIEW, ["LEGAL_LINEAGE_MISMATCH"]
        if (
            historical.needs_review
            or current.needs_review
            or historical.score < threshold
            or current.score < threshold
        ):
            return TemporalMisconceptionVerdict.NEEDS_REVIEW, ["LOW_CONFIDENCE_OR_NLI_REVIEW"]
        if historical.provision_id == current.provision_id and historical.label != current.label:
            return TemporalMisconceptionVerdict.NEEDS_REVIEW, ["INCONSISTENT_SAME_VERSION_NLI"]
        if (
            historical.label == NliLabel.KHOP
            and current.label == NliLabel.MAU_THUAN
            and historical.provision_id != current.provision_id
        ):
            return (
                TemporalMisconceptionVerdict.OUTDATED_BUT_PREVIOUSLY_TRUE,
                ["HISTORICALLY_SUPPORTED", "CURRENTLY_CONTRADICTED", "LEGAL_VERSION_CHANGED"],
            )
        if current.label == NliLabel.KHOP:
            return TemporalMisconceptionVerdict.SUPPORTED, ["CURRENTLY_SUPPORTED"]
        if current.label == NliLabel.MAU_THUAN and historical.label == NliLabel.MAU_THUAN:
            return TemporalMisconceptionVerdict.CONTRADICTED, ["HISTORICALLY_CONTRADICTED", "CURRENTLY_CONTRADICTED"]
        return TemporalMisconceptionVerdict.UNVERIFIABLE, ["INSUFFICIENT_DUAL_TIME_ENTAILMENT"]

    @staticmethod
    def _cluster_verdict(
        evaluations: list[TemporalOccurrenceEvaluation],
    ) -> TemporalMisconceptionVerdict:
        verdicts = {item.verdict for item in evaluations}
        if TemporalMisconceptionVerdict.NEEDS_REVIEW in verdicts:
            return TemporalMisconceptionVerdict.NEEDS_REVIEW
        if len(verdicts) == 1:
            return next(iter(verdicts))
        if verdicts == {TemporalMisconceptionVerdict.UNVERIFIABLE}:
            return TemporalMisconceptionVerdict.UNVERIFIABLE
        return TemporalMisconceptionVerdict.PARTIALLY_INCORRECT

    def _risk_assessment(
        self,
        *,
        cluster: dict[str, Any],
        occurrences: list[dict[str, Any]],
        evaluations: list[TemporalOccurrenceEvaluation],
        current_as_of: date,
        assessed_at: datetime,
    ) -> MisconceptionRiskAssessment:
        legal_texts = [item.current.legal_text for item in evaluations if item.current]
        combined_legal = " ".join(legal_texts)
        legal_impact = 0.9 if _CRITICAL_LEGAL_RE.search(combined_legal) else (
            0.7 if _MONEY_OR_DEADLINE_RE.search(combined_legal) else 0.45
        )
        source_reach = max(
            (_SOURCE_REACH.get(str(item.get("source_type") or ""), 0.4) for item in occurrences),
            default=0.4,
        )
        contradiction_confidence = max(
            (
                item.current.score
                for item in evaluations
                if item.current and item.current.label == NliLabel.MAU_THUAN
            ),
            default=0.0,
        )
        independent_hashes = {
            str(item.get("content_hash"))
            for item in occurrences
            if str(item.get("content_hash") or "").strip()
        }
        independent_volume = max(
            1,
            len(independent_hashes)
            or int(cluster.get("source_count") or 0)
            or len(occurrences),
        )
        published_by_source: dict[str, datetime] = {}
        for occurrence, evaluation in zip(occurrences, evaluations):
            source_identity = str(
                occurrence.get("content_hash")
                or occurrence.get("content_id")
                or occurrence.get("ykien_id")
                or evaluation.ykien_id
            )
            previous = published_by_source.get(source_identity)
            if previous is None or evaluation.published_at < previous:
                published_by_source[source_identity] = evaluation.published_at
        published = list(published_by_source.values())
        elapsed_hours = max(
            1.0,
            (max(published) - min(published)).total_seconds() / 3600 if len(published) > 1 else 24.0,
        )
        velocity = _clamp((independent_volume / elapsed_hours) / 0.5)
        source_diversity = _clamp(independent_volume / 3)
        recent_law_change = 0.0
        for item in evaluations:
            if item.current:
                age = (current_as_of - item.current.effective_from).days
                recent_law_change = max(recent_law_change, 1.0 if age <= 90 else (0.5 if age <= 365 else 0.0))
        engagement = _clamp(
            sum(float(item.get("engagement_score") or 0.0) for item in occurrences)
            / max(1, len(occurrences))
        )
        incomplete = sum(1 for item in occurrences if not item.get("provenance_complete", True))
        provenance_penalty = _clamp(incomplete / max(1, len(occurrences)))

        specs = [
            ("LEGAL_IMPACT", legal_impact, 0.25, "Impact of the linked legal duty, sanction or threshold."),
            ("SOURCE_REACH", source_reach, 0.20, "Estimated reach tier of the strongest source type."),
            ("CONTRADICTION_CONFIDENCE", contradiction_confidence, 0.15, "Strongest current-law contradiction confidence."),
            ("VELOCITY", velocity, 0.15, "Independent source bodies per hour; syndicated copies count once."),
            ("SOURCE_DIVERSITY", source_diversity, 0.10, "Independent content hashes, capped at three."),
            ("RECENT_LAW_CHANGE", recent_law_change, 0.10, "Recency of the currently effective legal version."),
            ("ENGAGEMENT", engagement, 0.05, "Normalized source engagement when available."),
        ]
        factors = [
            RiskFactor(
                code=code,
                score=round(score, 6),
                weight=weight,
                contribution=round(score * weight, 6),
                explanation=explanation,
            )
            for code, score, weight, explanation in specs
        ]
        penalty_contribution = -0.30 * provenance_penalty
        factors.append(RiskFactor(
            code="PROVENANCE_PENALTY",
            score=round(provenance_penalty, 6),
            weight=0.30,
            contribution=round(penalty_contribution, 6),
            explanation="Deduction for occurrences without complete source provenance.",
        ))
        risk_score = round(_clamp(sum(item.contribution for item in factors)), 6)
        severity = (
            "critical" if risk_score >= 0.85 else
            "high" if risk_score >= 0.70 else
            "medium" if risk_score >= 0.50 else
            "low"
        )
        return MisconceptionRiskAssessment(
            risk_score=risk_score,
            severity=severity,
            factors=factors,
            assessed_at=assessed_at,
        )


__all__ = ["TemporalMisconceptionService"]
