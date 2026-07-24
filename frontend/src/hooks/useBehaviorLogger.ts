import { useCallback } from 'react'
import { logApi } from '../services'
import type { BehaviorLogEntry } from '../types'

const FLUSH_INTERVAL = 5000 // 5 seconds
const MAX_QUEUE_SIZE = 50

// --- Module-level singleton: one queue + one flush timer per tab (single-user SPA) ---
const queue: BehaviorLogEntry[] = []
let timer: ReturnType<typeof setInterval> | null = null
let isFlushing = false

// Session-level metadata captured once per page load (design "七" session metadata)
const SESSION_META = {
  user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : undefined,
  screen_resolution:
    typeof window !== 'undefined' ? `${window.screen.width}x${window.screen.height}` : undefined,
  session_start_time: new Date().toISOString(),
  experiment_version: '1.0.0',
}

async function flush() {
  if (isFlushing || queue.length === 0) return
  isFlushing = true
  const batch = queue.splice(0, MAX_QUEUE_SIZE)
  try {
    await logApi.batch(batch)
  } catch (e) {
    queue.unshift(...batch)
    const stored = JSON.parse(localStorage.getItem('pending_logs') || '[]')
    localStorage.setItem('pending_logs', JSON.stringify([...batch, ...stored].slice(0, 200)))
  } finally {
    isFlushing = false
  }
}

export function useBehaviorLogger() {
  // Generic log — every entry carries session metadata automatically
  const log = useCallback((entry: BehaviorLogEntry) => {
    queue.push({
      ...SESSION_META,
      ...entry,
      page_path: entry.page_path || window.location.pathname,
    })
    if (queue.length >= MAX_QUEUE_SIZE) flush()
  }, [])

  // --- Semantic helpers (design "七" completeness) ---

  // AI agent interaction (OpenClaw monitoring + AI interaction behavior)
  const logAgent = useCallback((p: {
    agentId: string
    latencyMs?: number
    success?: boolean
    errorDetail?: string
    userActionOnAi?: 'accept' | 'reject' | 'modify'
    suggestionId?: string
    suggestionType?: string
    inputContent?: string
    aiResponse?: string
  }) => {
    log({
      action_type: 'agent_message',
      agent_id: p.agentId,
      input_content: p.inputContent,
      ai_response: p.aiResponse,
      request_latency_ms: p.latencyMs,
      is_success: p.success,
      error_detail: p.errorDetail,
      user_action_on_ai: p.userActionOnAi,
      ai_suggestion_id: p.suggestionId,
      ai_suggestion_type: p.suggestionType,
      phase: 'task',
    })
  }, [log])

  // Information retrieval behavior
  const logSearch = useCallback((p: {
    query: string
    resultsViewed?: number
    latencyMs?: number
    success?: boolean
    clickedItemId?: string
  }) => {
    log({
      action_type: 'search_query',
      input_content: p.query,
      results_viewed: p.resultsViewed,
      request_latency_ms: p.latencyMs,
      is_success: p.success,
      clicked_item_id: p.clickedItemId,
      phase: 'task',
    })
  }, [log])

  // Plan editing (manual edit count)
  const logPlanEdit = useCallback((p: {
    manualEditCount: number
    contentSnippet?: string
  }) => {
    log({
      action_type: 'document_edit',
      input_content: p.contentSnippet,
      manual_edit_count: p.manualEditCount,
      phase: 'task',
    })
  }, [log])

  // Final plan submission
  const logPlanSubmit = useCallback((p: {
    finalPlanText: string
  }) => {
    log({
      action_type: 'task_submit',
      final_plan_submit_time: new Date().toISOString(),
      extra_data: { final_plan_text: p.finalPlanText },
      phase: 'task',
    })
  }, [log])

  const start = useCallback(() => {
    if (timer) return
    timer = setInterval(flush, FLUSH_INTERVAL)
  }, [])

  const stop = useCallback(() => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    flush() // Final flush
  }, [])

  return { log, logAgent, logSearch, logPlanEdit, logPlanSubmit, start, stop, flush }
}
