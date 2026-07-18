-- Full-stack alert provenance read model.
-- `signals` contains source-grounded BE2 results only; no generated/fallback claims.
ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS signals JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS provenance_status TEXT NOT NULL DEFAULT 'missing';

CREATE INDEX IF NOT EXISTS idx_alerts_provenance_status
  ON alerts (provenance_status);

COMMENT ON COLUMN alerts.signals IS
  'Persisted BE2 signals: exact claim/evidence span, source post, NLI result and canonical legal reference.';
COMMENT ON COLUMN alerts.provenance_status IS
  'complete when every displayed signal is linked to persisted source and legal evidence; otherwise missing.';
