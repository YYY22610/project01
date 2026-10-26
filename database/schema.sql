-- Travel Experiment Platform — Database Schema
-- PostgreSQL 16

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    "group" VARCHAR(10),
    status VARCHAR(50) DEFAULT 'registered',
    age INTEGER,
    gender VARCHAR(20),
    education VARCHAR(50),
    tech_frequency VARCHAR(50),
    ai_experience VARCHAR(50),
    demo_watch_seconds INTEGER,
    session_id VARCHAR(100),
    task_start_time TIMESTAMPTZ,
    task_end_time TIMESTAMPTZ,
    -- 签知情同意时提交的前置问卷原始 10 题答案（JSONB）
    pre_survey JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Behavior logs table
CREATE TABLE IF NOT EXISTS behavior_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    "group" VARCHAR(10),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    action_type VARCHAR(50) NOT NULL,
    action_target VARCHAR(500),
    input_content TEXT,
    ai_response TEXT,
    agent_id VARCHAR(50),
    page_path VARCHAR(200),
    session_id VARCHAR(100),
    extra_data JSONB,
    -- Enriched fields (design "七")
    request_latency_ms INTEGER,
    is_success BOOLEAN,
    error_detail TEXT,
    user_agent VARCHAR(255),
    screen_resolution VARCHAR(20),
    experiment_version VARCHAR(20),
    session_start_time TIMESTAMPTZ,
    phase VARCHAR(30),
    manual_edit_count INTEGER,
    final_plan_submit_time TIMESTAMPTZ,
    results_viewed INTEGER,
    result_view_duration_ms INTEGER,
    clicked_item_id VARCHAR(100),
    user_action_on_ai VARCHAR(20),
    ai_suggestion_id VARCHAR(50),
    ai_suggestion_type VARCHAR(30),
    ai_interaction_rounds INTEGER
);

-- Task submissions table
CREATE TABLE IF NOT EXISTS task_submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task1_search BOOLEAN DEFAULT FALSE,
    task2_document BOOLEAN DEFAULT FALSE,
    task3_reminder BOOLEAN DEFAULT FALSE,
    task4_email BOOLEAN DEFAULT FALSE,
    docx_file_path VARCHAR(500),
    reminder_datetime TIMESTAMPTZ,
    email_status VARCHAR(20),
    email_recipient VARCHAR(255),
    duration_ms INTEGER,
    submitted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT,
    tool_calls JSONB,
    tool_call_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Questionnaire items table
-- 2026-10-14 版：前置问卷与后置问卷统一存于此表，用 phase 区分。
-- 建库新环境时直接按此 DDL 建即可；已有环境请执行 migrate_questionnaire_v2.sql。
CREATE TABLE IF NOT EXISTS questionnaire_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    construct VARCHAR(64) NOT NULL,
    question_text TEXT NOT NULL,
    question_type VARCHAR(20) DEFAULT 'likert',   -- likert | multiple | choice | text
    options JSONB,                                -- 单选/多选为字符串数组；双极量表为 {left,right}
    scale_level INTEGER DEFAULT 5,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    applicable_groups VARCHAR(20),                -- 一律 'ALL'（新问卷统一措辞，靠指导语做单盲）
    phase VARCHAR(10) NOT NULL DEFAULT 'post',    -- pre = 前置问卷 | post = 后置问卷
    is_reverse BOOLEAN NOT NULL DEFAULT FALSE,    -- 反向计分，导出聚合时按 scale+1-x 翻转
    section_note TEXT,                            -- 题组指导语，渲染为题干上方提示
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Questionnaire responses table
CREATE TABLE IF NOT EXISTS questionnaire_responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES questionnaire_items(id) ON DELETE CASCADE,
    response_value TEXT NOT NULL,                 -- 多选题以 ' | ' 连接多个选项
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_questionnaire_items_phase ON questionnaire_items (phase, sort_order);

-- Admin scores table (8-factor, 100-point scheme, GB/T 18972-2017 derived)
CREATE TABLE IF NOT EXISTS admin_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenic_score INTEGER,
    historic_score INTEGER,
    rarity_score INTEGER,
    scale_score INTEGER,
    integrity_score INTEGER,
    fame_score INTEGER,
    season_score INTEGER,
    eco_score INTEGER,
    total_score INTEGER,
    rationality_score INTEGER,
    quality_score INTEGER,
    notes TEXT,
    scored_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Reminders table
CREATE TABLE IF NOT EXISTS reminders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reminder_datetime TIMESTAMPTZ NOT NULL,
    content TEXT,
    is_set BOOLEAN DEFAULT TRUE,
    -- 标记提醒邮件是否已发送；NULL 表示尚未发送，发送后置为发送时间
    sent_at TIMESTAMPTZ,
    -- 发送失败计数与最近一次错误，用于重试上限与永久失败判定
    failed_attempts INTEGER DEFAULT 0 NOT NULL,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- System config table
CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description VARCHAR(255),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Admin users table
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_group ON users("group");
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_behavior_logs_user_id ON behavior_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_behavior_logs_timestamp ON behavior_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_behavior_logs_action_type ON behavior_logs(action_type);
CREATE INDEX IF NOT EXISTS idx_behavior_logs_session_id ON behavior_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_task_submissions_user_id ON task_submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_questionnaire_responses_user_id ON questionnaire_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_scores_user_id ON admin_scores(user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
