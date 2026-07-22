# Project feature audit — 2026-07-21

## Decision

**ACCEPTED for local/development feature operation.** The non-LAWGIC feature audit found and fixed reproducible correctness, security-boundary, and observability defects. The full test and local read-only smoke suites pass.

This decision does not change the overall LAWGIC production release decision. Production remains **NO_GO** until the independent holdout, approved production NLI, and production-like shadow evidence described in the LAWGIC progress report are available.

Audit issue: `local-audit-2026-07-21`

Environment: local/development
Fix rounds: 2 of 2

## Scope and acceptance criteria

Reviewed authentication/RBAC, admin legal APIs, ingest/job lifecycle, review queue, social/news monitoring, alerts, graph views, briefs/suggestions, citizen APIs, workers, frontend contracts/build, dependency integrity, and local datastore-backed read paths.

Acceptance required:

- reproducible defects fixed with regression coverage;
- backend and frontend contract suites passing;
- production frontend build and lint passing;
- Python import/compile and dependency checks passing;
- representative read-only calls succeeding against the configured local stores;
- no feature flags enabled as a side effect.

## Fixed findings

| Severity | Finding | Resolution and evidence |
| --- | --- | --- |
| High | Manual social ingest returned a queued job without actually submitting it to ARQ; payloads without `external_id` could never complete. | Default path now persists synchronously, generates a deterministic ID, and records running/success/error. Optional async mode creates a real ARQ envelope and enqueues it. Worker lifecycle is persisted. Regression tests cover both paths. |
| High | Link preview could resolve or redirect to loopback/private/metadata addresses (SSRF). | Added scheme, credentials, port, hostname, DNS/IP, and redirect-hop validation. Tests cover direct private targets and public-to-private redirects. |
| High | Admin jobs and review queue could return an empty/404 result when PostgreSQL or Neo4j failed, creating a false-healthy state. | Both surfaces now fail closed with a generic `503`, log internal details server-side, and do not leak connection strings. Review updates no longer fall through from a missing namespaced job to Neo4j. |
| Medium | Login database failures exposed raw backend exception details. | API now returns a generic `503`; regression test verifies connection details are absent. |
| Medium | Production auth fallback was logged but `/health` always reported `security_ok=true`. | Security settings retain a non-secret readiness error; health now reports `security_ok=false` for invalid production auth configuration while liveness remains available. |
| Medium | Neo4j review/diff queries used deprecated internal numeric IDs and generated notification noise. | Replaced with `elementId` and safe dynamic property access. |
| Low | Windows console logging could raise encoding errors on Vietnamese Neo4j notifications. | Standard streams are configured for UTF-8 with a safe fallback. |
| Low | Frontend emitted a module-mode warning and an export-related lint warning. | Declared ESM at the package root and moved shared citizen suggestions to a dedicated module. |

## Verification evidence

- Backend: **285 passed**.
- Focused regression set after the final fixes: **29 passed**.
- Frontend Node contract tests: **9 passed**.
- Frontend lint: passed with no findings.
- Frontend production build: passed; 5,633 modules transformed.
- Local datastore-backed ASGI smoke: **15/15 HTTP 200** across health, auth, dashboard, jobs, review, legal, social, alerts, graph, briefs, suggestions, and citizen news/read APIs.
- Python `compileall`: passed.
- Python dependency integrity: no broken requirements.
- npm audit: 0 vulnerabilities.
- Git whitespace validation: passed (line-ending notices only).

## Remaining operational decisions

These are not silently changed by this audit because they require deployment policy, credentials, or independent evidence:

1. Set a persistent random `AUTH_TOKEN_SECRET` of at least 32 characters in each deployed environment. The current local smoke process generated an ephemeral secret, so sessions do not survive a restart.
2. For production, set `APP_ENV=production`, keep `ENABLE_DEV_TOKENS=false`, and normally set `CORS_ALLOW_ALL=false` with an explicit `CORS_EXTRA_ORIGINS` allowlist.
3. The frontend production bundle is about 914 kB before gzip and still triggers Vite's 500 kB performance warning. It is a performance optimization item, not a correctness failure.
4. `legal_parse` and `legal_diff` contain placeholder worker functions, but they are not registered or reachable. Active legal ingest, extraction, and synchronous diff paths are implemented and tested. Do not register those placeholders without implementing their storage contracts.
5. LAWGIC release evidence still requires independent two-reviewer holdouts, an approved production NLI model, and production-like shadow traffic. All related feature flags remain off.
