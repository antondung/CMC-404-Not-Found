from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any
from uuid import uuid5, NAMESPACE_URL
from app.schemas import LinkCandidate, NliResult, SocialPost, TopicResult
from app.domain.misconception import ClaimOccurrenceEvidence
from app.domain.misconception import (
    MisconceptionEvaluationReport,
    TemporalOccurrenceEvaluation,
)
from app.pipelines.social.ingest import content_item_from_social_post


def topic_slug(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = re.sub(r"\s+", " ", str(name)).strip()
    if not cleaned:
        return None
    return cleaned.casefold()


def _coerce_datetime(value: Any) -> datetime:
    """Neo4j DateTime / ISO string / native datetime → aware datetime."""
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    to_native = getattr(value, "to_native", None)
    if callable(to_native):
        native = to_native()
        if isinstance(native, datetime):
            return native if native.tzinfo else native.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


class Neo4jSocialRepository:
    """BE2 Neo4j writes limited to labels/relationships in SYSTEM_DATA.md."""

    def __init__(self, driver: Any, pool: Any | None = None) -> None:
        self.driver = driver
        self.pool = pool

    async def upsert_post(self, post: SocialPost) -> str:
        bai_dang_id = f"{post.platform}:{post.external_id}"
        meta = post.source_metadata or {}
        chu_de = topic_slug(meta.get("source_topic") or meta.get("chu_de"))
        content_item = content_item_from_social_post(post)
        query = """
        MERGE (b:BaiDang:NoiDungNguon {platform: $platform, external_id: $external_id})
        SET b.content_id = $content_id,
            b.source_type = $source_type,
            b.provider = $provider,
            b.canonical_url = $canonical_url,
            b.content_hash = $content_hash,
            b.title = $title,
            b.engagement_json = $engagement_json,
            b.noi_dung = $noi_dung,
            b.tac_gia_hash = $tac_gia_hash,
            b.tac_gia = $tac_gia,
            b.url = $url,
            b.chu_de = $chu_de,
            b.source_topic = $chu_de,
            b.source_query = $source_query,
            b.youtube_kind = $youtube_kind,
            b.comment_id = $comment_id,
            b.comment_author_name = $comment_author_name,
            b.comment_text = $comment_text,
            b.comment_url = $comment_url,
            b.video_title = $video_title,
            b.video_url = $video_url,
            b.thoi_gian = datetime($thoi_gian),
            b.ngay_dang = datetime($thoi_gian),
            b.ingested_at = datetime($ingested_at),
            b.source_metadata_json = $source_metadata_json
        WITH b
        FOREACH (_ IN CASE WHEN $chu_de IS NULL THEN [] ELSE [1] END |
            MERGE (c:ChuDe {slug: $chu_de})
            SET c.ten = coalesce(c.ten, $chu_de_ten, $chu_de)
            MERGE (b)-[r:THAO_LUAN_VE]->(c)
            SET r.score = coalesce(r.score, 1.0),
                r.model = coalesce(r.model, 'crawl_source_topic'),
                r.status = coalesce(r.status, 'classified')
        )
        RETURN b.platform + ':' + b.external_id AS bai_dang_id
        """
        comment_text = None
        if meta.get("youtube_kind") == "comment":
            parts = [part.strip() for part in post.noi_dung.split("\n\n", 1)]
            comment_text = parts[1] if len(parts) == 2 else post.noi_dung
        chu_de_ten = str(meta.get("source_topic") or meta.get("chu_de") or chu_de or "").strip() or None
        params = {
            "platform": post.platform,
            "external_id": post.external_id,
            "content_id": content_item.content_id,
            "source_type": content_item.source_type.value,
            "provider": content_item.provider,
            "canonical_url": content_item.canonical_url,
            "content_hash": content_item.content_hash,
            "title": content_item.title,
            "engagement_json": json.dumps(content_item.engagement, ensure_ascii=False, default=str),
            "noi_dung": post.noi_dung,
            "tac_gia_hash": post.tac_gia_hash,
            "tac_gia": meta.get("comment_author_name") or meta.get("author_name") or meta.get("video_channel_title"),
            "url": post.url,
            "chu_de": chu_de,
            "chu_de_ten": chu_de_ten,
            "source_query": meta.get("source_query"),
            "youtube_kind": meta.get("youtube_kind"),
            "comment_id": meta.get("comment_id"),
            "comment_author_name": meta.get("comment_author_name"),
            "comment_text": comment_text,
            "comment_url": meta.get("comment_url"),
            "video_title": meta.get("video_title"),
            "video_url": meta.get("video_url"),
            "source_metadata_json": json.dumps(meta, ensure_ascii=False, default=str),
            "thoi_gian": post.thoi_gian.isoformat(),
            "ingested_at": post.ingested_at.isoformat(),
        }
        async with self.driver.session() as session:
            result = await session.run(query, **params)
            record = await result.single()
        return record["bai_dang_id"] if record else bai_dang_id

    async def ensure_topics_from_posts(self) -> int:
        """Backfill ChuDe + THAO_LUAN_VE for posts that only have chu_de / source_topic props."""
        query = """
        MATCH (b:BaiDang)
        WHERE coalesce(b.chu_de, b.source_topic) IS NOT NULL
          AND trim(toString(coalesce(b.chu_de, b.source_topic))) <> ''
        WITH b, toLower(trim(toString(coalesce(b.chu_de, b.source_topic)))) AS slug
        MERGE (c:ChuDe {slug: slug})
        SET c.ten = coalesce(c.ten, trim(toString(coalesce(b.chu_de, b.source_topic))))
        SET b.chu_de = slug
        MERGE (b)-[r:THAO_LUAN_VE]->(c)
        SET r.score = coalesce(r.score, 1.0),
            r.model = coalesce(r.model, 'backfill_source_topic'),
            r.status = coalesce(r.status, 'classified')
        RETURN count(DISTINCT c) AS topics
        """
        async with self.driver.session() as session:
            result = await session.run(query)
            record = await result.single()
        return int(record["topics"]) if record else 0

    async def ensure_monitored_topics(self, topics: list[str]) -> int:
        """Seed ChuDe nodes for configured monitor topics (even before crawl has posts)."""
        created = 0
        async with self.driver.session() as session:
            for name in topics:
                slug = topic_slug(name)
                if not slug:
                    continue
                result = await session.run(
                    """
                    MERGE (c:ChuDe {slug: $slug})
                    SET c.ten = coalesce(c.ten, $ten),
                        c.monitored = true
                    RETURN c.slug AS slug
                    """,
                    slug=slug,
                    ten=name.strip(),
                )
                if await result.single():
                    created += 1
        return created

    async def get_post(self, bai_dang_id: str) -> SocialPost | None:
        platform, external_id = bai_dang_id.split(":", 1)
        query = """
        MATCH (b:BaiDang {platform: $platform})
        WHERE toString(b.external_id) = $external_id
        RETURN b LIMIT 1
        """
        async with self.driver.session() as session:
            result = await session.run(query, platform=platform, external_id=str(external_id))
            record = await result.single()
        if not record:
            return None
        data = dict(record["b"])
        noi = str(data.get("noi_dung") or data.get("comment_text") or "").strip()
        if not noi:
            return None
        source_metadata = data.get("source_metadata_json") or {}
        if isinstance(source_metadata, str):
            try:
                source_metadata = json.loads(source_metadata)
            except json.JSONDecodeError:
                source_metadata = {}
        if not isinstance(source_metadata, dict):
            source_metadata = {}
        metadata_defaults = {
            "source_type": data.get("source_type"),
            "provider": data.get("provider"),
            "chu_de": data.get("chu_de"),
            "source_topic": data.get("source_topic") or data.get("chu_de"),
        }
        for key, value in metadata_defaults.items():
            if value is not None:
                source_metadata.setdefault(key, value)
        return SocialPost(
            platform=str(data.get("platform") or platform),
            external_id=str(data.get("external_id") or external_id),
            noi_dung=noi,
            tac_gia_hash=str(data["tac_gia_hash"]) if data.get("tac_gia_hash") is not None else None,
            url=str(data["url"]) if data.get("url") else None,
            thoi_gian=_coerce_datetime(
                data.get("thoi_gian") or data.get("ngay_dang") or data.get("ingested_at")
            ),
            source_metadata=source_metadata,
            ingested_at=_coerce_datetime(data.get("ingested_at")),
        )

    async def save_topic(self, result: TopicResult) -> None:
        if not result.slug:
            return
        platform, external_id = result.bai_dang_id.split(":", 1)
        slug = topic_slug(result.slug) or result.slug
        query = """
        MATCH (b:BaiDang {platform: $platform})
        WHERE toString(b.external_id) = $external_id
        MERGE (c:ChuDe {slug: $slug})
        SET c.ten = coalesce(c.ten, $slug)
        SET b.chu_de = coalesce(b.chu_de, $slug)
        MERGE (b)-[r:THAO_LUAN_VE]->(c)
        SET r.score = $score, r.model = $model, r.status = $status
        """
        async with self.driver.session() as session:
            result_cursor = await session.run(
                query,
                platform=platform,
                external_id=str(external_id),
                slug=slug,
                score=result.score,
                model=result.model,
                status=result.status,
            )
            await result_cursor.consume()

    async def get_topic(self, bai_dang_id: str) -> TopicResult | None:
        platform, external_id = bai_dang_id.split(":", 1)
        query = """
        MATCH (b:BaiDang)
        WHERE b.platform = $platform AND toString(b.external_id) = $external_id
        OPTIONAL MATCH (b)-[r:THAO_LUAN_VE]->(c:ChuDe)
        WITH b, c, r
        ORDER BY coalesce(r.score, 0) DESC
        LIMIT 1
        RETURN coalesce(c.slug, b.chu_de, b.source_topic) AS slug,
               coalesce(r.score, 1.0) AS score,
               coalesce(r.status, 'classified') AS status,
               coalesce(r.model, 'bai_dang_chu_de') AS model
        """
        async with self.driver.session() as session:
            result = await session.run(query, platform=platform, external_id=str(external_id))
            record = await result.single()
        if not record or not record.get("slug"):
            return None
        slug = topic_slug(str(record["slug"])) or str(record["slug"])
        status = record.get("status")
        if status not in {"classified", "needs_review", "unknown"}:
            status = "classified"
        return TopicResult(
            bai_dang_id=bai_dang_id,
            slug=slug,
            score=min(1.0, max(0.0, float(record.get("score") or 1.0))),
            status=status,
            model=str(record.get("model") or "bai_dang_chu_de"),
        )

    async def create_link_edge(self, bai_dang_id: str, candidate: LinkCandidate, *, method: str) -> None:
        platform, external_id = bai_dang_id.split(":", 1)
        # Do not require ChuDe-[:LIEN_QUAN]->Khoan beforehand — MERGE it when ChuDe exists.
        query = """
        MATCH (b:BaiDang {platform: $platform})
        WHERE toString(b.external_id) = $external_id
        MATCH (k:Khoan {khoan_id: $khoan_id})
        OPTIONAL MATCH (b)-[:THAO_LUAN_VE]->(c:ChuDe)
        FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END |
          MERGE (c)-[:LIEN_QUAN]->(k)
        )
        MERGE (b)-[r:GAN_CO_CAN_KIEM_CHUNG]->(k)
        SET r.score = $score, r.method = $method, r.updated_at = datetime($updated_at)
        """
        async with self.driver.session() as session:
            result = await session.run(
                query,
                platform=platform,
                external_id=str(external_id),
                khoan_id=candidate.khoan_id,
                score=candidate.score,
                method=method,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            await result.consume()

    async def fetch_khoan_text(self, khoan_id: str) -> str | None:
        async with self.driver.session() as session:
            result = await session.run(
                "MATCH (k:Khoan {khoan_id: $khoan_id}) RETURN k.noi_dung AS noi_dung LIMIT 1",
                khoan_id=khoan_id,
            )
            record = await result.single()
        return str(record["noi_dung"]) if record and record.get("noi_dung") else None

    async def save_nli(self, bai_dang_id: str, khoan_id: str, result: NliResult, *, claim_text: str, evidence_span: str) -> str:
        platform, external_id = bai_dang_id.split(":", 1)
        query = """
        MATCH (b:BaiDang {platform: $platform})
        WHERE toString(b.external_id) = $external_id
        MATCH (k:Khoan {khoan_id: $khoan_id})
        MERGE (y:YKien {uuid: $uuid})
        SET y.bai_dang_id = $bai_dang_id,
            y.claim_hash = $claim_hash,
            y.claim_text = $claim_text,
            y.evidence_span = $evidence_span,
            y.stance = $label,
            y.confidence = $score,
            y.created_at = coalesce(y.created_at, datetime($now)),
            y.updated_at = datetime($now)
        MERGE (b)-[:CO_YKIEN]->(y)
        MERGE (y)-[r:DOI_CHIEU]->(k)
        SET r.label = $label, r.score = $score, r.updated_at = datetime($now)
        """
        claim_hash = str(uuid5(NAMESPACE_URL, f"{bai_dang_id}:{khoan_id}:{claim_text}:{evidence_span}"))
        ykien_uuid = str(uuid5(NAMESPACE_URL, f"be2:ykien:{claim_hash}"))
        now = datetime.now(timezone.utc).isoformat()
        async with self.driver.session() as session:
            result_cursor = await session.run(
                query,
                platform=platform,
                external_id=str(external_id),
                khoan_id=khoan_id,
                bai_dang_id=bai_dang_id,
                uuid=ykien_uuid,
                claim_hash=claim_hash,
                claim_text=claim_text,
                evidence_span=evidence_span,
                label=result.label.value,
                score=result.score,
                now=now,
            )
            await result_cursor.consume()
        return ykien_uuid

    async def find_misconception_candidates(
        self,
        *,
        topic: str,
        legal_anchor_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = """
        MATCH (m:Misconception {topic: $topic, legal_anchor_id: $legal_anchor_id})
        WHERE coalesce(m.status, 'open') IN ['open', 'reviewing']
        RETURN m.uuid AS misconception_id,
               m.canonical_claim AS canonical_claim,
               m.normalized_claim AS normalized_claim,
               m.topic AS topic,
               m.legal_anchor_id AS legal_anchor_id,
               coalesce(m.number_signature, []) AS number_signature,
               coalesce(m.negation_signature, []) AS negation_signature,
               coalesce(m.volume, 0) AS occurrence_count,
               coalesce(m.status, 'open') AS status
        ORDER BY coalesce(m.last_seen_at, m.created_at) DESC
        LIMIT $limit
        """
        items: list[dict[str, Any]] = []
        async with self.driver.session() as session:
            result = await session.run(
                query,
                topic=topic,
                legal_anchor_id=legal_anchor_id,
                limit=max(1, min(int(limit), 100)),
            )
            async for record in result:
                items.append(dict(record))
        return items

    async def assign_misconception_occurrence(
        self,
        *,
        misconception_id: str,
        canonical_claim: str,
        normalized_claim: str,
        number_signature: list[str],
        negation_signature: list[str],
        similarity: float,
        evidence: ClaimOccurrenceEvidence,
    ) -> dict[str, Any]:
        """Atomically attach one grounded occurrence and refresh cluster counters."""
        now = datetime.now(timezone.utc).isoformat()
        query = """
        MATCH (y:YKien {uuid: $ykien_id})
        MATCH (legal)
        WHERE (legal:Khoan OR legal:LegalProvision)
          AND (legal.khoan_id = $legal_anchor_id OR legal.provision_id = $legal_anchor_id)
        WITH y, legal LIMIT 1
        OPTIONAL MATCH (y)-[:INSTANCE_OF]->(existing:Misconception)
        WITH y, legal, existing
        WHERE existing IS NULL OR existing.uuid = $misconception_id
        MERGE (m:Misconception {uuid: $misconception_id})
        ON CREATE SET m.canonical_claim = $canonical_claim,
                      m.normalized_claim = $normalized_claim,
                      m.topic = $topic,
                      m.legal_anchor_id = $legal_anchor_id,
                      m.number_signature = $number_signature,
                      m.negation_signature = $negation_signature,
                      m.status = 'open',
                      m.created_at = datetime($now)
        SET m.last_seen_at = datetime($now)
        MERGE (y)-[instance:INSTANCE_OF]->(m)
        ON CREATE SET instance.content_id = $content_id,
                      instance.source_type = $source_type,
                      instance.provider = $provider,
                      instance.canonical_url = $canonical_url,
                      instance.content_hash = $content_hash,
                      instance.published_at = datetime($published_at),
                      instance.evidence_start = $evidence_start,
                      instance.evidence_end = $evidence_end,
                      instance.nli_label = $nli_label,
                      instance.nli_score = $nli_score,
                      instance.engagement_score = $engagement_score,
                      instance.cluster_similarity = $similarity,
                      instance.assigned_at = datetime($now)
        MERGE (m)-[contradicts:CONTRADICTS]->(legal)
        ON CREATE SET contradicts.first_seen_at = datetime($now)
        SET contradicts.last_seen_at = datetime($now),
            contradicts.max_confidence = CASE
              WHEN coalesce(contradicts.max_confidence, 0.0) < $nli_score THEN $nli_score
              ELSE contradicts.max_confidence
            END
        WITH m
        OPTIONAL MATCH (:YKien)-[occurrence:INSTANCE_OF]->(m)
        WITH m,
             count(occurrence) AS occurrence_count,
             count(DISTINCT coalesce(occurrence.content_hash, occurrence.content_id)) AS source_count,
             count(DISTINCT occurrence.provider) AS provider_count
        SET m.volume = occurrence_count,
            m.source_count = source_count,
            m.provider_count = provider_count
        RETURN m.uuid AS misconception_id,
               $ykien_id AS ykien_id,
               m.canonical_claim AS canonical_claim,
               m.normalized_claim AS normalized_claim,
               $similarity AS similarity,
               false AS created_cluster,
               occurrence_count,
               source_count,
               provider_count,
               m.status AS status
        """
        params = {
            "misconception_id": misconception_id,
            "canonical_claim": canonical_claim,
            "normalized_claim": normalized_claim,
            "number_signature": number_signature,
            "negation_signature": negation_signature,
            "similarity": float(similarity),
            "ykien_id": evidence.ykien_id,
            "content_id": evidence.content_id,
            "source_type": evidence.source_type.value,
            "provider": evidence.provider,
            "canonical_url": evidence.canonical_url,
            "content_hash": evidence.content_hash,
            "published_at": evidence.published_at.isoformat(),
            "evidence_start": evidence.evidence_start,
            "evidence_end": evidence.evidence_end,
            "nli_label": evidence.nli_label.value,
            "nli_score": evidence.nli_score,
            "engagement_score": evidence.engagement_score,
            "topic": evidence.topic,
            "legal_anchor_id": evidence.legal_anchor_id,
            "now": now,
        }
        async with self.driver.session() as session:
            execute_write = getattr(session, "execute_write", None)
            if execute_write is None:
                raise ValueError("Neo4j managed write transactions are required for clustering")

            async def _write(tx: Any) -> Any:
                result = await tx.run(query, **params)
                return await result.single()

            record = await execute_write(_write)
        if record is None:
            raise ValueError("misconception occurrence did not match canonical claim/legal nodes")
        return dict(record)

    async def list_misconceptions(
        self,
        *,
        status: str | None = None,
        temporal_verdict: str | None = None,
        risk_severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = """
        MATCH (m:Misconception)
        WHERE ($status IS NULL OR m.status = $status)
          AND ($temporal_verdict IS NULL OR m.temporal_verdict = $temporal_verdict)
          AND ($risk_severity IS NULL OR m.risk_severity = $risk_severity)
        RETURN m.uuid AS misconception_id,
               m.canonical_claim AS canonical_claim,
               m.topic AS topic,
               m.legal_anchor_id AS legal_anchor_id,
               coalesce(m.status, 'open') AS status,
               coalesce(m.volume, 0) AS occurrence_count,
               coalesce(m.source_count, 0) AS source_count,
               coalesce(m.provider_count, 0) AS provider_count,
               m.temporal_verdict AS temporal_verdict,
               m.risk_score AS risk_score,
               m.risk_severity AS risk_severity,
               m.temporal_as_of AS temporal_as_of,
               m.created_at AS created_at,
               m.last_seen_at AS last_seen_at
        ORDER BY coalesce(m.last_seen_at, m.created_at) DESC
        SKIP $offset LIMIT $limit
        """
        items: list[dict[str, Any]] = []
        async with self.driver.session() as session:
            result = await session.run(
                query,
                status=status,
                temporal_verdict=temporal_verdict,
                risk_severity=risk_severity,
                limit=max(1, min(int(limit), 100)),
                offset=max(0, int(offset)),
            )
            async for record in result:
                items.append(dict(record))
        return items

    async def get_misconception(self, misconception_id: str) -> dict[str, Any] | None:
        query = """
        MATCH (m:Misconception {uuid: $misconception_id})
        OPTIONAL MATCH (y:YKien)-[instance:INSTANCE_OF]->(m)
        OPTIONAL MATCH (m)-[:CONTRADICTS]->(legal)
        WITH m, legal, collect(DISTINCT {
          ykien_id: y.uuid,
          claim_text: y.claim_text,
          evidence_span: y.evidence_span,
          content_id: instance.content_id,
          source_type: instance.source_type,
          provider: instance.provider,
          canonical_url: instance.canonical_url,
          content_hash: instance.content_hash,
          published_at: instance.published_at,
          nli_score: instance.nli_score,
          cluster_similarity: instance.cluster_similarity
        }) AS occurrences
        RETURN m.uuid AS misconception_id,
               m.canonical_claim AS canonical_claim,
               m.normalized_claim AS normalized_claim,
               m.topic AS topic,
               m.legal_anchor_id AS legal_anchor_id,
               coalesce(m.status, 'open') AS status,
               coalesce(m.volume, 0) AS occurrence_count,
               coalesce(m.source_count, 0) AS source_count,
               coalesce(m.provider_count, 0) AS provider_count,
               m.temporal_verdict AS temporal_verdict,
               m.temporal_as_of AS temporal_as_of,
               m.risk_score AS risk_score,
               m.risk_severity AS risk_severity,
               m.risk_factors_json AS risk_factors_json,
               m.evaluated_at AS evaluated_at,
               m.evaluated_by AS evaluated_by,
               m.created_at AS created_at,
               m.last_seen_at AS last_seen_at,
               occurrences,
               collect(DISTINCT coalesce(legal.provision_id, legal.khoan_id)) AS legal_anchor_ids
        """
        async with self.driver.session() as session:
            result = await session.run(query, misconception_id=misconception_id)
            record = await result.single()
            if not record:
                return None
            data = dict(record)
            evaluation_result = await session.run(
                """
                MATCH (m:Misconception {uuid: $misconception_id})
                MATCH (y:YKien)-[:INSTANCE_OF]->(m)
                MATCH (y)-[:HAS_TEMPORAL_EVALUATION]->(evaluation:TemporalMisconceptionEvaluation)
                WHERE evaluation.current_as_of = m.temporal_as_of
                OPTIONAL MATCH (evaluation)-[:HISTORICAL_BASIS]->(historical:LegalProvision)
                OPTIONAL MATCH (evaluation)-[:CURRENT_BASIS]->(current:LegalProvision)
                RETURN evaluation.evaluation_id AS evaluation_id,
                       m.uuid AS misconception_id,
                       y.uuid AS ykien_id,
                       evaluation.claim_text AS claim_text,
                       evaluation.published_at AS published_at,
                       evaluation.current_as_of AS current_as_of,
                       evaluation.verdict AS verdict,
                       evaluation.reason_codes AS reason_codes,
                       evaluation.evaluated_at AS evaluated_at,
                       CASE WHEN historical IS NULL THEN NULL ELSE {
                         as_of: date(evaluation.published_at),
                         provision_id: historical.provision_id,
                         lineage_id: historical.lineage_id,
                         legal_text: historical.noi_dung,
                         text_checksum: historical.text_checksum,
                         effective_from: historical.effective_from,
                         effective_to: historical.effective_to,
                         label: evaluation.historical_label,
                         score: evaluation.historical_score,
                         model: coalesce(evaluation.historical_model, 'persisted-nli'),
                         needs_review: coalesce(evaluation.historical_needs_review, false)
                       } END AS historical,
                       CASE WHEN current IS NULL THEN NULL ELSE {
                         as_of: evaluation.current_as_of,
                         provision_id: current.provision_id,
                         lineage_id: current.lineage_id,
                         legal_text: current.noi_dung,
                         text_checksum: current.text_checksum,
                         effective_from: current.effective_from,
                         effective_to: current.effective_to,
                         label: evaluation.current_label,
                         score: evaluation.current_score,
                         model: coalesce(evaluation.current_model, 'persisted-nli'),
                         needs_review: coalesce(evaluation.current_needs_review, false)
                       } END AS current
                ORDER BY evaluation.published_at ASC, evaluation.evaluation_id ASC
                """,
                misconception_id=misconception_id,
            )
            data["temporal_evaluations"] = [
                TemporalOccurrenceEvaluation.model_validate(dict(item)).model_dump(mode="json")
                async for item in evaluation_result
            ]
        factors = data.pop("risk_factors_json", None)
        if isinstance(factors, str):
            try:
                factors = json.loads(factors)
            except json.JSONDecodeError:
                factors = []
        data["risk_factors"] = factors if isinstance(factors, list) else []
        return data

    async def get_misconception_evaluation_inputs(
        self,
        misconception_id: str,
        *,
        limit: int = 100,
    ) -> dict[str, Any] | None:
        query = """
        MATCH (m:Misconception {uuid: $misconception_id})
        OPTIONAL MATCH (y:YKien)-[instance:INSTANCE_OF]->(m)
        WITH m, y, instance
        ORDER BY instance.published_at ASC, y.uuid ASC
        WITH m, collect({
          ykien_id: y.uuid,
          claim_text: y.claim_text,
          published_at: instance.published_at,
          legal_anchor_id: m.legal_anchor_id,
          source_type: instance.source_type,
          provider: instance.provider,
          content_id: instance.content_id,
          canonical_url: instance.canonical_url,
          content_hash: instance.content_hash,
          evidence_start: instance.evidence_start,
          evidence_end: instance.evidence_end,
          engagement_score: coalesce(instance.engagement_score, 0.0),
          provenance_complete: instance.canonical_url IS NOT NULL
            AND instance.content_hash IS NOT NULL
            AND instance.published_at IS NOT NULL
            AND instance.evidence_start IS NOT NULL
            AND instance.evidence_end > instance.evidence_start
        })[0..$limit] AS occurrences
        RETURN m.uuid AS misconception_id,
               m.canonical_claim AS canonical_claim,
               m.legal_anchor_id AS legal_anchor_id,
               coalesce(m.volume, size(occurrences)) AS occurrence_count,
               coalesce(m.source_count, size(occurrences)) AS source_count,
               coalesce(m.provider_count, 1) AS provider_count,
               m.created_at AS first_seen_at,
               m.last_seen_at AS last_seen_at,
               occurrences
        """
        async with self.driver.session() as session:
            result = await session.run(
                query,
                misconception_id=misconception_id,
                limit=max(1, min(int(limit), 100)),
            )
            record = await result.single()
        return dict(record) if record else None

    async def save_misconception_evaluation(
        self,
        *,
        report: MisconceptionEvaluationReport,
        actor_id: str,
    ) -> None:
        """Persist all occurrence evaluations and the aggregate risk in one transaction."""
        occurrence_query = """
        MATCH (m:Misconception {uuid: $misconception_id})
        MATCH (y:YKien {uuid: $ykien_id})-[:INSTANCE_OF]->(m)
        OPTIONAL MATCH (historical:LegalProvision {provision_id: $historical_id})
        OPTIONAL MATCH (current:LegalProvision {provision_id: $current_id})
        WITH m, y, historical, current
        WHERE ($historical_id IS NULL OR historical IS NOT NULL)
          AND ($current_id IS NULL OR current IS NOT NULL)
          AND ($historical_id IS NULL OR historical.text_checksum = $historical_checksum)
          AND ($current_id IS NULL OR current.text_checksum = $current_checksum)
          AND ($historical_id IS NULL OR historical.lineage_id = $historical_lineage_id)
          AND ($current_id IS NULL OR current.lineage_id = $current_lineage_id)
          AND ($verdict <> 'OUTDATED_BUT_PREVIOUSLY_TRUE'
               OR $historical_lineage_id = $current_lineage_id)
        MERGE (evaluation:TemporalMisconceptionEvaluation {evaluation_id: $evaluation_id})
        ON CREATE SET evaluation.misconception_id = $misconception_id,
                      evaluation.ykien_id = $ykien_id,
                      evaluation.claim_text = $claim_text,
                      evaluation.published_at = datetime($published_at),
                      evaluation.current_as_of = date($current_as_of),
                      evaluation.verdict = $verdict,
                      evaluation.reason_codes = $reason_codes,
                      evaluation.historical_label = $historical_label,
                      evaluation.historical_score = $historical_score,
                      evaluation.historical_model = $historical_model,
                      evaluation.historical_needs_review = $historical_needs_review,
                      evaluation.historical_lineage_id = $historical_lineage_id,
                      evaluation.historical_checksum = $historical_checksum,
                      evaluation.current_label = $current_label,
                      evaluation.current_score = $current_score,
                      evaluation.current_model = $current_model,
                      evaluation.current_needs_review = $current_needs_review,
                      evaluation.current_lineage_id = $current_lineage_id,
                      evaluation.current_checksum = $current_checksum,
                      evaluation.evaluated_at = datetime($evaluated_at),
                      evaluation.evaluated_by = $actor_id
        WITH m, y, historical, current, evaluation
        WHERE evaluation.misconception_id = $misconception_id
          AND evaluation.ykien_id = $ykien_id
          AND evaluation.claim_text = $claim_text
          AND evaluation.published_at = datetime($published_at)
          AND evaluation.current_as_of = date($current_as_of)
          AND evaluation.verdict = $verdict
          AND coalesce(evaluation.historical_lineage_id, '') = coalesce($historical_lineage_id, '')
          AND coalesce(evaluation.historical_checksum, '') = coalesce($historical_checksum, '')
          AND coalesce(evaluation.current_lineage_id, '') = coalesce($current_lineage_id, '')
          AND coalesce(evaluation.current_checksum, '') = coalesce($current_checksum, '')
        MERGE (y)-[:HAS_TEMPORAL_EVALUATION]->(evaluation)
        FOREACH (_ IN CASE WHEN historical IS NULL THEN [] ELSE [1] END |
          MERGE (evaluation)-[:HISTORICAL_BASIS]->(historical)
        )
        FOREACH (_ IN CASE WHEN current IS NULL THEN [] ELSE [1] END |
          MERGE (evaluation)-[:CURRENT_BASIS]->(current)
        )
        FOREACH (_ IN CASE
          WHEN $verdict = 'OUTDATED_BUT_PREVIOUSLY_TRUE' AND historical IS NOT NULL THEN [1]
          ELSE [] END |
          MERGE (m)-[outdated:BASED_ON_OUTDATED_VERSION]->(historical)
          SET outdated.last_evaluation_id = $evaluation_id,
              outdated.last_evaluated_at = datetime($evaluated_at)
        )
        FOREACH (_ IN CASE
          WHEN $verdict IN ['CONTRADICTED', 'OUTDATED_BUT_PREVIOUSLY_TRUE', 'PARTIALLY_INCORRECT']
               AND current IS NOT NULL THEN [1]
          ELSE [] END |
          MERGE (m)-[contradicts:CONTRADICTS]->(current)
          SET contradicts.last_evaluation_id = $evaluation_id,
              contradicts.last_evaluated_at = datetime($evaluated_at),
              contradicts.max_confidence = CASE
                WHEN coalesce(contradicts.max_confidence, 0.0) < $current_score THEN $current_score
                ELSE contradicts.max_confidence
              END
        )
        RETURN evaluation.evaluation_id AS evaluation_id
        """
        cluster_query = """
        MATCH (m:Misconception {uuid: $misconception_id})
        SET m.temporal_verdict = $cluster_verdict,
            m.temporal_as_of = date($current_as_of),
            m.risk_score = $risk_score,
            m.risk_severity = $risk_severity,
            m.risk_factors_json = $risk_factors_json,
            m.risk_assessment_version = $risk_assessment_version,
            m.evaluated_at = datetime($evaluated_at),
            m.evaluated_by = $actor_id
        RETURN m.uuid AS misconception_id
        """
        async with self.driver.session() as session:
            execute_write = getattr(session, "execute_write", None)
            if execute_write is None:
                raise ValueError("Neo4j managed write transactions are required for temporal evaluation")

            async def _write(tx: Any) -> None:
                for item in report.evaluations:
                    historical = item.historical
                    current = item.current
                    result = await tx.run(
                        occurrence_query,
                        misconception_id=report.misconception_id,
                        evaluation_id=item.evaluation_id,
                        ykien_id=item.ykien_id,
                        claim_text=item.claim_text,
                        published_at=item.published_at.isoformat(),
                        current_as_of=item.current_as_of.isoformat(),
                        verdict=item.verdict.value,
                        reason_codes=item.reason_codes,
                        historical_id=historical.provision_id if historical else None,
                        historical_label=historical.label.value if historical else None,
                        historical_score=historical.score if historical else None,
                        historical_model=historical.model if historical else None,
                        historical_needs_review=historical.needs_review if historical else None,
                        historical_lineage_id=historical.lineage_id if historical else None,
                        historical_checksum=historical.text_checksum if historical else None,
                        current_id=current.provision_id if current else None,
                        current_label=current.label.value if current else None,
                        current_score=current.score if current else None,
                        current_model=current.model if current else None,
                        current_needs_review=current.needs_review if current else None,
                        current_lineage_id=current.lineage_id if current else None,
                        current_checksum=current.text_checksum if current else None,
                        evaluated_at=item.evaluated_at.isoformat(),
                        actor_id=actor_id,
                    )
                    record = await result.single()
                    if record is None:
                        raise ValueError(
                            f"temporal evidence changed before persistence: {item.evaluation_id}"
                        )
                cluster_result = await tx.run(
                    cluster_query,
                    misconception_id=report.misconception_id,
                    cluster_verdict=report.cluster_verdict.value,
                    current_as_of=report.current_as_of.isoformat(),
                    risk_score=report.risk.risk_score,
                    risk_severity=report.risk.severity,
                    risk_factors_json=json.dumps(
                        [item.model_dump(mode="json") for item in report.risk.factors],
                        ensure_ascii=False,
                    ),
                    risk_assessment_version=report.risk.assessment_version,
                    evaluated_at=report.risk.assessed_at.isoformat(),
                    actor_id=actor_id,
                )
                if await cluster_result.single() is None:
                    raise ValueError("misconception disappeared before risk persistence")

            await execute_write(_write)

    async def save_alert(self, alert: dict[str, Any]) -> str:
        alert_uuid = alert.get("uuid") or alert.get("alert_id") or str(uuid5(NAMESPACE_URL, f"be2:alert:{alert.get('dedupe_key') or alert}"))
        now = datetime.now(timezone.utc).isoformat()
        query = """
        MERGE (a:AlertMeta {uuid: $uuid})
        SET a.chu_de = $chu_de, a.khoan_ids = $khoan_ids, a.severity = $severity,
            a.volume = $volume, a.status = $status, a.provenance_status = $provenance_status,
            a.risk_score = $risk_score,
            a.risk_factors_json = $risk_factors_json,
            a.dedupe_key = $dedupe_key,
            a.signals_json = $signals_json,
            a.created_at = coalesce(a.created_at, datetime($now)),
            a.updated_at = datetime($now),
            a.last_seen_at = datetime($now)
        WITH a
        UNWIND $signal_ids AS signal_id
        OPTIONAL MATCH (y:YKien {uuid: signal_id})
        FOREACH (_ IN CASE WHEN y IS NULL THEN [] ELSE [1] END | MERGE (a)-[:BAO_GOM_TIN_HIEU]->(y))
        WITH DISTINCT a
        UNWIND $misconception_ids AS misconception_id
        OPTIONAL MATCH (m:Misconception {uuid: misconception_id})
        FOREACH (_ IN CASE WHEN m IS NULL THEN [] ELSE [1] END | MERGE (a)-[:CANH_BAO_VE]->(m))
        RETURN a.uuid AS uuid
        """
        async with self.driver.session() as session:
            signals = alert.get("signals", [])
            result = await session.run(
                query,
                uuid=alert_uuid,
                dedupe_key=alert.get("dedupe_key"),
                chu_de=alert.get("chu_de"),
                khoan_ids=alert.get("khoan_ids", []),
                severity=alert.get("severity"),
                volume=alert.get("volume"),
                status=alert.get("status", "open"),
                provenance_status=alert.get("provenance_status", "missing"),
                risk_score=alert.get("risk_score"),
                risk_factors_json=json.dumps(alert.get("risk_factors", []), ensure_ascii=False),
                signals_json=json.dumps(signals, ensure_ascii=False, default=str),
                signal_ids=[s.get("ykien_id") for s in signals if s.get("ykien_id")],
                misconception_ids=list(dict.fromkeys(
                    str(s["misconception_id"])
                    for s in signals
                    if s.get("misconception_id")
                )),
                now=now,
            )
            record = await result.single()
        if self.pool and hasattr(self.pool, "acquire"):
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO alerts (id, chu_de, khoan_ids, severity, volume, status, signals, provenance_status)
                    VALUES ($1::uuid, $2, $3::jsonb, $4, $5, $6::alert_status, $7::jsonb, $8)
                    ON CONFLICT (id) DO UPDATE SET
                      chu_de = EXCLUDED.chu_de,
                      khoan_ids = EXCLUDED.khoan_ids,
                      severity = EXCLUDED.severity,
                      volume = EXCLUDED.volume,
                      status = EXCLUDED.status,
                      signals = EXCLUDED.signals,
                      provenance_status = EXCLUDED.provenance_status
                    """,
                    str(alert_uuid),
                    alert.get("chu_de"),
                    json.dumps(alert.get("khoan_ids", []), ensure_ascii=False),
                    alert.get("severity"),
                    alert.get("volume", 0),
                    alert.get("status", "open"),
                    json.dumps(alert.get("signals", []), ensure_ascii=False, default=str),
                    alert.get("provenance_status", "missing"),
                )
        return record["uuid"] if record else str(alert_uuid)

    async def find_recent_alert(self, key: str, cooldown_s: int) -> dict[str, Any] | None:
        query = """
        MATCH (a:AlertMeta {dedupe_key: $key})
        WHERE coalesce(a.last_seen_at, a.updated_at, a.created_at)
              >= datetime() - duration({seconds: $cooldown_s})
        RETURN a LIMIT 1
        """
        async with self.driver.session() as session:
            result = await session.run(
                query,
                key=key,
                cooldown_s=max(0, int(cooldown_s)),
            )
            record = await result.single()
        return dict(record["a"]) if record else None

    async def get_recent_alert_signals(
        self,
        *,
        chu_de: str | None,
        khoan_ids: list[str],
        window_s: int,
        min_score: float,
    ) -> list[dict[str, Any]]:
        """Load persisted, source-grounded contradictions for one alert aggregation window."""
        if not self.driver or not hasattr(self.driver, "session"):
            return []
        query = """
        MATCH (b:BaiDang)-[:CO_YKIEN]->(y:YKien)-[d:DOI_CHIEU]->(k:Khoan)
        OPTIONAL MATCH (y)-[:INSTANCE_OF]->(m:Misconception)
        OPTIONAL MATCH (b)-[:THAO_LUAN_VE]->(c:ChuDe)
        WHERE d.label = 'mau_thuan'
          AND d.score >= $min_score
          AND y.created_at >= datetime() - duration({seconds: $window_s})
          AND ($chu_de IS NULL OR coalesce(c.slug, b.chu_de) = $chu_de)
          AND (size($khoan_ids) = 0 OR k.khoan_id IN $khoan_ids)
        RETURN y.uuid AS ykien_id, y.claim_text AS claim_text,
               y.evidence_span AS evidence_span, d.label AS label, d.score AS score,
               b.platform + ':' + b.external_id AS bai_dang_id,
               b.noi_dung AS post_content, b.url AS post_url,
               coalesce(c.slug, b.chu_de) AS chu_de,
               m.uuid AS misconception_id,
               b.source_type AS source_type, b.provider AS provider,
               b.content_hash AS content_hash,
               k.khoan_id AS khoan_id, k.noi_dung AS legal_text,
               k.van_ban_id AS van_ban_id
        ORDER BY y.created_at DESC
        LIMIT 500
        """
        signals: list[dict[str, Any]] = []
        async with self.driver.session() as session:
            result = await session.run(
                query,
                chu_de=chu_de,
                khoan_ids=khoan_ids,
                window_s=max(1, int(window_s)),
                min_score=float(min_score),
            )
            async for record in result:
                signals.append({
                    "bai_dang_id": record.get("bai_dang_id"),
                    "ykien_id": record.get("ykien_id"),
                    "claim_text": record.get("claim_text"),
                    "evidence_span": record.get("evidence_span"),
                    "post_content": record.get("post_content"),
                    "post_url": record.get("post_url"),
                    "chu_de": record.get("chu_de"),
                    "misconception_id": record.get("misconception_id"),
                    "khoan_id": record.get("khoan_id"),
                    "label": record.get("label"),
                    "score": float(record.get("score") or 0.0),
                    "source_type": record.get("source_type"),
                    "provider": record.get("provider"),
                    "content_hash": record.get("content_hash"),
                    "legal_evidence": {
                        "khoan_id": record.get("khoan_id"),
                        "van_ban": record.get("van_ban_id"),
                        "quote": record.get("legal_text"),
                    },
                })
        return signals
