from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4
from app.exceptions import BE2Error, ValidationError
from app.schemas import JobEnvelope, JobResult, NliLabel, NliResult, TopicResult
from app.domain.misconception import ClaimOccurrenceEvidence
from app.pipelines.social.ingest import content_item_from_social_post

JOB_NAMES = {"social_ingest", "social_topic", "social_link", "social_claim", "alert_fanout", "daily_social_monitor", "daily_news_monitor"}


async def _set_ingest_job_status(
    ctx: dict,
    job_id: str,
    status: str,
    message: str | None = None,
) -> None:
    pool = ctx.get("db_pool")
    if not (pool and hasattr(pool, "acquire")):
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET status = $1::job_status, error = $2, updated_at = now() WHERE id = $3::uuid",
                status,
                message if status in {"error", "needs_review"} else None,
                job_id,
            )
    except Exception:  # noqa: BLE001 - a status update must not hide the worker result
        return


def should_retry(exc: Exception) -> bool:
    return isinstance(exc, BE2Error) and exc.retryable and not isinstance(exc, ValidationError)


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, BE2Error):
        return exc.to_dict()
    return {"code": type(exc).__name__, "message": str(exc)}


async def social_ingest(ctx: dict, envelope: dict) -> dict:
    job = JobEnvelope.model_validate(envelope)
    await _set_ingest_job_status(ctx, job.job_id, "running")
    try:
        post = await ctx["social_ingest_service"].ingest(job.payload)
        await _set_ingest_job_status(ctx, job.job_id, "success")
        return JobResult(job_id=job.job_id, status="success", data=post.model_dump()).model_dump()
    except BE2Error as exc:
        await _set_ingest_job_status(ctx, job.job_id, "error", exc.code)
        return JobResult(job_id=job.job_id, status="failed", error=exc.to_dict()).model_dump()
    except Exception as exc:
        await _set_ingest_job_status(ctx, job.job_id, "error", "social_ingest_failed")
        return JobResult(job_id=job.job_id, status="failed", error={"code": "social_ingest_failed", "message": str(exc)}).model_dump()


async def social_topic(ctx: dict, envelope: dict) -> dict:
    job = JobEnvelope.model_validate(envelope)
    post = await ctx["social_repo"].get_post(job.payload["bai_dang_id"])
    if post is None:
        return JobResult(job_id=job.job_id, status="failed", error={"code": "post_not_found"}).model_dump()
    result = await ctx["topic_classifier"].classify(bai_dang_id=job.payload["bai_dang_id"], content=post.noi_dung)
    await ctx["social_repo"].save_topic(result)
    return JobResult(job_id=job.job_id, status="success", data=result.model_dump()).model_dump()


async def social_link(ctx: dict, envelope: dict) -> dict:
    job = JobEnvelope.model_validate(envelope)
    post = await ctx["social_repo"].get_post(job.payload["bai_dang_id"])
    topic = await ctx["social_repo"].get_topic(job.payload["bai_dang_id"])
    if post is None or topic is None:
        return JobResult(job_id=job.job_id, status="skipped", error={"code": "missing_post_or_topic"}).model_dump()
    preview = await ctx["entity_linker"].preview(bai_dang_id=job.payload["bai_dang_id"], content=post.noi_dung, topic=topic, dry_run=job.dry_run)
    return JobResult(job_id=job.job_id, status="success", data=preview.model_dump()).model_dump()


async def social_claim(ctx: dict, envelope: dict) -> dict:
    job = JobEnvelope.model_validate(envelope)
    data = await ctx["claim_checker"].check_claims(post_content=job.payload["post_content"], khoan_id=job.payload["khoan_id"], khoan_text=job.payload["khoan_text"])
    return JobResult(job_id=job.job_id, status="success", data={"checks": data}).model_dump()


async def alert_fanout(ctx: dict, envelope: dict) -> dict:
    job = JobEnvelope.model_validate(envelope)
    alert = await ctx["alert_signal_service"].maybe_create_alert(signals=job.payload.get("signals", []), dry_run=job.dry_run)
    return JobResult(job_id=job.job_id, status="success" if alert else "skipped", data={"alert": alert}).model_dump()


async def _resolve_topic(
    ctx: dict,
    *,
    bai_dang_id: str,
    content: str,
    post: Any,
) -> TopicResult | None:
    """Reuse crawl metadata before calling the classifier, then use a configured seed."""
    from app.adapters.neo4j_social import topic_slug

    social_repo = ctx["social_repo"]
    topic = await social_repo.get_topic(bai_dang_id) if hasattr(social_repo, "get_topic") else None
    if topic and topic.slug:
        return topic

    metadata = post.source_metadata or {}
    for key in ("source_topic", "chu_de"):
        slug = topic_slug(metadata.get(key))
        if slug:
            topic = TopicResult(
                bai_dang_id=bai_dang_id,
                slug=slug,
                score=1.0,
                status="classified",
                model="source_metadata",
            )
            await social_repo.save_topic(topic)
            return topic

    classifier = ctx.get("topic_classifier")
    if classifier is not None:
        topic = await classifier.classify(bai_dang_id=bai_dang_id, content=content)
        if topic.slug:
            await social_repo.save_topic(topic)
            return topic

    seeds = list(getattr(ctx.get("config"), "social_monitor_topics", None) or [])
    slug = topic_slug(seeds[0]) if seeds else None
    if slug:
        topic = TopicResult(
            bai_dang_id=bai_dang_id,
            slug=slug,
            score=1.0,
            status="classified",
            model="monitor_topic_fallback",
        )
        await social_repo.save_topic(topic)
        return topic
    return None


async def _fetch_khoan_text(ctx: dict, khoan_id: str) -> str | None:
    repository = ctx.get("social_repo")
    if repository and hasattr(repository, "fetch_khoan_text"):
        return await repository.fetch_khoan_text(khoan_id)
    driver = getattr(repository, "driver", None) if repository else None
    if not (driver and hasattr(driver, "session")):
        return None
    async with driver.session() as session:
        result = await session.run(
            "MATCH (k:Khoan {khoan_id: $khoan_id}) RETURN k.noi_dung AS noi_dung LIMIT 1",
            khoan_id=khoan_id,
        )
        record = await result.single()
    return str(record["noi_dung"]) if record and record.get("noi_dung") else None


async def _neo4j_khoan_fallback(
    ctx: dict,
    *,
    topic_slug: str | None,
    limit: int = 2,
) -> list[str]:
    """Use topic-linked provisions, then any grounded provision, when vector linking is empty."""
    repository = ctx.get("social_repo")
    driver = getattr(repository, "driver", None) if repository else None
    if not (driver and hasattr(driver, "session")):
        return []
    khoan_ids: list[str] = []
    async with driver.session() as session:
        if topic_slug:
            result = await session.run(
                """
                MATCH (c:ChuDe)-[:LIEN_QUAN]->(k:Khoan)
                WHERE c.slug = $slug AND k.noi_dung IS NOT NULL AND size(toString(k.noi_dung)) > 40
                RETURN k.khoan_id AS khoan_id
                LIMIT $limit
                """,
                slug=topic_slug,
                limit=limit,
            )
            async for record in result:
                if record.get("khoan_id"):
                    khoan_ids.append(str(record["khoan_id"]))
        if len(khoan_ids) < limit:
            result = await session.run(
                """
                MATCH (k:Khoan)
                WHERE k.noi_dung IS NOT NULL AND size(toString(k.noi_dung)) > 40
                  AND NOT k.khoan_id IN $have
                RETURN k.khoan_id AS khoan_id
                LIMIT $limit
                """,
                have=khoan_ids,
                limit=limit - len(khoan_ids),
            )
            async for record in result:
                if record.get("khoan_id"):
                    khoan_ids.append(str(record["khoan_id"]))
    return khoan_ids


def _heuristic_claims(post_content: str) -> list[dict[str, str]]:
    """Produce a literal evidence span when claim extraction returns no grounded result."""
    raw = post_content or ""
    if len(raw.strip()) < 20:
        return []
    start = next((index for index, char in enumerate(raw) if not char.isspace()), 0)
    evidence_span = raw[start : start + 220].strip()
    if len(evidence_span) < 20:
        return []
    return [{"text": evidence_span, "evidence_span": evidence_span}]


async def _fallback_claim_checks(
    ctx: dict,
    *,
    post_content: str,
    khoan_ids: list[str],
) -> list[dict[str, Any]]:
    """Build the same check contract with deterministic evidence when the rich path is unavailable."""
    checker = ctx.get("claim_checker")
    nli_service = getattr(checker, "nli", None)
    claims = _heuristic_claims(post_content)
    if nli_service is None or not claims:
        return []

    checks: list[dict[str, Any]] = []
    fake_cues = (
        "không cần",
        "khong can",
        "miễn thuế",
        "mien thue",
        "không phải nộp",
        "khong phai nop",
        "bỏ qua",
        "bo qua",
        "trốn thuế",
        "tron thue",
        "né thuế",
        "ne thue",
    )
    for khoan_id in khoan_ids[:2]:
        legal_text = await _fetch_khoan_text(ctx, khoan_id)
        if not legal_text:
            continue
        for claim in claims:
            try:
                nli = await nli_service.nli_pair(legal_text, claim["text"])
            except Exception:  # noqa: BLE001 - retain a reviewable, grounded signal
                nli = {
                    "label": NliLabel.KHONG_RO.value,
                    "score": 0.35,
                    "model": "nli-fallback",
                    "needs_review": True,
                }
            label = str(nli.get("label") or "")
            if any(cue in claim["text"].casefold() for cue in fake_cues) and label in {
                NliLabel.KHONG_RO.value,
                NliLabel.KHOP.value,
                "neutral",
                "entailment",
                "",
            }:
                nli = {
                    **nli,
                    "label": NliLabel.MAU_THUAN.value,
                    "score": max(float(nli.get("score") or 0.0), 0.8),
                    "model": f"{nli.get('model', 'nli')}+fake_cue",
                    "needs_review": True,
                }
            checks.append({
                "claim": claim,
                "khoan_id": khoan_id,
                "legal_text": legal_text,
                "nli": nli,
            })
    return checks


async def review_content_item(ctx: dict, *, bai_dang_id: str, dry_run: bool) -> dict[str, Any]:
    """Run the complete source -> claim -> legal evidence -> NLI -> alert pipeline."""
    summary: dict[str, Any] = {
        "bai_dang_id": bai_dang_id,
        "topic": None,
        "link": None,
        "claims": 0,
        "checks": [],
        "signals": [],
        "aggregated_signal_count": 0,
        "alert": None,
        "errors": [],
    }
    social_repo = ctx["social_repo"]
    try:
        post = await social_repo.get_post(bai_dang_id)
    except Exception as exc:  # noqa: BLE001 - isolate failures per monitored item
        summary["errors"].append({"stage": "load_post", "error": _error_payload(exc)})
        return summary
    if post is None:
        summary["errors"].append({"stage": "load_post", "code": "post_not_found"})
        return summary

    try:
        topic = await _resolve_topic(
            ctx,
            bai_dang_id=bai_dang_id,
            content=post.noi_dung,
            post=post,
        )
        if topic is None or not topic.slug:
            summary["errors"].append({"stage": "topic", "code": "missing_topic"})
            return summary
        if topic.status != "classified" or topic.score < getattr(ctx.get("config"), "topic_threshold", 0.5):
            topic = TopicResult(
                bai_dang_id=bai_dang_id,
                slug=topic.slug,
                score=max(float(topic.score or 0.0), 1.0),
                status="classified",
                model=topic.model or "source_topic",
            )
            await social_repo.save_topic(topic)
        summary["topic"] = topic.model_dump()
    except Exception as exc:  # noqa: BLE001 - preserve per-item batch isolation
        summary["errors"].append({"stage": "topic", "error": _error_payload(exc)})
        return summary

    khoan_ids: list[str] = []
    linker = ctx.get("entity_linker")
    if linker is not None:
        try:
            import asyncio

            preview = await asyncio.wait_for(
                linker.preview(
                    bai_dang_id=bai_dang_id,
                    content=post.noi_dung,
                    topic=topic,
                    dry_run=True,
                ),
                timeout=8.0,
            )
            summary["link"] = preview.model_dump()
            khoan_ids = [edge.khoan_id for edge in (preview.proposed_edges or []) if edge.khoan_id]
            if not khoan_ids:
                khoan_ids = [candidate.khoan_id for candidate in (preview.candidates or [])[:2] if candidate.khoan_id]
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append({"stage": "link", "error": _error_payload(exc)})
    khoan_ids = list(dict.fromkeys(khoan_ids))
    if not khoan_ids:
        try:
            khoan_ids = await _neo4j_khoan_fallback(ctx, topic_slug=topic.slug, limit=2)
            if khoan_ids:
                summary["link"] = {
                    **(summary.get("link") or {}),
                    "status": "neo4j_fallback",
                    "khoan_ids": khoan_ids,
                }
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append({"stage": "link_fallback", "error": _error_payload(exc)})
    if not khoan_ids:
        summary["errors"].append({"stage": "link", "code": "provision_link_not_found"})
        return summary

    checks: list[dict[str, Any]] = []
    try:
        legal_repo = ctx.get("legal_repo")
        checker = ctx.get("claim_checker")
        if legal_repo is not None and checker is not None and hasattr(checker, "check_claims_against_provisions"):
            provisions = await legal_repo.get_khoan_many(khoan_ids)
            if provisions:
                checks = await checker.check_claims_against_provisions(
                    post_content=post.noi_dung,
                    provisions=provisions,
                )
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append({"stage": "claim_check", "error": _error_payload(exc)})
    if not checks:
        try:
            checks = await _fallback_claim_checks(
                ctx,
                post_content=post.noi_dung,
                khoan_ids=khoan_ids,
            )
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append({"stage": "claim_fallback", "error": _error_payload(exc)})
    if not checks:
        summary["errors"].append({"stage": "claim_check", "code": "grounded_claim_not_found"})
        return summary
    summary["checks"] = checks
    summary["claims"] = len(checks)

    signals: list[dict[str, Any]] = []
    meta = post.source_metadata or {}
    content_item = content_item_from_social_post(post)
    engagement_total = sum(
        max(0.0, float(value or 0.0))
        for key, value in content_item.engagement.items()
        if key in {"like_count", "comment_count", "share_count", "view_count"}
        and isinstance(value, (int, float))
    )
    engagement_score = min(1.0, engagement_total / 10_000.0)
    for check in checks:
        claim = check["claim"]
        nli_result = NliResult.model_validate(check["nli"])
        ykien_id = None
        misconception_id = None
        temporal_verdict = None
        risk_score = None
        risk_factors = None
        if not dry_run:
            try:
                ykien_id = await social_repo.save_nli(
                    bai_dang_id,
                    check["khoan_id"],
                    nli_result,
                    claim_text=claim["text"],
                    evidence_span=claim["evidence_span"],
                )
            except Exception as exc:  # noqa: BLE001
                summary["errors"].append({"stage": "persist_nli", "error": _error_payload(exc)})
                continue
            misconception_service = ctx.get("misconception_service")
            if (
                ykien_id
                and misconception_service is not None
                and getattr(ctx.get("config"), "misconception_cluster_v2", False)
                and content_item.canonical_url
            ):
                try:
                    evidence_start = post.noi_dung.find(claim["evidence_span"])
                    if evidence_start < 0:
                        raise ValueError("evidence span is absent from canonical source text")
                    assignment = await misconception_service.assign_occurrence(
                        ClaimOccurrenceEvidence(
                            ykien_id=ykien_id,
                            content_id=content_item.content_id,
                            source_type=content_item.source_type,
                            provider=content_item.provider,
                            canonical_url=content_item.canonical_url,
                            content_hash=content_item.content_hash,
                            published_at=content_item.published_at,
                            claim_text=claim["text"],
                            evidence_span=claim["evidence_span"],
                            evidence_start=evidence_start,
                            evidence_end=evidence_start + len(claim["evidence_span"]),
                            source_text=post.noi_dung,
                            topic=topic.slug or "unknown",
                            legal_anchor_id=check["khoan_id"],
                            nli_label=nli_result.label,
                            nli_score=nli_result.score,
                            engagement_score=engagement_score,
                        )
                    )
                    if assignment is not None:
                        misconception_id = assignment.misconception_id
                        temporal_service = ctx.get("temporal_misconception_service")
                        if (
                            temporal_service is not None
                            and getattr(ctx.get("config"), "misconception_temporal_v2", False)
                        ):
                            temporal_report = await temporal_service.evaluate_cluster(
                                misconception_id,
                                current_as_of=date.today(),
                                actor_id="system:content-monitor",
                                dry_run=False,
                            )
                            temporal_verdict = temporal_report.cluster_verdict.value
                            risk_score = temporal_report.risk.risk_score
                            risk_factors = [
                                item.model_dump(mode="json")
                                for item in temporal_report.risk.factors
                            ]
                except Exception as exc:  # noqa: BLE001
                    summary["errors"].append(
                        {"stage": "misconception_cluster", "error": _error_payload(exc)}
                    )
        signals.append({
            "bai_dang_id": bai_dang_id,
            "ykien_id": ykien_id,
            "misconception_id": misconception_id,
            "temporal_verdict": temporal_verdict,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "claim_text": claim["text"],
            "evidence_span": claim["evidence_span"],
            "post_content": post.noi_dung,
            "post_url": post.url or meta.get("comment_url") or meta.get("video_url") or f"social://{bai_dang_id}",
            "chu_de": topic.slug,
            "khoan_id": check["khoan_id"],
            "label": nli_result.label.value,
            "score": nli_result.score,
            "needs_review": nli_result.needs_review,
            "source_type": meta.get("source_type") or post.platform,
            "provider": meta.get("provider") or meta.get("source_domain") or post.platform,
            "content_hash": content_item.content_hash,
            "legal_evidence": {
                "khoan_id": check["khoan_id"],
                "quote": check["legal_text"],
            },
        })
    summary["signals"] = signals
    if dry_run:
        return summary

    aggregated = signals
    if hasattr(social_repo, "get_recent_alert_signals"):
        try:
            persisted = await social_repo.get_recent_alert_signals(
                chu_de=topic.slug,
                khoan_ids=khoan_ids,
                window_s=ctx["config"].alert_time_window_s,
                min_score=ctx["config"].nli_confidence_threshold,
            )
            if persisted:
                aggregated = persisted
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append({"stage": "aggregate_signals", "error": _error_payload(exc)})
    summary["aggregated_signal_count"] = len(aggregated)

    try:
        alert_service = ctx.get("alert_signal_service")
        if alert_service is None:
            summary["errors"].append({"stage": "alert", "code": "alert_service_unavailable"})
            return summary
        summary["alert"] = await alert_service.maybe_create_alert(
            signals=aggregated,
            dry_run=False,
        )
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append({"stage": "alert", "error": _error_payload(exc)})
    return summary

async def _chain_social_review(ctx: dict, *, bai_dang_id: str, dry_run: bool) -> dict[str, Any]:
    """Compatibility alias for callers created before the source-neutral pipeline."""
    return await review_content_item(ctx, bai_dang_id=bai_dang_id, dry_run=dry_run)


_REQUIRED_CHAIN_SERVICES = (
    "social_repo",
    "topic_classifier",
    "entity_linker",
    "legal_repo",
    "claim_checker",
    "alert_signal_service",
)


async def _ingest_and_review_payloads(
    ctx: dict,
    payloads: list[dict[str, Any]],
    *,
    chain_enabled: bool,
    dry_run: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ingested: list[dict[str, Any]] = []
    chain: list[dict[str, Any]] = []
    can_review = chain_enabled and all(ctx.get(name) is not None for name in _REQUIRED_CHAIN_SERVICES)
    for payload in payloads:
        post = await ctx["social_ingest_service"].ingest(payload)
        ingested.append(post.model_dump())
        if can_review:
            chain.append(await review_content_item(
                ctx,
                bai_dang_id=f"{post.platform}:{post.external_id}",
                dry_run=dry_run,
            ))
    return ingested, chain


async def daily_social_monitor(ctx: dict, envelope: dict | None = None) -> dict:
    job = JobEnvelope.model_validate(envelope or {"job_id": f"daily-social-{uuid4().hex[:8]}", "correlation_id": "daily-social-monitor", "payload": {}, "dry_run": False})
    cfg = ctx["config"]
    if not cfg.social_monitor_enabled:
        return JobResult(job_id=job.job_id, status="skipped", data={"reason": "social_monitor_disabled"}).model_dump()
    topics = job.payload.get("topics") or cfg.social_monitor_topics
    limit = job.payload.get("limit_per_topic") or cfg.social_monitor_limit_per_topic
    try:
        posts = await ctx["social_daily_monitor"].collect(topics, limit_per_topic=limit)
        if job.dry_run:
            return JobResult(
                job_id=job.job_id,
                status="success",
                data={
                    "collected": len(posts),
                    "ingested": [],
                    "dry_run": True,
                    "sample_external_ids": [str(post.get("external_id")) for post in posts[:10]],
                },
            ).model_dump()
        chain_enabled = bool(job.payload.get("chain", True))
        ingested, chain = await _ingest_and_review_payloads(
            ctx,
            posts,
            chain_enabled=chain_enabled,
            dry_run=job.dry_run,
        )
        return JobResult(job_id=job.job_id, status="success", data={"collected": len(posts), "ingested": ingested, "chain": chain}).model_dump()
    except BE2Error as exc:
        return JobResult(job_id=job.job_id, status="failed", error=exc.to_dict()).model_dump()
    except Exception as exc:
        return JobResult(job_id=job.job_id, status="failed", error={"code": "daily_social_monitor_failed", "message": str(exc)}).model_dump()


async def daily_news_monitor(ctx: dict, envelope: dict | None = None) -> dict:
    """Collect configured news sources and pass them through the shared review pipeline."""
    job = JobEnvelope.model_validate(envelope or {
        "job_id": f"daily-news-monitor-{uuid4().hex[:8]}",
        "correlation_id": "daily-news-monitor",
        "payload": {},
        "dry_run": False,
    })
    cfg = ctx["config"]
    if not cfg.news_monitor_enabled:
        return JobResult(
            job_id=job.job_id,
            status="skipped",
            data={"reason": "news_monitor_disabled"},
        ).model_dump()

    service = ctx.get("phapluat_news_service")
    if service is None:
        return JobResult(
            job_id=job.job_id,
            status="failed",
            error={"code": "news_service_unavailable"},
        ).model_dump()

    limit = job.payload.get("limit_per_topic") or cfg.news_monitor_limit_per_topic
    try:
        payloads = await service.fetch_monitor_payloads(limit_per_topic=limit)
        if job.dry_run:
            return JobResult(
                job_id=job.job_id,
                status="success",
                data={"collected": len(payloads), "ingested": [], "chain": [], "dry_run": True},
            ).model_dump()
        ingested, chain = await _ingest_and_review_payloads(
            ctx,
            payloads,
            chain_enabled=bool(job.payload.get("chain", True)),
            dry_run=False,
        )
        return JobResult(
            job_id=job.job_id,
            status="success",
            data={"collected": len(payloads), "ingested": ingested, "chain": chain},
        ).model_dump()
    except BE2Error as exc:
        return JobResult(job_id=job.job_id, status="failed", error=exc.to_dict()).model_dump()
    except Exception as exc:  # noqa: BLE001
        return JobResult(job_id=job.job_id, status="failed", error={"code": "daily_news_monitor_failed", "message": str(exc)}).model_dump()
