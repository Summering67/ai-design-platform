ALTER TABLE generation_attempts
  DROP CONSTRAINT generation_attempts_status_check,
  ADD CONSTRAINT generation_attempts_status_check
    CHECK (status IN ('running', 'awaiting_input', 'completed', 'failed', 'interrupted'));

DROP INDEX generation_attempts_one_running_project_idx;
CREATE UNIQUE INDEX generation_attempts_one_active_project_idx
  ON generation_attempts (project_id)
  WHERE status IN ('running', 'awaiting_input');

CREATE TABLE generation_input_requests (
  id UUID PRIMARY KEY,
  generation_id UUID NOT NULL REFERENCES generation_attempts(id) ON DELETE CASCADE,
  source_stage TEXT NOT NULL,
  source_task_id TEXT NOT NULL,
  round INTEGER NOT NULL CHECK (round BETWEEN 1 AND 3),
  questions JSONB NOT NULL,
  answers JSONB,
  response_id UUID UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('pending', 'answered')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  answered_at TIMESTAMPTZ,
  UNIQUE (generation_id, source_stage, round)
);

CREATE UNIQUE INDEX generation_input_requests_one_pending_idx
  ON generation_input_requests (generation_id)
  WHERE status = 'pending';

CREATE INDEX generation_input_requests_generation_idx
  ON generation_input_requests (generation_id, source_stage, round);
