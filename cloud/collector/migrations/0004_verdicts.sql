-- Migration 0004: hosted-API verdicts table.
--
-- Stores paired-correctness outcomes posted by SDK clients to
-- POST /v1/verdicts on the api Worker. One row per verdict.
--
-- Privacy posture: switch_name is operator-chosen (e.g.
-- "intent_classifier") and is opaque to us. ground_truth and
-- metadata are optional and capped server-side at insert time.
--
-- Why on this DB: shared with users + api_keys + collector events
-- so a single D1 query can join api_key → user → tier → recent
-- verdicts. Avoids a second database round-trip on the report path.

CREATE TABLE IF NOT EXISTS verdicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key_id INTEGER NOT NULL REFERENCES api_keys(id),
    -- Operator-chosen identifier for the @ml_switch site (matches the
    -- name argument they pass at decoration). Opaque to us.
    switch_name TEXT NOT NULL,
    -- Phase letter at the time the verdict was recorded:
    --   'P0' RULE | 'P1' MODEL_SHADOW | 'P2' MODEL_PRIMARY |
    --   'P3' ML_SHADOW | 'P4' ML_WITH_FALLBACK | 'P5' ML_PRIMARY
    -- Nullable for backwards compat with clients that don't report it.
    phase TEXT,
    -- Paired-correctness outcomes per decision-maker. NULL = the layer
    -- wasn't active at this verdict (e.g. no ML head until P3).
    rule_correct INTEGER,
    model_correct INTEGER,
    ml_correct INTEGER,
    -- Ground-truth label as a free string (or NULL when unknown). Capped
    -- to 512 chars at insert; longer strings are rejected with 400.
    ground_truth TEXT,
    -- Client-supplied idempotency key. Combined with api_key_id, lets
    -- us de-duplicate retries via the partial index below.
    request_id TEXT,
    -- Operator metadata blob — JSON, capped at 4KB at insert time.
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Hot path index for the report-card render: pull recent verdicts for
-- a given key + switch, ordered newest first.
CREATE INDEX IF NOT EXISTS idx_verdicts_key_switch_time
    ON verdicts (api_key_id, switch_name, created_at DESC);

-- Idempotency lookup. Partial index keeps it small (most rows have no
-- request_id) and uniqueness-by-(api_key_id, request_id) prevents
-- duplicate inserts on client retries.
CREATE UNIQUE INDEX IF NOT EXISTS idx_verdicts_request_id_unique
    ON verdicts (api_key_id, request_id) WHERE request_id IS NOT NULL;
