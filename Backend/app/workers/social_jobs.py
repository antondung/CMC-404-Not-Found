from __future__ import annotations

from app.exceptions import BE2Error, ValidationError
from app.schemas import JobEnvelope, JobResult

JOB_NAMES = {"social_ingest", "social_topic", "social_link", "social_claim", "alert_fanout"}


def should_retry(exc: Exception) -> bool:
    return isinstance(exc, BE2Error) and exc.retryable and not isinstance(exc, ValidationError)


async def social_ingest(ctx: dict, envelope: dict) -> dict:
    job = JobEnvelope.model_validate(envelope)
    try:
        post = await ctx["social_ingest_service"].ingest(job.payload)
        return JobResult(job_id=job.job_id, status="success", data=post.model_dump()).model_dump()
    except BE2Error as exc:
        return JobResult(job_id=job.job_id, status="failed", error=exc.to_dict()).model_dump()


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
