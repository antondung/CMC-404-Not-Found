# LAWGIC core evaluation

This directory separates CI contract evidence from release evidence.

## Evidence levels

- `synthetic_contract_fixture`: deterministic cases used to detect schema, metric and guardrail regressions. These cases may pass CI but can never authorize rollout.
- `independent_holdout`: manually labelled cases that were not used to implement or tune the evaluated feature. Every suite must set `independent_review=true` and meet the minimum sample size before the runner can return `GO`.

Gold files contain only inputs and expected labels. Predictions are stored in separate files so an implementation cannot silently rewrite the expected answer while producing a result.

## Run the smoke gates

From the repository root:

```powershell
Backend\.venv\Scripts\python.exe Backend\scripts\run_lawgic_quality_gates.py `
  --manifest eval\manifest.smoke.json `
  --output eval\reports\l7-smoke-report.json
```

The smoke report should have `blocking_gates_passed=true` and `release_decision=NO_GO`. The `NO_GO` is intentional: bundled synthetic data is not release evidence.

For a release candidate, create a separate manifest pointing to independently reviewed holdout files and run with `--release`. That mode exits non-zero if metadata, sample sizes or any blocking gate is insufficient.

## Metrics

| Suite | Primary metrics |
|---|---|
| Parser | recall by Điều/Khoản/Điểm, character coverage, invariant errors |
| Retrieval | Recall@1/5, MRR, nDCG@5 for lexical/vector/hybrid/graph/reranker profiles |
| Temporal | exact active-node accuracy at `as_of` |
| Citation | exact node, canonical quote/effectivity/existence, claim support F1 |
| Amendment | pairing precision/recall, change-type macro F1, auto-approved precision |
| Misinformation | verdict macro F1, outdated-verdict F1, pairwise cluster F1, high-risk precision |
| Safety | required refusal, over-refusal, accuracy |
| System | P50/P95, P95 regression ratio, failure rate |

Objective legal labels are scored directly. An LLM judge is not a blocking evaluator for exact node, effectivity, citation, amendment pair or temporal verdict correctness.

## Independent labelling protocol

1. Freeze raw source files and their checksums before labelling.
2. Split cases into tune and holdout sets before threshold tuning.
3. Require two reviewers for temporal, citation, amendment and misinformation labels; resolve disagreement through a third reviewer.
4. Record reviewer IDs, guideline version, adjudication state and source checksum in dataset metadata kept outside prediction files.
5. Include hard negatives: partial amendments, future/repealed nodes, fabricated citations, non-entailed exact quotes, old-but-once-true claims and syndicated news copies.
6. Publish all failed metrics and error categories; never remove a failed case after seeing model output unless the source label is formally adjudicated and audited.

### Required release metadata

Every gold file marked `dataset_kind: independent_holdout` must include all of the following metadata. A boolean `independent_review` by itself is not release evidence.

```json
{
  "metadata": {
    "dataset_id": "lawgic-<suite>-holdout-v1",
    "dataset_kind": "independent_holdout",
    "independent_review": true,
    "reviewer_ids": ["reviewer-01", "reviewer-02"],
    "adjudication_status": "adjudicated",
    "guideline_version": "lawgic-holdout-v1",
    "source_dataset_sha256": "<64 lowercase hex characters>"
  }
}
```

Reviewer IDs must be distinct pseudonymous audit identifiers. `source_dataset_sha256` is the checksum of the frozen raw-source bundle used for labelling, not the checksum of the prediction file. Missing or malformed provenance keeps `release_decision=NO_GO` and is listed in `review_provenance_issues`.

## Acceptance catalog

Validate that the repository contains exactly T01–T20 and N01–N02:

```powershell
Backend\.venv\Scripts\python.exe Backend\scripts\run_lawgic_acceptance.py `
  --catalog Data\schema\acceptance_queries.cypher
```

Real Neo4j execution is opt-in and read-only. Supply `--integration-config` with all 22 checks, each containing query `params` and one assertion (`empty`, `nonempty`, `row_count`, `field_equals`, or `field_set_equals`). Credentials come only from `NEO4J_URI`, `NEO4J_USER` and `NEO4J_PASSWORD`.

Catalog validation is not datastore acceptance. T01–T20/N01–N02 are release evidence only after the integration runner executes against the approved fixture datastore and the resulting report is retained.

## Current limitations

- Bundled fixtures are synthetic and intentionally below release sample sizes.
- Bundled latency values test calculation/reporting only; they are not measured production latency.
- No migration, source crawl, database write, feature activation or rollout is performed by either evaluation runner.

## Multi-datastore integration acceptance

Copy `config/integration-fixture.template.json`, replace every `REPLACE_*` value with an approved fixture value, and record immutable snapshot IDs for all three datastores. The runner rejects unresolved placeholders and incomplete snapshot metadata.

```powershell
Backend\.venv\Scripts\python.exe Backend\scripts\run_lawgic_integration_acceptance.py `
  --integration-config eval\config\integration-fixture.approved.json `
  --output eval\reports\integration-acceptance-report.json
```

This command is fail-closed and read-only:

- Neo4j runs all T01-T20/N01-N02 checks in read access mode.
- PostgreSQL runs six schema/workflow/reconciliation invariant checks inside a read-only transaction.
- Qdrant payload IDs and checksums must exactly match the deepest canonical Neo4j leaves.
- Any unavailable store, assertion failure, missing snapshot ID or checksum drift makes the aggregate report fail.

The template is intentionally not runnable evidence. Do not rename it to an approved config until the fixture and snapshot identifiers have been independently verified.

### Local synthetic runtime fixture

The repository includes a localhost-only, idempotent fixture loader for proving the LAWGIC execution invariants end to end. It refuses every non-loopback datastore URL and requires an explicit apply confirmation.

```powershell
Backend\.venv\Scripts\python.exe Backend\scripts\load_lawgic_integration_fixture.py

Backend\.venv\Scripts\python.exe Backend\scripts\load_lawgic_integration_fixture.py `
  --apply --yes `
  --output-config eval\config\integration-fixture.local.json
```

The first command is a non-mutating dry run. The applied fixture creates 10 immutable legal versions, an audited amendment commit, one dual-time misconception case and 8 ID-only Qdrant leaves. It is classified as `synthetic_integration_fixture`: a passing runtime report proves contract behavior, but it is not independent legal holdout evidence and cannot authorize release.

### Local temporal shadow benchmark

Run at least 100 measured reads across the V1, V2 and V3 dates:

```powershell
Backend\.venv\Scripts\python.exe Backend\scripts\run_lawgic_shadow_benchmark.py `
  --iterations 120 `
  --warmup 12

Backend\.venv\Scripts\python.exe Backend\scripts\run_lawgic_quality_gates.py `
  --manifest eval\manifest.local-shadow.json `
  --output eval\reports\l7-local-shadow-quality.json
```

The benchmark compares the canonical `TemporalLawService` output with a functionally equivalent direct Neo4j reference inside managed read transactions. It alternates execution order to reduce cache bias and fails on any leaf mismatch, exception, sample count below 100, or P95 regression above 20%. The generated system gold/prediction files are measured local evidence, but remain release-ineligible.
