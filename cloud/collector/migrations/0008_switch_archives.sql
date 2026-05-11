-- Migration 0008: per-user switch archive registry.
--
-- Lands the data shape behind the new manual-archive UX on
-- /dashboard/switches and /dashboard/switches/<name>. Spec at:
--   docs/working/launch-proposal-2026-05-07.md (post-Phase-1 polish)
--
-- Context: a switch shows up in the dashboard roster the moment it
-- records its first verdict. If the customer later removes the
-- `@ml_switch` from their code, the row sits there with frozen metrics
-- and no signal that it's dormant. The fix is two-part:
--
--   1. presentation-only stale chip when last_activity > 30 days ago
--      (no schema needed — derived at read time from verdicts.created_at)
--   2. manual archive: customer-driven action that hides the switch
--      from the default roster view without altering verdict history.
--      This table is the persistence layer for part 2.
--
-- Semantics:
--   * archive is presentation-only on top of preserved data. Verdict
--     history is never touched.
--   * one row per (user_id, switch_name); duplicates are prevented by
--     UNIQUE. Archive endpoints are idempotent — re-archiving a switch
--     returns the existing row, not a 409.
--   * auto-unarchive: when a verdict arrives for a (user, switch) that
--     has an archive row, the row is deleted in the verdict hot path
--     (cloud/api/src/verdicts.ts). The natural recovery — the customer
--     un-commented their @ml_switch and the function is alive again.
--   * available on all tiers. Archive is account management, not a Pro
--     feature.

CREATE TABLE IF NOT EXISTS switch_archives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Switch name as it appears in verdicts.switch_name. We don't FK
    -- to verdicts because there's no FK target — verdicts are per-key
    -- and a switch is a logical name on the user's data, not a row in
    -- a switches table. The application layer enforces "user owns at
    -- least one verdict with this switch_name" before allowing archive.
    switch_name TEXT NOT NULL,
    archived_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- Optional free-text reason the customer typed in the inline form.
    -- Capped at 200 chars on the API side; nullable so the dashboard can
    -- offer "archive" as a one-click action without forcing a reason.
    archived_reason TEXT,
    UNIQUE(user_id, switch_name)
);

-- Hot path: the /admin/switches list LEFT JOINs this table per row to
-- decide whether to include each switch. Indexing on user_id keeps the
-- join cheap; UNIQUE(user_id, switch_name) already implies a composite
-- index for the auto-unarchive DELETE lookup.
CREATE INDEX IF NOT EXISTS idx_switch_archives_user
    ON switch_archives (user_id);
