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
  pre_survey?: Record<string, string> | null
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
  /** 服务端记录的「已与 AI 助手对话」（仅对配置了 AI 助手的组返回 true） */
  ai_chat_started?: boolean
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
  // likert = 量表（含双极，锚点见 options）；multiple = 多选；choice = 单选；text = 开放填空
  question_type: 'likert' | 'choice' | 'multiple' | 'text'
  options?: any
  scale_level: number
  sort_order: number
  applicable_groups?: string | null
  phase: 'pre' | 'post'
  is_reverse: boolean
  /** 题组指导语，渲染为题干上方的提示段落（仅题组首题有值） */
  section_note?: string | null
}

/** 双极量表的左右锚点（情绪体验构念用） */
export interface BipolarAnchors {
  left: string
  right: string
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
