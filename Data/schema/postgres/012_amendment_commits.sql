-- L5.3 reconciliation metadata for an approved review after Neo4j commit.

ALTER TABLE amendment_review_batches
  ADD COLUMN IF NOT EXISTS commit_idempotency_key TEXT,
  ADD COLUMN IF NOT EXISTS committed_by TEXT,
  ADD COLUMN IF NOT EXISTS committed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS commit_result JSONB;

CREATE UNIQUE INDEX IF NOT EXISTS uq_amendment_batches_commit_key
  ON amendment_review_batches (commit_idempotency_key)
  WHERE commit_idempotency_key IS NOT NULL;

COMMENT ON COLUMN amendment_review_batches.commit_idempotency_key IS
  'Retry-safe key shared with Neo4j temporal relationships.';
COMMENT ON COLUMN amendment_review_batches.commit_result IS
  'Graph commit report used to reconcile a successful Neo4j transaction with PostgreSQL.';
