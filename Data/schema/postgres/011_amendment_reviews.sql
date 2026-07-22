-- L5.2 amendment review persistence.
-- Preview/review is PostgreSQL-only. This migration does not mutate Neo4j.

DO $$ BEGIN
  CREATE TYPE amendment_batch_status AS ENUM
    ('draft', 'in_review', 'approved', 'rejected', 'committed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE amendment_candidate_decision AS ENUM
    ('pending', 'accepted', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS amendment_review_batches (
  id                    UUID PRIMARY KEY,
  target_logical_vb_id  TEXT NOT NULL,
  amendment_text        TEXT NOT NULL,
  status                amendment_batch_status NOT NULL DEFAULT 'draft',
  idempotency_key       TEXT NOT NULL UNIQUE,
  request_hash          TEXT NOT NULL CHECK (length(request_hash) = 64),
  preview_snapshot      JSONB NOT NULL,
  created_by            TEXT NOT NULL,
  submitted_by          TEXT,
  submitted_at          TIMESTAMPTZ,
  reviewed_by           TEXT,
  reviewed_at           TIMESTAMPTZ,
  review_note           TEXT,
  revision              INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
  commit_allowed        BOOLEAN NOT NULL DEFAULT FALSE CHECK (commit_allowed = FALSE),
  auto_approve_eligible BOOLEAN NOT NULL DEFAULT FALSE CHECK (auto_approve_eligible = FALSE),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (length(amendment_text) BETWEEN 5 AND 50000)
);

CREATE INDEX IF NOT EXISTS idx_amendment_batches_status_updated
  ON amendment_review_batches (status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_amendment_batches_target
  ON amendment_review_batches (target_logical_vb_id, created_at DESC);

CREATE TABLE IF NOT EXISTS amendment_review_candidates (
  id                      UUID PRIMARY KEY,
  batch_id                UUID NOT NULL REFERENCES amendment_review_batches(id) ON DELETE RESTRICT,
  old_provision_id        TEXT,
  new_provision_id        TEXT,
  lineage_id              TEXT,
  reference_ids           JSONB NOT NULL DEFAULT '[]'::jsonb,
  confidence              DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  score_breakdown         JSONB,
  change_type             TEXT NOT NULL CHECK (change_type IN (
    'UNCHANGED', 'REWORDED', 'TIGHTENED', 'LOOSENED',
    'ADDED', 'REMOVED', 'SPLIT', 'MERGED', 'UNCERTAIN'
  )),
  review_route            TEXT NOT NULL CHECK (review_route IN ('human_review', 'mandatory_review')),
  proposed_effective_from DATE,
  decision                amendment_candidate_decision NOT NULL DEFAULT 'pending',
  reason_codes            JSONB NOT NULL DEFAULT '[]'::jsonb,
  diff_hunks              JSONB NOT NULL DEFAULT '[]'::jsonb,
  reviewer_note           TEXT,
  reviewed_by             TEXT,
  reviewed_at             TIMESTAMPTZ,
  revision                INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
  commit_allowed          BOOLEAN NOT NULL DEFAULT FALSE CHECK (commit_allowed = FALSE),
  auto_approve_eligible   BOOLEAN NOT NULL DEFAULT FALSE CHECK (auto_approve_eligible = FALSE),
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (old_provision_id IS NOT NULL OR new_provision_id IS NOT NULL),
  CHECK (old_provision_id IS DISTINCT FROM new_provision_id)
);

CREATE INDEX IF NOT EXISTS idx_amendment_candidates_batch
  ON amendment_review_candidates (batch_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_amendment_candidates_decision
  ON amendment_review_candidates (decision, review_route);

CREATE TABLE IF NOT EXISTS amendment_review_events (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id          UUID NOT NULL REFERENCES amendment_review_batches(id) ON DELETE RESTRICT,
  candidate_id      UUID REFERENCES amendment_review_candidates(id) ON DELETE RESTRICT,
  actor_id          TEXT NOT NULL,
  action            TEXT NOT NULL,
  from_status       TEXT,
  to_status         TEXT,
  expected_revision INTEGER,
  payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_amendment_events_batch_created
  ON amendment_review_events (batch_id, created_at, id);

DROP TRIGGER IF EXISTS trg_amendment_batches_updated ON amendment_review_batches;
CREATE TRIGGER trg_amendment_batches_updated BEFORE UPDATE ON amendment_review_batches
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_amendment_candidates_updated ON amendment_review_candidates;
CREATE TRIGGER trg_amendment_candidates_updated BEFORE UPDATE ON amendment_review_candidates
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE amendment_review_batches IS
  'Human-review workflow for amendment previews. Approval is not a Neo4j commit.';
COMMENT ON TABLE amendment_review_events IS
  'Append-only audit trail for every amendment review state or candidate change.';
