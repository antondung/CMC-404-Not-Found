# LAWGIC Core Progress

## Status: Phase L7.1B architecture parity review and local gates passed; independent legal holdouts and production-like shadow evidence remain

## Quick reference

- Research: `docs/lawgic-core/RESEARCH.md`
- Implementation: `docs/lawgic-core/IMPLEMENTATION.md`
- Execution plan: `docs/architecture/lawgic-core-execution-plan-v2.md`

## Tasks completed

- Baseline code, khoảng hở, execution plan v2 và ba ADR đã được xác nhận.
- Thêm immutable `LegalProvisionVersion`, lineage/version ID, checksum và interval validation.
- Thêm `CitationContractV2` claim-level với mapping hai chiều và fail-closed refusal.
- Nâng ontology 2.0.0, constraints/index additive và quan hệ `SUPERSEDED_BY`/`AMENDED_BY`.
- Thêm feature flags v2 với read/write/temporal/citation/amendment mặc định tắt.
- Thêm temporal fixture V1/V2/V3: partial amendment, future, repeal, Khoản không Điểm và Điều không Khoản.
- Thêm acceptance query contract T01–T10.
- Sửa `_build_tree()` giữ `diem_list`, canonical ID, lineage, parent lineage và checksum.
- Hoàn thành immutable Neo4j writer cho Điều/Khoản/Điểm trong một managed transaction.
- Bỏ việc tự tạo Khoản giả cho Điều không có Khoản.
- Thêm preflight/collision report, concurrent Cypher guard và per-document dry-run.
- Nối atomic dual-schema writer sau `LEGAL_PROVISION_V2_WRITE`; default v1 không đổi.
- Mở rộng Admin ingest request nhận ngày hiệu lực và logical lineage metadata.

## Verification

- Latest full backend suite: 269 tests passed.
- Focused L7 evaluation/integration/shadow/temporal suite: 31 tests passed.
- Frontend contract suite: 9 tests passed; production build passed.
- Python compileall, report JSON parsing and Git whitespace check: passed.
- Local runtime acceptance: Neo4j 22/22, PostgreSQL 7/7 and Qdrant 8/8 exact ID/checksum parity.
- Local temporal shadow: 120/120 parity, zero failures and P95 regression ratio 1.06108 (limit 1.2).
- Release guard rejected `--release` as intended; every rollout flag remains off and no live/staging store was contacted.

## Blockers

- Release evidence still needs frozen legal holdouts labelled by two distinct reviewers and completed adjudication.
- Production-like shadow evidence is still required before a release `GO`; local synthetic evidence cannot authorize rollout.

## Session log

### 2026-07-19

- Bắt đầu Phase L0 + PR-L1.1.
- Hoàn thành contract, schema additive, flags, fixture, acceptance queries và parser preservation.
- Giữ scope an toàn: chưa sửa QA production, chưa chạy migration thật, chưa bật writer/read v2.
- Hoàn thành PR-L1.2; writer v2 vẫn sau feature flag và không đóng interval trong ingest thường.
- Live Neo4j migration/integration mutation chưa chạy trên dữ liệu người dùng.

## Files changed

- `Backend/app/domain/legal_provision.py`
- `Backend/app/domain/citation_contract.py`
- `Backend/app/domain/legal_write.py`
- `Backend/app/adapters/neo4j_legal_v2.py`
- `Backend/app/adapters/neo4j_legal.py`
- `Backend/app/api/admin/legal.py`
- `Backend/app/pipelines/legal/normalize.py`
- `Backend/app/pipelines/legal/pipeline.py`
- `Backend/app/config.py`
- `Backend/.env.example`
- `Backend/tests/fixtures/temporal_legal.py`
- `Backend/tests/test_legal_temporal_contracts.py`
- `Backend/tests/test_neo4j_legal_v2.py`
- `Data/schema/ontology.json`
- `Data/schema/neo4j_constraints.cypher`
- `Data/schema/acceptance_queries.cypher`

## Previous next task: Phase L2 (superseded by the update below)

- Tạo Qdrant collection `legal_provision` với ID-only payload.
- Viết migration inventory dry-run, raw-source coverage và collision report cho dữ liệu v1.
- Thêm resumable reindex và shadow parity v1/v2.
- Không chạy migration apply trước snapshot/staging Go/No-Go 1.

## Phase L2 update - 2026-07-19

Completed in code:

- Qdrant `legal_provision` v2 collection contract with ID-only payload.
- Feature-flagged deepest-leaf dual-index while legacy `khoan` remains available.
- Deterministic UUID5 IDs, checksum repair and resumable checkpoint contract.
- Read-only temporal migration inventory with per-document re-ingest reasons.
- Additive-only Qdrant bootstrap and Neo4j/Qdrant identity+checksum parity report.
- 21 focused tests and 126 full backend tests passed; compile and diff checks passed.

Not executed against live services:

- No collection create/index mutation.
- No vector reindex.
- No Neo4j migration apply.
- No v2 read-path switch.

Historical L2 rollout gate:

1. The six tracked documentation deletions were confirmed as intentional; active references were removed.
2. Take Neo4j/Qdrant snapshots in staging.
3. Run inventory and bootstrap dry-runs.
4. Review documents marked `requires_reingest` or `requires_source_review`.
5. Approve additive bootstrap/reindex, then require exact ID+checksum parity before L3.
## Phase L3 update - 2026-07-19

Completed in code:

- Read-only `Neo4jTemporalRepository` with managed transaction support and half-open interval queries.
- Canonical `TemporalLawService` with deepest-leaf selection, public visibility enforcement and immutable contract hydration.
- Fail-closed checks for duplicate active versions, invalid checksums/coordinates, interval overlap and supersession cycles.
- Stale physical candidate hydration to the active lineage version for the upcoming L4 retrieval path.
- Feature-flagged Admin as-of/timeline/compare APIs and Citizen as-of provision API.
- Dead references to the six intentionally deleted legacy documentation files were removed from active docs.

Verification:

- 40 focused L3/temporal tests passed.
- 157 full backend tests passed.
- Compileall and whitespace checks passed.
- No live or staging data mutation was performed; v2 read and temporal flags remain off.

Next phase:

1. Build hybrid retrieval over exact + lexical + Qdrant + graph candidates.
2. Hydrate every candidate through `TemporalLawService` at the requested date.
3. Connect Citation Contract v2 and strict claim-level grounding.
4. Keep Citizen rollout disabled until citation validity and refusal gates pass.
## Phase L4A start - 2026-07-19

In progress:

- Define ID-only retrieval candidates and application-side RRF by lineage.
- Add explicit-reference, Neo4j full-text, Qdrant vector and bounded graph sources.
- Require canonical temporal hydration before returning candidate text.
- Add deterministic reranker baseline and five-profile ablation harness.
- Keep QA routes and Citizen rollout unchanged until L4B/L4C grounding gates pass.

## Phase L4A completion - 2026-07-19

Completed in code:

- Typed ID-only candidate and evidence contracts for exact, lexical, vector, graph and reranker sources.
- Strict fail-closed exact lookup for physical IDs, lineage IDs and document numbers.
- Neo4j full-text discovery plus bounded two-hop graph expansion.
- Qdrant vector discovery with `public + approved` filtering.
- Application-side RRF deduplicated by lineage and mandatory temporal Neo4j hydration.
- Stale vector/full-text IDs resolve to the legal version effective at `as_of`.
- Five retrieval profiles and a deterministic reranker baseline.
- Read-only gold-set ablation with Recall@K, MRR and nDCG@K; source failures remain visible and score zero.
- Qdrant payload/bootstrap contracts now include `review_status`.

Verification:

- 39 focused L4A tests passed.
- 187 full backend tests passed.
- Compileall, JSON parsing and Git whitespace checks passed.
- No live/staging data mutation, feature-flag activation or QA route switch was performed.

Next phase — L4B:

1. Validate the existing Citation Contract v2 against canonical retrieval candidates.
2. Map answer claims to citations in both directions.
3. Enforce quote checksum, effective-date and claim-support checks.
4. Add strict refusal when any material claim lacks valid support.
5. Wire QA only behind `QA_CITATION_V2`, keeping Citizen rollout disabled until acceptance gates pass.
## Phase L4B completion - 2026-07-20

Completed in code:

- Untrusted Pydantic draft boundary for model-generated claims and citation pointers.
- Exact physical-node Citation v2 validation from Neo4j at `as_of` with no stale-ID rewrite.
- Canonical identity, coordinate, interval, text-checksum and exact-quote validation.
- Retrieval allowlist enforcement so a model cannot cite a valid but unrelated graph node.
- Per-edge NLI entailment and reciprocal claim/citation mapping.
- Strict refusal for unsupported or unmapped material legal statements.
- Isolated `LegalQAV2Service` and shared QA factory for Admin/Citizen routes.
- Three-flag dispatch gate: v2 read + temporal + citation must all be enabled.
- Read-only acceptance catalog extended through T15.

Verification:

- 66 focused L4B tests passed.
- 219 full backend tests passed.
- Compileall, import smoke and Git whitespace checks passed.
- No live/staging mutation or feature-flag activation was performed.

Next phase — L4C:

1. Add frontend response adapters that keep the v1 response readable when Citation v2 is off.
2. Render node level, Điều/Khoản/Điểm, effective interval, `as_of` and claim-support status.
3. Add timeline and compare links from CitationCard.
4. Add frontend tests/build and only then prepare a shadow-read rollout plan.
## Phase L4C completion - 2026-07-20

Completed in code:

- Shared v1/v2 QA response adapter for Citizen Ask, floating chat and Admin QA.
- Citation v2 cards with exact legal coordinates, effective interval, `as_of`, support status, entailment score and canonical-source indicator.
- Strict refusal state with readable public explanation and technical reason code where available.
- Public read-only timeline and compare endpoints that retain temporal flags and Citizen visibility filtering.
- Accessible Citizen/Admin history dialog with focus containment, Escape close, focus restoration, timeline selection and adjacent-version diff.
- Legacy `khoan_id` rendering remains compatible while v2 uses `node_id`.

Verification:

- 3 frontend contract tests passed.
- Frontend production build passed.
- Frontend lint passed with one pre-existing Fast Refresh warning.
- 66 focused backend tests passed.
- 219 full backend tests passed.
- No live/staging mutation or rollout flag activation was performed.

Next phase — L5 / PR-L5.1:

1. Parse explicit amendment targets at Điều/Khoản/Điểm level.
2. Match old/new immutable provision candidates with explainable score breakdown.
3. Classify `UNCHANGED | REWORDED | TIGHTENED | LOOSENED | ADDED | REMOVED | SPLIT | MERGED | UNCERTAIN`.
4. Keep all proposed pairs in preview/review mode; do not commit graph changes yet.
## Phase L5.1 start - 2026-07-20

Scope locked:

- Parse explicit Vietnamese amendment targets and phrase replacements.
- Load all old/new candidate texts canonically by immutable Neo4j IDs.
- Produce explainable match scores and conservative change types.
- Keep `commit_allowed=false`; no interval closure or temporal edge writes.
- Keep high-confidence proposals in human review until independent pairing precision reaches 95%.
## Phase L5.1 completion - 2026-07-20

Completed in code:

- Added strict amendment-domain contracts for explicit references, score breakdowns, diffs, paired matches and unmatched `ADDED`/`REMOVED` candidates.
- Added Vietnamese explicit amendment parsing for Article/Clause/Point targets and quoted phrase replacement.
- Added explainable one-to-one candidate matching with coordinate, lexical, numeric and legal-term signals.
- Added conservative deterministic classification for `UNCHANGED | REWORDED | TIGHTENED | LOOSENED | ADDED | REMOVED | SPLIT | MERGED | UNCERTAIN`.
- Hydrated both old and new immutable candidate IDs from the canonical temporal Neo4j boundary; cross-document or fabricated candidates fail closed.
- Required mandatory review when effective dates regress, targets are ambiguous, phrase replacements do not match canonical text, or the change is split/merge/uncertain.
- Added Admin-only `POST /admin/legal/amendments/preview` behind `AMENDMENT_PREVIEW_V2=false` and the legal v2 read flag.
- Kept `commit_allowed=false` and `auto_approve_eligible=false` for every result until independent pairing precision reaches 95%.
- Performed no interval closure, `SUPERSEDED_BY` write, live/staging mutation or feature-flag activation.

Verification:

- 59 focused amendment/temporal contract tests passed.
- 242 full backend tests passed.
- Python compileall and Git whitespace checks passed.
- The only test warning is the existing Windows pytest-cache permission warning; it does not affect test execution.

Next phase — L5.2:

1. Add PostgreSQL review-batch and candidate persistence with immutable audit fields.
2. Add Admin list/detail/edit/submit-review APIs with optimistic concurrency and idempotency.
3. Keep review persistence separate from Neo4j commit; `AMENDMENT_COMMIT_V2` remains false.
4. Build deterministic amendment gold data and measure pairing precision before any auto-approve path exists.

## Phase L5.2 completion - 2026-07-21

Completed in code:

- Added additive PostgreSQL migration `011_amendment_reviews.sql` for review batches, candidates and append-only audit events.
- Enforced database checks that `commit_allowed=false` and `auto_approve_eligible=false` throughout L5.2.
- Added strict domain contracts and workflow states: `draft -> in_review -> approved|rejected`.
- Added idempotent batch creation with request hashes and conflict detection when a key is reused for a different request.
- Added optimistic concurrency using independent batch/candidate revisions.
- Added canonical candidate validation through `TemporalLawService`; fabricated and cross-document IDs fail closed.
- Added reviewer pair/date/change-type edits. Pair changes reset stale scores/references, recompute diffs and force mandatory review.
- Added legal-role-only Admin APIs for create, list, detail, candidate update, submit and approve/reject.
- Kept approval separate from graph commit; there is no call path to interval closure or `SUPERSEDED_BY` creation.
- Added independent `AMENDMENT_REVIEW_V2=false`; all amendment and legal-v2 flags remain disabled by default.

Verification:

- 49 focused amendment review/preview/contract tests passed.
- 259 full backend tests passed.
- Python compileall and Git whitespace checks passed.
- No PostgreSQL migration apply, live/staging mutation, Neo4j write or feature-flag activation was performed.

Next phase — L5.3:

1. Implement checksum-guarded, idempotent Neo4j commit in one managed transaction.
2. Re-read the approved PostgreSQL review and canonical old/new versions immediately before commit.
3. Close the old interval and create `SUPERSEDED_BY`/`AMENDED_BY` atomically, with rollback on any conflict.
4. Build the Admin amendment review UI and keep `AMENDMENT_COMMIT_V2=false` until integration and precision gates pass.

## Phase L5.3 completion - 2026-07-21

Completed in code:

- Added additive PostgreSQL migration `012_amendment_commits.sql` for commit idempotency, actor/time metadata and durable graph-commit reconciliation results.
- Added a strict commit domain contract that permits only deterministic accepted candidates: paired `REWORDED|TIGHTENED|LOOSENED`, new-only `ADDED`, and old-only `REMOVED`.
- Re-read every approved immutable version through `TemporalLawService` immediately before commit and rejected changed checksums, target-document mismatches, invalid dates, levels or lineages.
- Added one managed Neo4j write transaction for the entire approved batch. Any stale checksum, interval conflict, competing successor/predecessor, cycle or retry-key mismatch returns zero rows and rolls back the transaction.
- Closed old half-open intervals, approved new versions, and created retry-stamped `SUPERSEDED_BY`/`AMENDED_BY` edges.
- Reconciled the successful graph report into PostgreSQL idempotently. A retry after graph success but PostgreSQL failure completes reconciliation without creating duplicate graph edges.
- Added legal-role-only `POST /admin/legal/amendment-reviews/{batch_id}/commit` behind all legal-v2, preview, review and commit flags.
- Added the Admin amendment review page with batch navigation, candidate editing, diff/reason evidence, submit/approve/reject workflow and a separately confirmed commit action.
- Kept `AMENDMENT_COMMIT_V2=false`, `commit_allowed=false` and `auto_approve_eligible=false` by default. The new endpoint is an explicit human-reviewed commit path, not auto-approval.
- Added T16/T17 read-only acceptance contracts for a valid committed amendment and the absence of graph writes for ambiguous reviews.

Verification:

- 64 focused amendment commit/review/preview/temporal tests passed.
- 274 full backend tests passed; Python compileall passed.
- 6 frontend contract tests passed; production frontend build and lint passed.
- Lint retains one pre-existing Fast Refresh warning in `CitizenChrome.tsx`.
- No PostgreSQL migration apply, live/staging graph mutation or feature-flag activation was performed.

Next phase — L6:

1. Add source-neutral evidence adapters with news-first ingestion and a stable path to social-network connectors.
2. Add `Misconception` clusters and link repeated claims to current and historical legal provisions.
3. Implement `OUTDATED_BUT_PREVIOUSLY_TRUE` using publication-time and current-time legal checks.
4. Add explainable communications risk scoring and a human publish gate for public corrections.

## Phase L6.1 completion - 2026-07-21

Completed in code:

- Added `ClaimOccurrenceEvidence`, `Misconception`, cluster-candidate and assignment contracts.
- Required exact evidence offsets, canonical HTTP(S) URL, timezone-aware publication time and a content checksum matching normalized source text.
- Reused the existing `ContentItem` adapter, so news, social posts, video comments and forums enter one clustering contract.
- Added conservative deterministic clustering scoped by topic and legal anchor. Different numeric or negation signatures never auto-merge; lexical/sequence similarity must reach 0.84.
- Added managed Neo4j transaction writes for `YKien-[:INSTANCE_OF]->Misconception-[:CONTRADICTS]->LegalProvision|Khoan` with source provenance on the occurrence edge.
- Prevented one claim occurrence from being attached to competing misconception clusters.
- Added occurrence/source/provider counters and alert linkage through `AlertMeta-[:CANH_BAO_VE]->Misconception`.
- Integrated clustering into the shared news/social review worker without creating a second orchestration pipeline.
- Added Admin list/detail APIs behind `MISCONCEPTION_CLUSTER_V2=false` and existing Admin authentication.
- Added additive ontology, uniqueness/index contracts and read-only acceptance queries N01/N02.
- Kept `MISCONCEPTION_TEMPORAL_V2=false`; L6.1 does not assign historical/current temporal verdicts or publish anything to Citizen.

Verification:

- 33 focused misconception/news/social/temporal tests passed.
- 286 full backend tests passed; Python compileall passed.
- No Neo4j schema apply, feature-flag activation, crawl or live/staging mutation was performed.

Next phase — L6.2:

1. Evaluate every cluster against law at source publication time and at the requested current time.
2. Implement `OUTDATED_BUT_PREVIOUSLY_TRUE` only when the historical provision entails the claim and the current provision contradicts it.
3. Persist old/new provision IDs, intervals, NLI evidence and an explicit needs-review state.
4. Add explainable risk-score components and the Admin misconception/risk UI while preserving the Citizen publish gate.

## Phase L6.2 completion - 2026-07-21

Completed in code:

- Added strict temporal verdict contracts for `SUPPORTED`, `CONTRADICTED`, `PARTIALLY_INCORRECT`, `OUTDATED_BUT_PREVIOUSLY_TRUE`, `UNVERIFIABLE` and `NEEDS_REVIEW`.
- Resolved the same legal lineage at each occurrence publication date and at `current_as_of`, then ran NLI separately against both immutable canonical texts.
- Required historical `khop`, current `mau_thuan`, confidence gates and different physical provision IDs before emitting `OUTDATED_BUT_PREVIOUSLY_TRUE`.
- Classified missing legal versions as `UNVERIFIABLE`, low-confidence/inconsistent same-version NLI as `NEEDS_REVIEW`, and claims contradicted at both dates as `CONTRADICTED` rather than previously true.
- Persisted immutable `TemporalMisconceptionEvaluation` nodes with `HISTORICAL_BASIS` and `CURRENT_BASIS` in one managed Neo4j transaction.
- Added idempotent evaluation identity, checksum guards and durable old/new evidence history.
- Added eight explainable risk components: legal impact, source reach, contradiction confidence, velocity, source diversity, recent law change, engagement and provenance penalty.
- Propagated temporal verdict/risk into the shared news/social worker and alert severity when both misconception flags are enabled.
- Added legal-role-only `POST /admin/misconceptions/{id}/evaluate`, plus list filters for verdict and severity.
- Added an Admin page showing clusters, source occurrences, historical/current legal cards and factor-level risk contributions.
- Added T18/T19 acceptance contracts that reject outdated verdicts without two valid immutable bases.
- Kept both misconception flags disabled by default and retained the Citizen publish gate.

Verification:

- 38 focused temporal-misconception/clustering/social/contract tests passed.
- 298 full backend tests passed; Python compileall passed.
- 8 frontend contract tests passed; production build and lint passed.
- Lint retains one pre-existing Fast Refresh warning in `CitizenChrome.tsx`.
- No Neo4j schema apply, crawl, feature-flag activation or live/staging mutation was performed.

Next phase — L7:

1. Build independent gold sets for temporal misconception verdict and risk ranking.
2. Run T01-T20 and N01-N02 against real Neo4j/PostgreSQL/Qdrant integration fixtures.
3. Measure citation validity, outdated-verdict F1, refusal safety, P95 latency and cost.
4. Execute snapshot, dry-run, shadow-read and go/no-go gates before any feature activation.

## Phase L7.1A completion - 2026-07-21

Completed in code:

- Added one deterministic evaluation runner for parser, five-profile retrieval ablation, temporal exact match, citation validity/support, amendment pairing/change type, misconception verdict/clustering/risk, refusal safety and system latency/failure rate.
- Separated expected labels from predictions and classified every bundled dataset as `synthetic_contract_fixture`.
- Added release-evidence checks: only `independent_holdout` data with independent review and the configured minimum sample size can produce `GO`.
- Added blocking/advisory gates, per-label precision/recall/F1 and explicit limitations in the persisted JSON report.
- Completed the read-only acceptance catalog through T20 and added a validator for exactly T01-T20/N01-N02.
- Added an opt-in, read-only Neo4j acceptance executor whose parameters/assertions must be supplied by the approved integration fixture.
- Added a GitHub Actions workflow for backend tests, evaluation smoke gates, acceptance catalog validation, frontend contracts/build/lint and report artifacts.
- Added three locked demo contracts: time travel, outdated-but-previously-true news and fail-closed refusal.

Verification:

- 8 focused L7 evaluation/acceptance tests passed.
- 230 tests in the currently collected backend suite passed; Python compileall passed.
- Evaluation smoke blocking gates passed, while release decision correctly remained `NO_GO` because all bundled datasets are synthetic and below release sample sizes.
- Acceptance catalog validation found exactly 22 checks: T01-T20 and N01-N02.
- 8 frontend contract tests, production build and lint passed; existing Fast Refresh and bundle-size warnings remain non-blocking.
- No integration datastore was contacted and no schema, migration, crawl, feature flag or live/staging data was changed.

Next phase — L7.1B:

1. Produce independently labelled holdouts with two reviewers and adjudication for legal labels.
2. Load the approved integration fixture and execute all 22 read-only checks against real Neo4j, plus PostgreSQL/Qdrant parity tests.
3. Capture real shadow-read latency/cost/failure evidence and snapshot identifiers.
4. Re-run with `--release`; keep every rollout flag off unless the result is `GO`.

## Phase L6.2B hardening completion - 2026-07-21

The L6.2 dual-time and risk path was re-opened for a fail-closed audit and hardened:

- Historical and current legal bases must now share the same lineage. A mismatch returns `NEEDS_REVIEW` with `LEGAL_LINEAGE_MISMATCH`; it can never become `OUTDATED_BUT_PREVIOUSLY_TRUE`.
- Temporal evaluation identity now includes cluster, claim text, publication time, both lineage IDs/checksums, as-of date and verdict.
- The Neo4j transaction re-checks canonical checksum and lineage for both bases immediately before persistence, and validates immutable evaluation fields on retry.
- Cluster `source_count` now uses distinct content hashes rather than source IDs.
- Risk velocity and source diversity deduplicate syndicated/reposted bodies by `content_hash`; multiple providers carrying identical content count once.
- Alert volume deduplicates by content hash plus legal/claim identity, while distinct claims in one article remain separate.
- Persisted alert signals now carry `content_hash`, and the Admin UI distinguishes occurrences, independent content and providers.
- T18/T19 now require checksum and same-lineage consistency for outdated verdict evidence.

Verification:

- 54 focused L6.2/L6.1/worker/evaluation tests passed.
- Full current backend collection: 234 passed; compileall passed.
- Frontend: 9 contract tests, production build and lint passed.
- Acceptance catalog remained valid with all 22 T01-T20/N01-N02 contracts.
- Existing Fast Refresh, module-type and bundle-size warnings remain non-blocking.
- No datastore, crawl, migration or feature flag was changed.

## Phase L7.1B start - independent holdout provenance gate - 2026-07-21

Completed in code:

- Strengthened release-evidence eligibility so `independent_review=true` alone is no longer sufficient.
- Required at least two distinct reviewer audit IDs, completed adjudication, a guideline version and a valid SHA-256 checksum for the frozen source dataset.
- Added explicit `review_provenance_issues` to evaluation reports so incomplete evidence remains explainable and returns `NO_GO`.
- Added a reusable independent-holdout metadata template and documented the required review protocol.
- Added fail-closed tests for missing reviewer, adjudication, guideline and checksum evidence.

Verification:

- 12 focused L7 evaluation/acceptance tests passed.
- Evaluation smoke blocking gates passed and correctly remained `NO_GO` because bundled fixtures are synthetic.
- Python compileall and Git whitespace checks passed.
- No datastore, migration, crawl, feature flag or live/staging data was changed.

Next L7.1B slice:

1. Obtain independently labelled cases and reviewer/adjudication records for all eight suites.
2. Freeze the raw-source bundle and replace template checksums with audited SHA-256 values.
3. Run the 22 read-only Neo4j checks and Neo4j/Qdrant parity against the approved fixture datastore.
4. Capture real shadow-read latency/cost/failure evidence before invoking `--release`.

## Phase L7.1B multi-datastore acceptance harness - 2026-07-21

Completed in code:

- Added one fail-closed read-only runner across Neo4j, PostgreSQL and Qdrant.
- Neo4j executes all T01-T20/N01-N02 checks with explicit read access and fixture-specific assertions.
- PostgreSQL executes six schema, workflow, audit and commit-reconciliation invariant checks inside a read-only transaction.
- Qdrant must exactly match the deepest canonical Neo4j leaf IDs and text checksums.
- Required immutable snapshot IDs for all three stores and rejected every unresolved fixture placeholder.
- Added composite and non-empty field assertions so multi-field legal invariants can be proven by one acceptance case.
- Preserved per-store failure evidence even when another datastore is unavailable.
- Hardened the shared Neo4j leaf inventory boundary to always request read access.
- Added an approved-fixture configuration template and command documentation.

Verification:

- 30 focused evaluation, integration-acceptance and legal-provision-index tests passed.
- Template preflight failed closed before datastore access, as required.
- Docker Desktop is installed but its service cannot be started from the current session, so real local datastore evidence is still pending.
- No datastore, migration, crawl, feature flag or live/staging data was changed.

Next:

1. Start the local/dev data stack with sufficient host permission.
2. Load an approved fixed fixture, take three snapshot IDs and replace every template placeholder.
3. Run the multi-datastore acceptance command and retain the JSON report.
4. Produce independent holdouts and measured shadow-read evidence before `--release` can return `GO`.

## Phase L7.1B local runtime acceptance - 2026-07-21

Completed and verified on the localhost development stack:

- Started Neo4j, PostgreSQL, Qdrant, Redis and MinIO through the repository Docker stack.
- Applied the additive schema and migrations, including amendment review/commit persistence and the `legal_provision` Qdrant collection.
- Added a localhost-only, explicit-apply synthetic fixture loader with non-loopback refusal.
- Loaded 10 immutable legal versions covering partial amendment, V1-V2-V3 history, future effect, repeal, Clause leaves and Article leaves.
- Loaded an audited PostgreSQL amendment commit, one dual-time outdated misconception case and 8 Qdrant leaf payloads.
- Fixed T06 so it proves the complete maximal V1-V2-V3 path rather than accepting a shorter sub-path.
- Fixed Windows UTF-8 report output and the open-ended T05 assertion discovered during the first runtime round.

Fresh runtime evidence:

- Neo4j: 22/22 T01-T20/N01-N02 checks passed.
- PostgreSQL: 7/7 schema, safety, audit and reconciliation checks passed in a read-only transaction.
- Qdrant parity: 8/8 IDs and checksums matched canonical Neo4j leaves; coverage 1.0.
- Aggregate multi-datastore report: `passed=true`, `mutated=false` during acceptance execution.

This evidence is synthetic local integration evidence, not independent release evidence. Rollout remains `NO_GO` until independent holdouts and production-like shadow latency/cost/failure measurements pass.

## Phase L7.1B measured local shadow reads - 2026-07-21

Completed:

- Added a localhost-only temporal shadow benchmark across pre-amendment, current and future-effective dates.
- Compared `TemporalLawService` against an equivalent direct Neo4j reference using managed read transactions and full legal payloads.
- Alternated baseline/candidate order to reduce cache bias and emitted system-evaluation gold/prediction artifacts.
- Added fail-closed gates for at least 100 cases, zero failures, exact temporal leaf parity and P95 regression no greater than 20%.
- Added measured cost and LLM-call accounting; this datastore-only workload makes no paid calls.
- Fixed a real adapter defect found by runtime measurement: Neo4j temporal values are now converted to native Python dates/datetimes before Pydantic validation.

Fresh measured evidence after the architecture hardening review (120 reads, 12 warmups):

- Temporal leaf parity: 120/120, rate 1.0.
- Failure rate: 0.0.
- Candidate P50/P95: 18.4756 ms / 27.3458 ms.
- Equivalent baseline P50/P95: 16.7047 ms / 25.4420 ms.
- P95 regression ratio: 1.074829, below the 1.2 blocking limit.
- Estimated external cost: USD 0; LLM calls: 0.

The local shadow gate passed. Release remains `NO_GO` because legal-quality suites still require independently reviewed holdouts and production-like shadow evidence.

## Phase L7.1B architecture parity hardening - 2026-07-21

The full LAWGIC runtime path was re-reviewed against the eight mandatory invariants. Seven concrete safeguards were hardened:

- Citizen temporal/retrieval reads no longer treat missing visibility or review metadata as `public/approved`.
- Qdrant reindex refuses legal provisions without explicit publication metadata.
- Citation v2 refuses execution when `QA_STRICT_GROUNDING_V2` is disabled.
- Alert provenance requires a valid SHA-256 content hash before independent-volume aggregation.
- Canonical retrieval removes an active parent when an active deeper child candidate is available.
- Brief publish and audit writes now require one PostgreSQL transaction and fail closed without Postgres.
- Strict LAWGIC consumers treat heuristic NLI as `needs_review`; it cannot authorize Citation v2 or temporal misconception verdicts while legacy QA remains unchanged.

Fresh verification: 260 backend tests passed, 9 frontend contract tests passed, frontend production build passed, compileall passed, all 22/7/8 datastore checks passed, and the refreshed 120-read shadow report passed. See `docs/lawgic-core/ARCHITECTURE_REVIEW_2026-07-21.md` for the invariant matrix and remaining risks.

## Phase L7.1B amendment reconciliation observability - 2026-07-21

Completed:

- Added a read-only cross-store monitor for the Neo4j-to-PostgreSQL amendment commit saga.
- Detects graph key conflicts, missing PostgreSQL batches, graph-only commits, commit-key mismatches, incomplete actor/time/result metadata and missing reconciliation audit events.
- Added a legal-admin health endpoint that remains usable when graph commit is disabled, provided the review rollout is available.
- Added an opt-in periodic job to the legal worker only; it logs degraded evidence but never mutates or automatically repairs canonical legal data.
- Added explicit Neo4j read access and normalized Neo4j-native datetimes at the adapter boundary.
- Hardened the local fixture with immutable graph commit actor/time provenance.

Fresh verification:

- Full backend suite: 269 passed.
- Frontend contract suite: 9 passed; production build passed.
- Live local reconciliation scan: `healthy`, one graph commit scanned, zero issues.
- Multi-datastore acceptance: Neo4j 22/22, PostgreSQL 7/7 and Qdrant 8/8, with `passed=true` and `mutated=false`.
- Isolated 120-read shadow rerun: exact parity 120/120, zero failures and P95 ratio 1.06108 (gate maximum 1.2).

The monitor closes the observability gap but does not turn the saga into a distributed transaction. Operators must retry an affected approved batch with the same idempotency key. Release remains `NO_GO` pending independent legal holdouts, an approved production NLI model and production-like shadow evidence.
