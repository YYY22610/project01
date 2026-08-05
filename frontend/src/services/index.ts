import { api } from './api'
import type { User, TaskConfig, TaskStatus, SearchResult, QuestionnaireItem, BehaviorLogEntry } from '../types'

// Auth
export const authApi = {
  register: (email: string) =>
    api.post('/auth/register', { email }),
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  loginByEmail: (email: string) =>
    api.post('/auth/login-by-email', { email }),
  consent: () => api.post('/auth/consent'),
  demographics: (data: any) => api.post('/auth/demographics', data),
  me: () => api.get<User>('/auth/me'),
  adminLogin: (username: string, password: string) =>
    api.post('/auth/admin/login', { username, password }),
}

// Task
export const taskApi = {
  config: () => api.get<TaskConfig>('/task/config'),
  demoComplete: (watchSeconds?: number) =>
    api.post('/task/demo-complete', watchSeconds != null ? { watch_seconds: watchSeconds } : {}),
  start: () => api.post('/task/start'),
  submit: (data: any) => api.post('/task/submit', data),
  status: () => api.get('/task/status'),
  reset: () => api.post('/task/reset'),
}

// Search
export const searchApi = {
  search: (query: string, page: number = 1) =>
    api.post('/search', { query, page }),
}

// Document
export const documentApi = {
  generate: (title: string, content: string, format: 'text' | 'html' = 'text') =>
    api.post('/document/generate', { title, content, format }),
  /** 返回下载 URL 字符串（仅用于拼接，不直接触发下载） */
  downloadUrl: (fileName: string) =>
    `/api/document/download/${fileName}`,
  /** 用 fetch + Blob 方式下载文件到本地（携带 JWT） */
  download: async (fileName: string): Promise<void> => {
    const token = localStorage.getItem('access_token')
    const res = await fetch(`/api/document/download/${fileName}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`下载失败 (${res.status}): ${text}`)
    }
    const blob = await res.blob()
    // 触发浏览器"另存为"下载
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    // 延迟释放，避免某些浏览器下载被取消
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  },
}

// Reminder
export const reminderApi = {
  set: (datetime: string, content: string) =>
    api.post('/reminder', { reminder_datetime: datetime, content }),
  list: () => api.get('/reminder'),
}

// Email
export const emailApi = {
  send: (
    toEmail: string,
    subject: string,
    content: string,
    files?: File[],
    attachmentPath?: string,
  ) => {
    const fd = new FormData()
    fd.append('to_email', toEmail)
    fd.append('subject', subject)
    fd.append('content', content)
    if (attachmentPath) fd.append('attachment_path', attachmentPath)
    if (files && files.length) {
      files.forEach((f) => fd.append('files', f))
    }
    // 不手动设置 Content-Type，让 axios 自动带上 multipart/form-data 边界
    return api.post('/email/send', fd)
  },
}

// Agent chat (SSE)
export const agentApi = {
  chat: async (
    agentId: string,
    message: string,
    onEvent: (event: string, data: any) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const token = localStorage.getItem('access_token')
    const response = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ agent_id: agentId, message }),
      signal,
    })

    if (!response.ok) {
      let detail = `Agent chat failed: ${response.status}`
      try {
        const body = await response.json()
        if (body?.detail) detail = `Agent chat failed: ${response.status} - ${body.detail}`
      } catch {
        // 非 JSON 响应时保持默认提示
      }
      throw new Error(detail)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let currentEvent = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6))
              onEvent(currentEvent, data)
            } catch {
              onEvent(currentEvent, line.slice(6))
            }
            currentEvent = ''
          }
        }
      }
    } catch (err: any) {
      // 用户主动中断（AbortController.abort）时静默结束，不视为错误
      if (err?.name === 'AbortError') return
      throw err
    }
  },

  /** 干预接口：参与者随时中断指定助理的当前操作 */
  cancel: async (agentId: string): Promise<void> => {
    await api.post('/agent/cancel', { agent_id: agentId })
  },
}

// Questionnaire
export const questionnaireApi = {
  items: () => api.get<QuestionnaireItem[]>('/questionnaire/items'),
  submit: (responses: { item_id: string; response_value: string }[]) =>
    api.post('/questionnaire/submit', { responses }),
}

// Behavior log
export const logApi = {
  batch: (logs: BehaviorLogEntry[]) =>
    api.post('/log/batch', { logs }),
}
