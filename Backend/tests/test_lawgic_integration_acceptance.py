from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.evaluation.acceptance_catalog import EXPECTED_ACCEPTANCE_IDS
from app.evaluation.integration_acceptance import (
    POSTGRES_ACCEPTANCE_CHECKS,
    run_integration_acceptance,
    validate_integration_config,
)
from app.evaluation.integration_fixture import fixture_config, fixture_versions
from app.evaluation.lawgic_quality import EvaluationError


ROOT = Path(__file__).resolve().parents[2]
NEGATIVE_CHECKS = {"T09", "T10", "T17", "N02", "T19", "T20"}


class _Record:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def data(self) -> dict[str, Any]:
        return self.payload


class _AsyncRows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = [_Record(row) for row in rows]

    def __aiter__(self):
        self._iterator = iter(self.rows)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _Neo4jSession:
    def __init__(self) -> None:
        self.session_kwargs: dict[str, Any] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def run(self, query: str, **_params: Any) -> _AsyncRows:
        if "legal_v2_leaf_inventory" in query:
            return _AsyncRows(
                [
                    {"provision_id": "p1", "text_checksum": "c1"},
                    {"provision_id": "p2", "text_checksum": "c2"},
                ]
            )
        negative_markers = (
            "occurrences > 1",
            "p.noi_dung IS NULL",
            "edge.review_id = $ambiguous_review_id",
            "cluster_count > 1",
            "size(old_versions) <> 1",
            "(raw:AlertMeta OR raw:DeXuatDinhChinh)",
        )
        if any(marker in query for marker in negative_markers):
            return _AsyncRows([])
        if "count(p) AS canonical_node_count" in query:
            return _AsyncRows([{"canonical_node_count": 0}])
        return _AsyncRows([{"fixture_row": True}])


class _Neo4jDriver:
    def __init__(self) -> None:
        self.last_session: _Neo4jSession | None = None
        self.last_session_kwargs: dict[str, Any] = {}

    def session(self, **kwargs: Any) -> _Neo4jSession:
        self.last_session_kwargs = kwargs
        self.last_session = _Neo4jSession()
        return self.last_session


class _Transaction:
    def __init__(self, connection: "_PostgresConnection", readonly: bool) -> None:
        self.connection = connection
        self.readonly = readonly

    async def __aenter__(self):
        self.connection.readonly = self.readonly
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _PostgresConnection:
    def __init__(self) -> None:
        self.readonly = False
        self.queries: list[str] = []

    def transaction(self, *, readonly: bool = False) -> _Transaction:
        return _Transaction(self, readonly)

    async def fetch(self, query: str, *_args: Any) -> list[dict[str, Any]]:
        self.queries.append(query)
        return []


class _Acquire:
    def __init__(self, connection: _PostgresConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _PostgresConnection:
        return self.connection

    async def __aexit__(self, *_args: object) -> None:
        return None


class _PostgresPool:
    def __init__(self) -> None:
        self.connection = _PostgresConnection()

    def acquire(self) -> _Acquire:
        return _Acquire(self.connection)


class _Qdrant:
    def __init__(self, *, checksum_p2: str = "c2") -> None:
        self.checksum_p2 = checksum_p2

    async def list_payload_records(
        self,
        _collection: str,
        _keys: list[str],
    ) -> list[dict[str, str]]:
        return [
            {"provision_id": "p1", "text_checksum": "c1"},
            {"provision_id": "p2", "text_checksum": self.checksum_p2},
        ]


def _config() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for check_id in EXPECTED_ACCEPTANCE_IDS:
        if check_id in NEGATIVE_CHECKS:
            assertion: dict[str, Any] = {"type": "empty"}
        elif check_id == "T12":
            assertion = {
                "type": "field_equals",
                "field": "canonical_node_count",
                "value": 0,
            }
        else:
            assertion = {"type": "nonempty"}
        checks[check_id] = {"params": {}, "assertion": assertion}
    return {
        "fixture_id": "lawgic-integration-v1",
        "postgres_fixture_review_id": "11111111-1111-4111-8111-111111111111",
        "snapshots": {
            "neo4j": "neo4j-snapshot-001",
            "postgres": "postgres-snapshot-001",
            "qdrant": "qdrant-snapshot-001",
        },
        "checks": checks,
    }


@pytest.mark.asyncio
async def test_multistore_acceptance_is_read_only_and_passes_exact_parity() -> None:
    driver = _Neo4jDriver()
    postgres = _PostgresPool()

    report = await run_integration_acceptance(
        driver=driver,
        postgres_pool=postgres,
        qdrant=_Qdrant(),
        catalog_path=ROOT / "Data" / "schema" / "acceptance_queries.cypher",
        config=_config(),
    )

    assert report["passed"] is True
    assert report["mutated"] is False
    assert report["stores"]["neo4j"]["check_count"] == 22
    assert report["stores"]["postgres"]["check_count"] == len(POSTGRES_ACCEPTANCE_CHECKS)
    assert report["stores"]["qdrant_parity"]["exact_match"] is True
    assert driver.last_session_kwargs["default_access_mode"] == "READ"
    assert postgres.connection.readonly is True


@pytest.mark.asyncio
async def test_multistore_acceptance_fails_on_qdrant_checksum_drift() -> None:
    report = await run_integration_acceptance(
        driver=_Neo4jDriver(),
        postgres_pool=_PostgresPool(),
        qdrant=_Qdrant(checksum_p2="drifted"),
        catalog_path=ROOT / "Data" / "schema" / "acceptance_queries.cypher",
        config=_config(),
    )

    assert report["passed"] is False
    assert report["stores"]["qdrant_parity"]["checksum_mismatch_ids"] == ["p2"]


def test_integration_config_requires_all_snapshot_ids() -> None:
    config = _config()
    config["snapshots"]["postgres"] = ""

    with pytest.raises(EvaluationError, match="snapshot IDs for: postgres"):
        validate_integration_config(config)


def test_positive_neo4j_check_cannot_be_configured_as_empty() -> None:
    config = _config()
    config["checks"]["T01"]["assertion"] = {"type": "empty"}

    with pytest.raises(EvaluationError, match="T01 cannot use an empty assertion"):
        validate_integration_config(config)


def test_negative_neo4j_check_must_be_empty() -> None:
    config = _config()
    config["checks"]["T20"]["assertion"] = {"type": "nonempty"}

    with pytest.raises(EvaluationError, match="T20 must use an empty assertion"):
        validate_integration_config(config)


def test_integration_config_rejects_unresolved_placeholders() -> None:
    config = _config()
    config["checks"]["T01"]["params"] = {"khoan_lineage": "REPLACE_KHOAN"}

    with pytest.raises(EvaluationError, match="unresolved placeholder"):
        validate_integration_config(config)


@pytest.mark.asyncio
async def test_multistore_report_retains_one_store_failure() -> None:
    report = await run_integration_acceptance(
        driver=_Neo4jDriver(),
        postgres_pool=None,
        qdrant=_Qdrant(),
        catalog_path=ROOT / "Data" / "schema" / "acceptance_queries.cypher",
        config=_config(),
    )

    assert report["passed"] is False
    assert report["stores"]["neo4j"]["passed"] is True
    assert report["stores"]["postgres"]["passed"] is False
    assert report["stores"]["qdrant_parity"]["passed"] is True


def test_synthetic_integration_fixture_has_complete_runnable_contract() -> None:
    config = fixture_config()

    validate_integration_config(config)
    assert len(fixture_versions()) == 10
    assert set(config["checks"]) == set(EXPECTED_ACCEPTANCE_IDS)
    assert config["fixture_kind"] == "synthetic_integration_fixture"
    assert all(
        str(value).startswith("content-sha256:")
        for value in config["snapshots"].values()
    )
