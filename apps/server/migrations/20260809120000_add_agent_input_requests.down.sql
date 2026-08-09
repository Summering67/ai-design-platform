DROP INDEX IF EXISTS generation_input_requests_generation_idx;
DROP INDEX IF EXISTS generation_input_requests_one_pending_idx;
DROP TABLE IF EXISTS generation_input_requests;
DROP INDEX IF EXISTS generation_attempts_one_active_project_idx;
CREATE UNIQUE INDEX generation_attempts_one_running_project_idx
  ON generation_attempts (project_id)
  WHERE status = 'running';
ALTER TABLE generation_attempts
  DROP CONSTRAINT generation_attempts_status_check,
  ADD CONSTRAINT generation_attempts_status_check
    CHECK (status IN ('running', 'completed', 'failed', 'interrupted'));
