# LAWGIC Core Implementation Plan

## Authoritative plan

Chi tiết đầy đủ nằm tại `docs/architecture/lawgic-core-execution-plan-v2.md`.

## Completed phases: L0 + PR-L1.1 + PR-L1.2 + PR-L2.1 safe preparation

### Objective

Khóa contract và fixture trước, sau đó sửa đường parse để giữ đầy đủ Điều–Khoản–Điểm mà chưa thay đổi QA production hoặc chạy migration thật.

### Tasks

- [x] Tạo `LegalProvisionVersion` và `CitationContractV2`.
- [x] Nâng ontology/constraints additive.
- [x] Thêm feature flags mặc định an toàn.
- [x] Tạo temporal fixture V1/V2/V3 và acceptance queries nền tảng.
- [x] Sửa `_build_tree()` để giữ `diem_list`, lineage và checksum.
- [x] Thêm test contract, parser round-trip và deepest-leaf fixture.
- [x] Chạy full backend tests và compile check.

### Success criteria

- Existing behavior v1 vẫn là mặc định.
- Parser tree giữ nguyên văn và ID của mọi Điểm trong fixture.
- Contract chặn interval sai và citation reference sai.
- Không có migration apply, QA v2 read hoặc amendment commit trong phase này.

## Completion note — 2026-07-19

- Backend: 105 tests passed.
- Compile check: passed.
- Ontology v2 JSON và T01–T10 acceptance query contract: passed.
- Các cờ v2 read/write/temporal/citation/amendment mặc định tắt.
- Không chạy migration và không thay đổi production QA path.


## Phase PR-L1.2 — Immutable Neo4j writer

### Tasks

- [x] Không tạo Khoản giả cho Điều không có Khoản.
- [x] Flatten và validate Điều/Khoản/Điểm thành immutable rows.
- [x] Ghi đủ ba cấp trong một managed transaction.
- [x] Ghi đồng thời compatibility fields v1 và contract v2 trên cùng node.
- [x] Chặn checksum, source và interval collision trước mutation.
- [x] Thêm Cypher guard chống concurrent overwrite.
- [x] Thêm report `written | idempotent | dry_run | conflict | invalid` theo từng cấp.
- [x] Nối writer sau `LEGAL_PROVISION_V2_WRITE`; mặc định vẫn tắt.
- [x] Mở rộng ingest API nhận temporal metadata.
- [x] Thêm repository/pipeline tests và full regression.

### Completion note — 2026-07-19

- Backend: 116 tests passed sau khi thêm 11 test PR-L1.2.
- Compile và whitespace checks: passed.
- Không chạy migration, không bật v2 read, không tạo `SUPERSEDED_BY` trong ingest thường.
- `dry_run=True` hiện là preflight cho một parsed document; migration inventory toàn kho chưa chạy.

## Previous next phase: L2 — implemented as safe preparation below

- Tạo collection `legal_provision` ID-only payload.
- Thêm migration inventory dry-run cho dữ liệu v1, raw-source coverage và collision report.
- Thêm reindex resumable và shadow count parity.
- Chỉ xem xét migration apply sau snapshot/staging Go/No-Go 1.

## Phase PR-L2.1 - Qdrant dual-index and migration safety tooling

### Completed

- [x] Added the additive `legal_provision` collection contract with ID-only payload and datetime indexes.
- [x] Added deepest-leaf dual-index after a successful/idempotent v2 Neo4j write.
- [x] Kept the legacy `khoan` index active while `LEGAL_PROVISION_V2_READ=false`.
- [x] Added stable UUID5 point IDs and checksum-aware skip/repair behavior.
- [x] Added a read-only legacy migration inventory with raw-source/Point coverage reasons.
- [x] Added resumable reindex with `--resume-from` and optional checkpoint file.
- [x] Added identity/checksum parity reporting between Neo4j and Qdrant.
- [x] Added an additive-only collection bootstrap; it never deletes or recreates a collection.
- [x] Added unit/integration coverage and full backend regression.

### Operational commands

```text
python Backend/scripts/migrate_temporal_v2.py --output work/temporal-v2-inventory.json
python Backend/scripts/bootstrap_qdrant_v2.py
python Backend/scripts/bootstrap_qdrant_v2.py --apply --yes
python Backend/scripts/reindex_legal_provisions.py --checkpoint-file work/legal-v2-checkpoint.json
python Backend/scripts/reindex_legal_provisions.py --apply --yes --checkpoint-file work/legal-v2-checkpoint.json
python Backend/scripts/compare_legal_v1_v2.py --output work/legal-v2-parity.json
```

The inventory and parity commands are read-only. Bootstrap/reindex require explicit `--apply --yes` before mutation. No live command was executed in this phase.

### Verification - 2026-07-19

- Focused Phase L2 tests: 21 passed.
- Full backend suite: 126 passed.
- Python compile and whitespace checks: passed.
- Live/staging Neo4j and Qdrant were not mutated.
- Graph migration apply remains deferred until snapshot, inventory review and staging Go/No-Go.
## Phase PR-L3.1/L3.2 - Temporal repository, service and read-only APIs

### Completed

- [x] Added a read-only Neo4j temporal repository using managed read transactions.
- [x] Added half-open effective-date filtering at provision level.
- [x] Added `law_as_of`, `get_provision`, `resolve_version`, `timeline`, `compare_versions` and `hydrate_candidates`.
- [x] Added deepest-leaf selection based on active `parent_lineage_id` values.
- [x] Added fail-closed overlap, invalid-contract and supersession-cycle checks.
- [x] Enforced public + approved visibility for Citizen reads.
- [x] Added Admin as-of/timeline/compare APIs and Citizen as-of provision API.
- [x] Protected every new API with both v2 read and temporal feature flags.
- [x] Added repository, service, API and partial-amendment acceptance tests.
- [x] Removed references to the six intentionally deleted legacy documentation files.

### API contract

```text
GET /admin/legal/documents/{id}/as-of?date=YYYY-MM-DD
GET /admin/legal/provisions/{id}/timeline
GET /admin/legal/provisions/compare?old_id=...&new_id=...
GET /citizen/legal/provisions/{id}?as_of=YYYY-MM-DD
```

The compare endpoint uses query parameters because legal provision IDs may contain `/`; this avoids ambiguous two-ID path routing.

### Verification - 2026-07-19

- Focused L3 + temporal contract tests: 40 passed.
- Full backend suite: 157 passed.
- Python compileall and Git whitespace checks: passed.
- No live/staging Neo4j or Qdrant mutation was executed.
- `LEGAL_PROVISION_V2_READ=false` and `TEMPORAL_LAW_V2=false` remain the defaults.
- Production QA still uses v1 until the L4 citation/retrieval gates pass.

## Phase PR-L4.1 - Hybrid legal retrieval

### Completed

- [x] Added a typed retrieval contract with exact, lexical, vector, graph and reranker evidence.
- [x] Added strict exact-reference handling for provision IDs, lineage IDs and document numbers.
- [x] Added ID-only Neo4j full-text discovery and a bounded two-hop graph expansion allowlist.
- [x] Added Qdrant vector discovery with `public + approved` Citizen filtering.
- [x] Added application-side RRF by lineage; raw full-text and cosine scores are never compared directly.
- [x] Added mandatory `TemporalLawService.hydrate_candidates()` before any legal text is returned.
- [x] Added stale physical-ID resolution to the version effective at the requested date.
- [x] Added a deterministic token-overlap reranker baseline without a new model dependency.
- [x] Added five measurable profiles: `lexical`, `vector`, `hybrid`, `hybrid_graph`, `hybrid_graph_rerank`.
- [x] Added a read-only ablation harness with Recall@K, MRR and nDCG@K.
- [x] Added the `legal_provision_text_ft` Neo4j index and synchronized Qdrant `review_status` payload/index contracts.

### Retrieval safety contract

```text
source discovery (IDs only)
  -> RRF by lineage
  -> bounded graph expansion
  -> temporal Neo4j hydration at as_of
  -> optional rerank
  -> canonical LegalProvisionVersion output
```

Qdrant text is never copied into a result. An explicit legal reference that is not present returns no candidates and cannot fall through to semantic retrieval. Citizen candidates must be public and approved at discovery and hydration time.

### Read-only ablation command

```text
python Backend/scripts/eval_legal_retrieval_v2.py --gold Data/gold/legal_retrieval_v2.json --k 5 --output work/legal-retrieval-v2-report.json
```

Gold input must be a non-empty list, or an object with a `cases` list:

```json
{
  "cases": [{
    "case_id": "threshold-before-change",
    "query": "Nguong ap dung la bao nhieu?",
    "as_of": "2026-06-30",
    "audience": "citizen",
    "expected_lineage_ids": ["01/2026/ND-CP::D5.K2.Pa"]
  }]
}
```

The runner reports source errors as zero-scoring cases instead of excluding them. No benchmark result is claimed until a reviewed gold file is supplied and the command is run against an approved environment.

### Verification - 2026-07-19

- Focused retrieval/index/evaluation tests: 39 passed.
- Full backend suite: 187 passed.
- Python compileall, JSON contract parsing and Git whitespace checks: passed.
- No live/staging Neo4j or Qdrant mutation was executed.
- No v2 feature flag was enabled; production QA remains on v1.
- L4B citation wiring is deliberately not included in PR-L4.1.
## Phase PR-L4.2/L4.3 - Canonical Citation v2 and strict refusal

### Completed

- [x] Added strict untrusted draft models for claims and citation pointers with extra fields forbidden.
- [x] Added `text_checksum` to Citation v2 and validated node identity from lineage, date and checksum.
- [x] Added exact physical-version hydration that never redirects a stale citation to a newer version.
- [x] Added canonical Neo4j validation for node visibility, effective date, checksum and exact quote containment.
- [x] Restricted model citations to node IDs returned by canonical retrieval.
- [x] Added reciprocal claim/citation mapping validation and NLI validation for every declared edge.
- [x] Added hard refusal for unmapped material amounts, rates, deadlines, duties, prohibitions and penalties.
- [x] Added an isolated Citation v2 QA service using the L4A retrieval service.
- [x] Wired Admin/Citizen QA through a shared factory while preserving the v1 service when flags are off.
- [x] Required `LEGAL_PROVISION_V2_READ`, `TEMPORAL_LAW_V2` and `QA_CITATION_V2` together before dispatch.
- [x] Kept Citation v2 uncached during the validation rollout.
- [x] Extended the read-only acceptance catalog from T01-T10 to T01-T15.

### Validation order

```text
untrusted Pydantic draft
  -> retrieved-node allowlist
  -> exact physical Neo4j hydration at as_of
  -> public + approved visibility
  -> canonical text checksum
  -> exact normalized quote substring
  -> every reciprocal claim-citation edge passes NLI
  -> every material answer statement has a validated claim
  -> CitationContractV2 answered | refused
```

Retrieval may resolve a stale candidate by lineage before generation. Citation validation is stricter: the final `node_id` itself must be the physical version effective on `as_of`; it is never silently rewritten.

### Rollout contract

Citation v2 dispatch occurs only when all three settings are true:

```text
LEGAL_PROVISION_V2_READ=true
TEMPORAL_LAW_V2=true
QA_CITATION_V2=true
```

Defaults remain false. If `QA_CITATION_V2` is enabled without the two read prerequisites, QA returns `citation_v2_dependencies_disabled` and does not call the v2 delegate.

### Verification - 2026-07-20

- Focused L4B canonical/QA/temporal tests: 66 passed.
- Full backend suite: 219 passed.
- Python compileall, import smoke and Git whitespace checks: passed.
- Acceptance T11-T15 are present and covered by deterministic fixtures.
- No live/staging Neo4j or Qdrant mutation was executed.
- No feature flag was enabled in an environment; production QA remains on v1.
- Frontend CitationCard/timeline work remains L4C.
## Phase PR-L4.4 - Citation and temporal frontend

### Completed

- [x] Added a single response adapter for both legacy QA v1 and Citation Contract v2.
- [x] Added explicit UI states for `answered` and strict `refused` responses.
- [x] Upgraded `CitationCard` to show physical node metadata, Điều/Khoản/Điểm, effective interval, `as_of`, claim support and entailment score.
- [x] Kept `khoan_id` as a compatibility alias while all new rendering uses `node_id` when available.
- [x] Added expandable canonical quote display and Neo4j validation provenance.
- [x] Added a shared accessible history panel for Citizen/Admin with timeline selection and adjacent-version comparison.
- [x] Added public read-only timeline/compare routes backed by Citizen visibility filtering.
- [x] Wired the adapter into Citizen Ask, Citizen floating chat and Admin QA.
- [x] Added deterministic contract tests for answered v2, refused v2 and legacy v1.
- [x] Kept every v2 environment flag disabled.

### Verification - 2026-07-20

- Frontend response-contract tests: 3 passed.
- Frontend TypeScript + Vite production build: passed.
- Frontend lint: passed with one pre-existing Fast Refresh warning in `CitizenChrome.tsx`.
- Focused temporal/citation backend tests: 66 passed.
- Full backend suite: 219 passed.
- No live/staging data mutation or feature-flag activation was performed.

### Next phase

Phase L5 / PR-L5.1 starts the legal amendment engine: explicit-reference parsing, candidate matching and deterministic change classification. Review persistence, atomic commit and Admin approval UI remain separate slices behind `AMENDMENT_COMMIT_V2=false`.
## Phase PR-L5.1 - Amendment preview engine

### Completed

- [x] Added immutable preview contracts with a hard `commit_allowed=false` invariant.
- [x] Parsed explicit Vietnamese amendment actions, deepest Article/Clause/Point coordinates and quoted phrase replacements.
- [x] Loaded every old/new physical ID through `TemporalLawService.load_versions_by_ids()` so preview text is canonical Neo4j content.
- [x] Rejected fabricated IDs, overlapping old/new physical IDs and candidates outside the requested logical document.
- [x] Added explainable weighted matching and deterministic one-to-one selection.
- [x] Added conservative legal change classification and explicit unmatched `ADDED`/`REMOVED` review records.
- [x] Marked split, merge, uncertain, invalid-date, multi-target and phrase-mismatch results as mandatory review.
- [x] Kept all other results in human review; no result is eligible for auto-approval before the independent 95% precision gate.
- [x] Added an Admin-only preview route behind `LEGAL_PROVISION_V2_READ` and `AMENDMENT_PREVIEW_V2`.
- [x] Kept `AMENDMENT_COMMIT_V2=false`; no review persistence or graph mutation is part of this slice.

### Preview flow

```text
Admin request with immutable old/new provision IDs
  -> exact canonical Neo4j hydration
  -> logical-document boundary validation
  -> explicit amendment-reference parsing
  -> explainable score matrix
  -> deterministic one-to-one selection
  -> conservative change classification
  -> human/mandatory review preview
  -> no persistence and no graph write
```

### Verification - 2026-07-20

- Focused amendment and temporal contract tests: 59 passed.
- Full backend suite: 242 passed.
- Python compileall and Git whitespace checks: passed.
- No live/staging mutation and no feature flag activation were performed.

### Next phase

PR-L5.2 adds review persistence and Admin workflow APIs only. Transactional Neo4j interval closure and `SUPERSEDED_BY` creation remain PR-L5.3 and stay disabled behind `AMENDMENT_COMMIT_V2=false`.

## Phase PR-L5.2 - Amendment review persistence and APIs

### Completed

- [x] Added `Data/schema/postgres/011_amendment_reviews.sql` with batches, candidates and append-only audit events.
- [x] Added strict review contracts with immutable `commit_allowed=false` and `auto_approve_eligible=false`.
- [x] Added PostgreSQL repository operations using parameterized SQL and managed transactions.
- [x] Added request-hash idempotency and explicit conflict reporting for key reuse.
- [x] Added batch and candidate revision guards for optimistic concurrency.
- [x] Added canonical validation for reviewer-edited old/new IDs and target-document boundaries.
- [x] Reset stale score/reference evidence and recompute the diff whenever a reviewer changes a pair.
- [x] Added workflow gates for draft, submission, candidate decisions and final review approval/rejection.
- [x] Restricted review persistence APIs to `admin_phap_che`.
- [x] Added `AMENDMENT_REVIEW_V2=false` independently from preview and commit flags.
- [x] Kept PostgreSQL approval semantically separate from a legal-graph commit.

### API contract

```text
POST  /admin/legal/amendment-reviews
GET   /admin/legal/amendment-reviews
GET   /admin/legal/amendment-reviews/{batch_id}
PATCH /admin/legal/amendment-reviews/{batch_id}/candidates/{candidate_id}
POST  /admin/legal/amendment-reviews/{batch_id}/submit
POST  /admin/legal/amendment-reviews/{batch_id}/decision
```

Every mutating review request uses an idempotency key or expected revision. An `approved` review remains `commit_allowed=false` and cannot mutate Neo4j.

### Verification - 2026-07-21

- Focused L5.2/L5.1/contract tests: 49 passed.
- Full backend suite: 259 passed.
- Python compileall and Git whitespace checks: passed.
- No migration apply, environment flag activation or live/staging mutation was performed.

### Next phase

PR-L5.3 implements the separately gated transactional commit and Admin review UI. The commit service must re-read canonical checksums and intervals, then either close the old interval and create all temporal edges atomically or make no graph change.

## Phase PR-L5.3 - Transactional amendment commit and Admin UI

### Completed

- [x] Added PostgreSQL commit reconciliation metadata in `012_amendment_commits.sql`.
- [x] Added strict deterministic commit operations and rejected unchanged, split, merge and uncertain candidates before graph write.
- [x] Re-hydrated immutable canonical versions and revalidated document, lineage, level, checksum and effective-date invariants.
- [x] Added a single managed Neo4j transaction for each approved batch with conflict guards and full rollback behavior.
- [x] Added idempotent `SUPERSEDED_BY` and `AMENDED_BY` writes, exclusive old-interval closure and new-version approval.
- [x] Added retry-safe PostgreSQL reconciliation after graph success.
- [x] Added a legal-role-only commit API behind `AMENDMENT_COMMIT_V2=false` and the preceding legal feature flags.
- [x] Added an Admin amendment-review UI with candidate evidence, workflow actions and explicit commit confirmation.
- [x] Added T16/T17 acceptance queries and commit-key properties to the ontology relationship contract.

### Cross-database consistency contract

PostgreSQL and Neo4j do not share a distributed transaction. The implementation therefore commits the complete graph batch atomically first and stores the graph report in PostgreSQL second. Every graph edge carries the same review ID and commit key. If PostgreSQL reconciliation fails, retrying the same key recognizes the already committed graph state and completes PostgreSQL without duplicating or changing the legal graph. A different key fails closed.

### API contract

```text
POST /admin/legal/amendment-reviews/{batch_id}/commit
```

The batch must be `approved`, its revision must match, all accepted candidates must be deterministic, and the caller must have `admin_phap_che`. Approval alone never mutates Neo4j.

### Verification - 2026-07-21

- Focused L5.3/L5.2/L5.1/temporal tests: 64 passed.
- Full backend suite: 274 passed; Python compileall passed.
- Frontend contract tests: 6 passed; production build and lint passed.
- No migration apply, environment flag activation or live/staging mutation was performed.

### Next phase

PR-L6.1 introduces source-neutral misconception evidence and clustering, starting with news pages and retaining adapters for later social-network ingestion. PR-L6.2 adds historical/current verdicts and explainable risk scoring.

## Phase PR-L6.1 - Source-neutral misconception evidence and clustering

### Completed

- [x] Added strict occurrence provenance contracts with exact offsets, canonical URL, publication timestamp and verified content hash.
- [x] Added deterministic normalization/signatures and conservative cluster matching.
- [x] Prevented automatic merge when numbers or negation markers differ.
- [x] Added `Misconception` ontology, uniqueness/indexes and `INSTANCE_OF`, `CONTRADICTS`, `CANH_BAO_VE` relationships.
- [x] Added one managed Neo4j write transaction per occurrence assignment with competing-cluster guard.
- [x] Integrated assignment after canonical claim persistence in the shared news/social worker.
- [x] Grouped eligible alerts by misconception ID when present and retained the legacy topic/provision fallback.
- [x] Added Admin list/detail APIs behind `MISCONCEPTION_CLUSTER_V2=false`.
- [x] Added N01/N02 acceptance queries for provenance completeness and single-cluster assignment.

### Clustering contract

```text
ContentItem (news/social/video/comment/forum)
  -> source-grounded YKien occurrence
  -> exact provenance validation
  -> topic + legal-anchor candidate lookup
  -> number/negation compatibility guard
  -> deterministic similarity >= 0.84
  -> INSTANCE_OF Misconception
  -> CONTRADICTS canonical legal anchor
  -> optional alert linkage
```

Clustering is intentionally precision-first. A claim with a changed amount, threshold, date or negation becomes a separate cluster even when the remaining wording is similar.

### API contract

```text
GET /admin/misconceptions
GET /admin/misconceptions/{misconception_id}
```

Both endpoints require Admin authentication and remain hidden unless `MISCONCEPTION_CLUSTER_V2=true`.

### Verification - 2026-07-21

- Focused L6.1/news/social/temporal tests: 33 passed.
- Full backend suite: 286 passed; Python compileall passed.
- No schema apply, feature-flag activation, crawl or external mutation was performed.

### Next phase

PR-L6.2 adds dual-time legal evaluation, `OUTDATED_BUT_PREVIOUSLY_TRUE`, explainable risk factors and the Admin misconception/risk UI. It remains separately gated by `MISCONCEPTION_TEMPORAL_V2=false`.

## Phase PR-L6.2 - Dual-time verdict, risk score and Admin UI

### Completed

- [x] Added immutable historical/current legal-check and temporal-evaluation contracts.
- [x] Used `TemporalLawService.resolve_version()` at publication date and current as-of date.
- [x] Required two checksum-verified physical versions and strict NLI gates for the outdated verdict.
- [x] Added fail-closed outcomes for missing, neutral, low-confidence and inconsistent evidence.
- [x] Persisted evaluation nodes and both legal-basis relationships in one managed Neo4j transaction.
- [x] Added idempotent evaluation IDs and prevented an existing evaluation ID from being rebound to another claim/result.
- [x] Added eight weighted risk factors with a provenance deduction and fixed severity thresholds.
- [x] Integrated temporal evaluation and risk-aware alert severity into the shared source pipeline.
- [x] Added a legal-role evaluate endpoint and safe list/detail filters.
- [x] Added an Admin misconception page with source evidence, old/new law cards and risk breakdown.
- [x] Added T18/T19 acceptance queries.

### Verdict contract

```text
claim + publication timestamp + legal anchor
  -> resolve historical immutable provision
  -> resolve current immutable provision
  -> NLI(claim, historical text)
  -> NLI(claim, current text)
  -> strict confidence/review gates
  -> OUTDATED only for historical KHOP + current MAU_THUAN + different IDs
  -> persist both bases and checksums atomically
```

### API contract

```text
POST /admin/misconceptions/{misconception_id}/evaluate
{
  "current_as_of": "2026-07-21",
  "dry_run": false
}
```

The write action requires `admin_phap_che`. Read APIs remain available to authenticated Admin users when clustering is enabled.

### Verification - 2026-07-21

- Focused L6.2/L6.1/social/contract tests: 38 passed.
- Full backend suite: 298 passed; Python compileall passed.
- Frontend contract tests: 8 passed; production build and lint passed.
- No schema apply, crawl, flag activation or live/staging mutation was performed.

### Next phase

PR-L7.1 builds independent evaluation datasets, real datastore integration acceptance, benchmark reports and rollout go/no-go evidence.

## Phase L7.1A — evaluation, CI and demo contracts

### Completed

- [x] Added `Backend/app/evaluation/lawgic_quality.py` with objective metrics and per-label reports.
- [x] Added `Backend/scripts/run_lawgic_quality_gates.py` with strict release-evidence validation.
- [x] Added separated synthetic gold/prediction fixtures for eight evaluation suites.
- [x] Added five retrieval profiles and explicit vector-to-full ablation delta.
- [x] Added T20 and a catalog validator for T01-T20/N01-N02.
- [x] Added opt-in read-only Neo4j execution with caller-supplied parameters and assertions.
- [x] Added CI smoke gates, persisted reports and three locked demo cases.
- [x] Added fail-closed tests proving independently reviewed evidence still receives `NO_GO` when a blocking metric regresses.

### Commands

```text
python Backend/scripts/run_lawgic_quality_gates.py --manifest eval/manifest.smoke.json --output eval/reports/l7-smoke-report.json
python Backend/scripts/run_lawgic_acceptance.py --catalog Data/schema/acceptance_queries.cypher --output eval/reports/acceptance-catalog-report.json
```

`--release` is intentionally stricter than the CI smoke mode. The bundled report has all smoke contract gates passing but `release_decision=NO_GO`, because synthetic cases are not independently reviewed release evidence.

### Verification - 2026-07-21

- Focused L7 tests: 8 passed.
- Current full backend collection: 230 passed; compileall passed.
- Acceptance catalog: 22/22 IDs present.
- Frontend: 8 contract tests, production build and lint passed.
- Real datastore acceptance, independent holdout metrics, snapshots and shadow-read P95 remain pending.

## Phase L6.2B — lineage and syndication hardening

### Completed

- [x] Reject dual-time legal bases from different lineages before an outdated verdict can be emitted.
- [x] Bind evaluation IDs to claim/publication/lineage/checksum evidence, not only occurrence and as-of date.
- [x] Re-check both canonical checksums and lineage IDs inside the managed Neo4j write transaction.
- [x] Validate immutable occurrence/evaluation fields on idempotent replay.
- [x] Count independent source bodies by `content_hash` and preserve provider count as a separate dimension.
- [x] Use independent bodies for risk velocity/diversity and alert volume so syndicated news copies cannot manufacture severity.
- [x] Propagate content hashes through the worker and recent-signal repository path.
- [x] Explain occurrences, independent content and providers separately in the Admin UI.

### Verification - 2026-07-21

- Focused L6.2/L6.1/worker/evaluation suite: 54 passed.
- Full backend suite: 234 passed; compileall passed.
- Frontend contract suite: 9 passed; build and lint passed.
- No live/staging mutation or feature activation was performed.

## Phase L7.1B start — independent holdout provenance

### Completed

- [x] Require two distinct reviewer IDs for every `independent_holdout` suite.
- [x] Require completed adjudication and a non-empty guideline version.
- [x] Require a valid SHA-256 checksum for the frozen raw-source dataset.
- [x] Report provenance failures as `review_provenance_issues` and keep the release decision at `NO_GO`.
- [x] Add a reusable metadata template under `eval/templates/`.
- [x] Add focused fail-closed tests for incomplete review provenance.

### Verification - 2026-07-21

- 12 focused evaluation/acceptance tests passed.
- Smoke gates passed but remained intentionally ineligible for release.
- Python compileall and Git whitespace checks passed.
- No external datastore was contacted and no rollout flag was enabled.

### Remaining L7.1B work

Independent reviewers must now produce and adjudicate the real holdout labels. Local read-only datastore acceptance and local shadow measurements are complete; after the raw-source bundle is frozen and production-like shadow evidence is captured, invoke the evaluator with `--release`. The repository must continue returning `NO_GO` until both provenance and metric gates pass.

### Multi-datastore acceptance harness

- [x] Add a single aggregate runner for Neo4j, PostgreSQL and Qdrant.
- [x] Force Neo4j acceptance and leaf-parity sessions into read access mode.
- [x] Execute PostgreSQL invariants inside a read-only transaction.
- [x] Require exact Qdrant ID/checksum parity with canonical Neo4j leaves.
- [x] Require fixture and snapshot identity for all three stores.
- [x] Reject unresolved template placeholders before opening datastore connections.
- [x] Preserve per-store errors in one aggregate fail-closed report.
- [x] Add composite assertion support for multi-field acceptance contracts.
- [x] Add focused tests and an approved-fixture configuration template.

Focused verification: 31 tests passed. The initial Docker service permission error was resolved by launching Docker Desktop in the user session; runtime evidence is recorded below. No external environment was contacted.

### Local runtime acceptance evidence

- [x] Start the localhost Docker data stack.
- [x] Apply additive Neo4j/PostgreSQL/Qdrant schema contracts.
- [x] Load the idempotent synthetic LAWGIC integration fixture.
- [x] Run all 22 Neo4j acceptance checks in read mode.
- [x] Run seven PostgreSQL invariants in a read-only transaction.
- [x] Prove exact 8/8 Qdrant ID and checksum parity.
- [x] Persist the aggregate runtime report with `passed=true`.

The first runtime round exposed and corrected two harness defects: Neo4j `collect(null)` semantics for T05 and Windows console UTF-8 output. T06 was also tightened to require the complete maximal version path. This local synthetic evidence does not change the release decision; independent holdouts and production-like shadow evidence remain mandatory.

### Measured local temporal shadow reads

- [x] Add a minimum-100-case temporal workload over three effective-date regimes.
- [x] Compare candidate and baseline with equivalent payloads and managed read transactions.
- [x] Require exact leaf parity and zero failures.
- [x] Enforce the 1.2 P95 regression gate.
- [x] Export measured system-suite gold and predictions.
- [x] Fix Neo4j `Date`/`DateTime` conversion at the repository boundary.

Measured local result after architecture hardening: 120/120 parity, zero failures, candidate P95 27.3458 ms, baseline P95 25.4420 ms, regression ratio 1.074829, zero external cost and zero LLM calls. This is local synthetic evidence, not release authorization.

### Amendment commit reconciliation observability

- [x] Scan `AMENDED_BY` commit stamps through an explicit Neo4j read transaction.
- [x] Cross-check graph review IDs and commit keys against PostgreSQL workflow, commit result and append-only audit evidence.
- [x] Fail the health report to `degraded` for missing, mismatched or incomplete reconciliation provenance.
- [x] Expose a legal-admin read-only health endpoint.
- [x] Schedule an opt-in monitor on the legal worker, with no automatic graph or PostgreSQL repair.
- [x] Keep the monitor flag disabled by default.

Fresh local result: one graph commit scanned, zero issues, 269 backend tests passed, 22/7/8 datastore acceptance passed and the isolated shadow P95 ratio was 1.06108. Operational retry must use the original idempotency key; this monitor does not replace that rule.
