from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from app.domain.legal_provision import ProvisionLevel, build_provision_version


FIXTURE_ID = "lawgic-local-integration-v1"
LOGICAL_VB_ID = "LAWGIC-FIXTURE-LAW"
REVIEW_ID = "11111111-1111-4111-8111-111111111111"
CANDIDATE_ID = "22222222-2222-4222-8222-222222222222"
EVENT_ID = "33333333-3333-4333-8333-333333333333"
COMMIT_KEY = "lawgic-fixture-commit-v1"
V1_DATE = date(2020, 1, 1)
V2_DATE = date(2026, 7, 1)
V3_DATE = date(2027, 1, 1)


def _source_checksum(source_id: str) -> str:
    return hashlib.sha256(source_id.encode("utf-8")).hexdigest()


def fixture_versions() -> list[Any]:
    shared = {"logical_vb_id": LOGICAL_VB_ID, "visibility": "public"}
    specs = [
        ("V1", ProvisionLevel.DIEU, "5", None, None, "Điều về ngưỡng áp dụng.", V1_DATE, None, 1),
        ("V1", ProvisionLevel.KHOAN, "5", "2", None, "Ngưỡng áp dụng được quy định như sau.", V1_DATE, None, 1),
        ("V1", ProvisionLevel.DIEM, "5", "2", "a", "Ngưỡng áp dụng là 200 triệu đồng.", V1_DATE, V2_DATE, 1),
        ("V2", ProvisionLevel.DIEM, "5", "2", "a", "Ngưỡng áp dụng là 500 triệu đồng.", V2_DATE, V3_DATE, 2),
        ("V3", ProvisionLevel.DIEM, "5", "2", "a", "Ngưỡng áp dụng là 700 triệu đồng.", V3_DATE, None, 3),
        ("V1", ProvisionLevel.DIEM, "5", "2", "b", "Điểm b tiếp tục có hiệu lực và không bị sửa đổi.", V1_DATE, None, 1),
        ("V1", ProvisionLevel.KHOAN, "5", "3", None, "Khoản này không có Điểm.", V1_DATE, None, 1),
        ("V1", ProvisionLevel.DIEU, "6", None, None, "Điều này không có Khoản.", V1_DATE, None, 1),
        ("V3", ProvisionLevel.DIEU, "7", None, None, "Điều này có hiệu lực trong tương lai.", V3_DATE, None, 1),
        ("V1", ProvisionLevel.DIEU, "8", None, None, "Điều này bị bãi bỏ từ ngày 01 tháng 07 năm 2026.", V1_DATE, V2_DATE, 1),
    ]
    versions = []
    for source_suffix, level, article, clause, point, text, start, end, version_no in specs:
        source_id = f"{LOGICAL_VB_ID}-{source_suffix}"
        versions.append(
            build_provision_version(
                **shared,
                source_vb_id=source_id,
                source_checksum=_source_checksum(source_id),
                level=level,
                article=article,
                clause=clause,
                point=point,
                text=text,
                effective_from=start,
                effective_to=end,
                version_no=version_no,
            )
        )
    return versions


def _version_map(versions: list[Any]) -> dict[tuple[str, str, str | None, str | None], Any]:
    return {
        (version.level.value, version.article, version.clause, version.point): version
        for version in versions
    }


def fixture_config() -> dict[str, Any]:
    versions = fixture_versions()
    by_coordinate = _version_map(versions)
    point_a = sorted(
        [v for v in versions if v.level == ProvisionLevel.DIEM and v.point == "a"],
        key=lambda value: value.version_no,
    )
    point_b = by_coordinate[("diem", "5", "2", "b")]
    clause = by_coordinate[("khoan", "5", "2", None)]
    leaf_clause = by_coordinate[("khoan", "5", "3", None)]
    leaf_article = by_coordinate[("dieu", "6", None, None)]
    future = by_coordinate[("dieu", "7", None, None)]
    repealed = by_coordinate[("dieu", "8", None, None)]
    canonical_payload = [version.model_dump(mode="json") for version in versions]
    neo_hash = hashlib.sha256(
        json.dumps(canonical_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    parent_lineages = {v.parent_lineage_id for v in versions if v.parent_lineage_id}
    leaves = [v for v in versions if v.lineage_id not in parent_lineages]
    qdrant_hash = hashlib.sha256(
        json.dumps(
            sorted((v.provision_id, v.text_checksum) for v in leaves),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    postgres_hash = hashlib.sha256(
        f"{REVIEW_ID}:{COMMIT_KEY}:{point_a[0].provision_id}:{point_a[1].provision_id}".encode()
    ).hexdigest()
    claim = "Ngưỡng áp dụng là 200 triệu đồng."
    return {
        "fixture_id": FIXTURE_ID,
        "fixture_kind": "synthetic_integration_fixture",
        "postgres_fixture_review_id": REVIEW_ID,
        "database": "neo4j",
        "snapshots": {
            "neo4j": f"content-sha256:{neo_hash}",
            "postgres": f"content-sha256:{postgres_hash}",
            "qdrant": f"content-sha256:{qdrant_hash}",
        },
        "checks": {
            "T01": {"params": {"khoan_lineage": clause.lineage_id}, "assertion": {"type": "field_set_equals", "field": "diem_lineages", "value": [point_a[0].lineage_id, point_b.lineage_id]}},
            "T02": {"params": {"khoan_lineage": clause.lineage_id, "as_of": "2026-07-21"}, "assertion": {"type": "field_set_equals", "field": "active_diem_ids", "value": [point_a[1].provision_id, point_b.provision_id]}},
            "T03": {"params": {"leaf_khoan_lineage": leaf_clause.lineage_id, "as_of": "2026-07-21"}, "assertion": {"type": "field_equals", "field": "leaf_id", "value": leaf_clause.provision_id}},
            "T04": {"params": {"leaf_dieu_lineage": leaf_article.lineage_id, "as_of": "2026-07-21"}, "assertion": {"type": "field_equals", "field": "leaf_id", "value": leaf_article.provision_id}},
            "T05": {"params": {"diem_a_lineage": point_a[0].lineage_id, "diem_b_lineage": point_b.lineage_id}, "assertion": {"type": "all", "assertions": [{"type": "field_set_equals", "field": "diem_a_versions", "value": [v.provision_id for v in point_a]}, {"type": "field_set_equals", "field": "diem_b_versions", "value": [point_b.provision_id]}, {"type": "field_set_equals", "field": "diem_b_effective_to", "value": []}]}},
            "T06": {"params": {"lineage": point_a[0].lineage_id}, "assertion": {"type": "all", "assertions": [{"type": "field_equals", "field": "version_path", "value": [v.provision_id for v in point_a]}, {"type": "field_equals", "field": "hops", "value": 2}]}},
            "T07": {"params": {"future_lineage": future.lineage_id, "as_of": "2026-07-21"}, "assertion": {"type": "field_set_equals", "field": "active_ids", "value": []}},
            "T08": {"params": {"repealed_lineage": repealed.lineage_id, "as_of": "2026-07-21"}, "assertion": {"type": "field_set_equals", "field": "active_ids", "value": []}},
            "T09": {"params": {}, "assertion": {"type": "empty"}},
            "T10": {"params": {}, "assertion": {"type": "empty"}},
            "T11": {"params": {"citation_node_id": point_a[1].provision_id}, "assertion": {"type": "all", "assertions": [{"type": "field_equals", "field": "node_id", "value": point_a[1].provision_id}, {"type": "field_nonempty", "field": "canonical_text"}, {"type": "field_nonempty", "field": "text_checksum"}]}},
            "T12": {"params": {"fabricated_node_id": "fabricated-node-does-not-exist"}, "assertion": {"type": "field_equals", "field": "canonical_node_count", "value": 0}},
            "T13": {"params": {"citation_node_id": point_a[1].provision_id, "as_of": "2026-07-21"}, "assertion": {"type": "field_equals", "field": "active_citation_node_id", "value": point_a[1].provision_id}},
            "T14": {"params": {"citation_node_id": point_a[1].provision_id, "exact_quote": "500 triệu đồng"}, "assertion": {"type": "field_equals", "field": "quote_valid_node_id", "value": point_a[1].provision_id}},
            "T15": {"params": {"citation_node_id": point_a[1].provision_id, "claim_text": claim}, "assertion": {"type": "all", "assertions": [{"type": "field_equals", "field": "node_id", "value": point_a[1].provision_id}, {"type": "field_nonempty", "field": "nli_premise"}, {"type": "field_equals", "field": "nli_hypothesis", "value": claim}]}},
            "T16": {"params": {"old_provision_id": point_a[0].provision_id, "new_provision_id": point_a[1].provision_id, "source_vb_id": f"{LOGICAL_VB_ID}-V2", "review_id": REVIEW_ID, "commit_key": COMMIT_KEY}, "assertion": {"type": "all", "assertions": [{"type": "field_equals", "field": "old_id", "value": point_a[0].provision_id}, {"type": "field_equals", "field": "new_id", "value": point_a[1].provision_id}, {"type": "field_equals", "field": "source_vb_id", "value": f"{LOGICAL_VB_ID}-V2"}, {"type": "field_equals", "field": "change_type", "value": "REWORDED"}]}},
            "T17": {"params": {"ambiguous_review_id": "ambiguous-review-without-edges"}, "assertion": {"type": "empty"}},
            "T18": {"params": {}, "assertion": {"type": "all", "assertions": [{"type": "field_nonempty", "field": "claim_occurrence_id"}, {"type": "field_nonempty", "field": "historical_id"}, {"type": "field_nonempty", "field": "current_id"}]}},
            "T19": {"params": {}, "assertion": {"type": "empty"}},
            "T20": {"params": {}, "assertion": {"type": "empty"}},
            "N01": {"params": {}, "assertion": {"type": "all", "assertions": [{"type": "field_nonempty", "field": "content_id"}, {"type": "field_nonempty", "field": "claim_occurrence_id"}, {"type": "field_nonempty", "field": "misconception_id"}, {"type": "field_nonempty", "field": "legal_anchor_id"}]}},
            "N02": {"params": {}, "assertion": {"type": "empty"}}
        },
    }


__all__ = [
    "CANDIDATE_ID",
    "COMMIT_KEY",
    "EVENT_ID",
    "FIXTURE_ID",
    "LOGICAL_VB_ID",
    "REVIEW_ID",
    "fixture_config",
    "fixture_versions",
]
