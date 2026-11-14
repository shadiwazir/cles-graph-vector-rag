-- Separate real traffic from test runs: drift checks and dashboards look at 'live' rows only.
ALTER TABLE request_audit ADD COLUMN environment TEXT NOT NULL DEFAULT 'live';
UPDATE request_audit SET environment = 'test';   -- every row so far came from tests and smoke runs
CREATE INDEX idx_audit_env_created ON request_audit (environment, created_at);
