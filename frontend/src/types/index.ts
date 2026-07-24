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
}

export interface TaskConfig {
  task_days: number
  task_budget: number
  target_email: string
  destination: string
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
