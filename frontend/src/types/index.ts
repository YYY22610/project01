// TypeScript type definitions

export type ExperimentGroup = 'H' | 'SOA' | 'MOA'

export type UserStatus =
  | 'registered'
  | 'consented'
  | 'demo_completed'
  | 'task_in_progress'
  | 'task_completed'
  | 'questionnaire_completed'

export interface User {
  id: string
  email: string
  status: UserStatus
  age?: number
  gender?: string
  education?: string
  tech_frequency?: string
  ai_experience?: string
  pre_survey?: PreSurvey | null
}

// 实验前置问卷 10 题（与后端 schemas.auth.PreSurveySubmission 对应）
export interface PreSurvey {
  q1_used_gen_ai: string          // yes / no
  q2_travel_experience: string    // domestic / abroad / both / never
  q3_llm_frequency_6m: string     // never / rarely / sometimes / often / daily
  q4_agent_awareness: string[]    // 多选：agent_principle / agent_openclaw / agent_built / agent_deployed / agent_helpful / none
  q5_llm_duration: string         // lt_1m / m_1_3 / m_3_6 / gte_6m
  q6_gender: string               // male / female
  q7_age_range: string            // 18-24 / 25-34 / 35-44 / 45-54 / 55-64 / 65+
  q8_education: string            // high_school / bachelor / master / phd
  q9_marital: string              // married / unmarried
  q10_occupation: string          // student / full_time / part_time / freelance / unemployed / retired / other
  submitted_at?: string
}

export interface TaskConfig {
  task_days: number
  task_budget: number
  target_email: string
  destination: string
  travelers: string
  sub_tasks: string[]
}

export interface TaskStatus {
  status: UserStatus
  task_start_time: string | null
  task_end_time: string | null
  submission: {
    task1_search: boolean
    task2_document: boolean
    task3_reminder: boolean
    task4_email: boolean
    docx_file_path: string | null
    email_status: string | null
  } | null
}

export interface SearchResult {
  title: string
  url: string
  snippet: string
  source?: 'search_engine' | 'mock' | 'ai'
}

export interface ChatMessage {
  id?: string
  agent_id: string
  role: 'user' | 'assistant' | 'tool'
  content: string | null
  tool_calls?: any
  created_at?: string
}

export interface QuestionnaireItem {
  id: string
  construct: string
  question_text: string
  question_type: 'likert' | 'choice' | 'text'
  options?: any
  scale_level: number
  sort_order: number
}

export interface BehaviorLogEntry {
  action_type: string
  action_target?: string
  input_content?: string
  ai_response?: string
  agent_id?: string
  page_path?: string
  extra_data?: any
  // Enriched fields (design "七")
  request_latency_ms?: number
  is_success?: boolean
  error_detail?: string
  user_agent?: string
  screen_resolution?: string
  experiment_version?: string
  session_start_time?: string
  phase?: string
  manual_edit_count?: number
  final_plan_submit_time?: string
  results_viewed?: number
  result_view_duration_ms?: number
  clicked_item_id?: string
  user_action_on_ai?: string
  ai_suggestion_id?: string
  ai_suggestion_type?: string
  ai_interaction_rounds?: number
}
