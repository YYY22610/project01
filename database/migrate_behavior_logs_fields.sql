-- Migration: enrich behavior_logs + add agent_service_paused config
-- Safe ADD COLUMN (ignored if already present); non-destructive.

ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS request_latency_ms INTEGER;
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS is_success BOOLEAN;
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS error_detail TEXT;
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS user_agent VARCHAR(255);
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS screen_resolution VARCHAR(20);
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS experiment_version VARCHAR(20);
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS session_start_time TIMESTAMPTZ;
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS phase VARCHAR(30);
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS manual_edit_count INTEGER;
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS final_plan_submit_time TIMESTAMPTZ;
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS results_viewed INTEGER;
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS result_view_duration_ms INTEGER;
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS clicked_item_id VARCHAR(100);
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS user_action_on_ai VARCHAR(20);
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS ai_suggestion_id VARCHAR(50);
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS ai_suggestion_type VARCHAR(30);
ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS ai_interaction_rounds INTEGER;

-- OpenClaw pause switch config (idempotent insert)
INSERT INTO system_config (key, value, description)
SELECT 'agent_service_paused', 'false', 'AI助理服务是否暂停'
WHERE NOT EXISTS (SELECT 1 FROM system_config WHERE key = 'agent_service_paused');
