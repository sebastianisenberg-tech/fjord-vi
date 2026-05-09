-- Fjord VI Phase 16 bootstrap
-- Placeholder migration structure for future Alembic integration

CREATE INDEX IF NOT EXISTS idx_activity_log_created_at
ON activity_log (created_at);

CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
ON audit_log (created_at);
