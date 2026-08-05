import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

// 会话级聊天隔离：每个登录会话拥有独立存储键。
// - 刷新页面：sessionRef.id 不变 → 读取同一份聊天记录（保留）。
// - 换用户登录 / 同一用户重新登录：startNewSession 生成新 id → 全新空会话。
// 这样「刷新不丢记录」「重登即全新 AI 助手」两个需求同时满足。
const CHAT_SESSION_KEY = 'chat_session_id'
function genSessionId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `s_${Date.now()}_${Math.random().toString(36).slice(2)}`
}
function ensureSessionId(): string {
  let sid = localStorage.getItem(CHAT_SESSION_KEY)
  if (!sid) {
    sid = genSessionId()
    localStorage.setItem(CHAT_SESSION_KEY, sid)
  }
  return sid
}
const sessionRef = { id: ensureSessionId() }

const sessionStorage = createJSONStorage(() => ({
  getItem: (name) => localStorage.getItem(`agent-chat-${sessionRef.id}`),
  setItem: (name, value) => localStorage.setItem(`agent-chat-${sessionRef.id}`, value),
  removeItem: (name) => localStorage.removeItem(`agent-chat-${sessionRef.id}`),
}))

interface ChatState {
  messages: Record<string, ChatMessageData[]>  // keyed by agent_id
  isStreaming: Record<string, boolean>
  toolActivity: Record<string, ToolActivity[]>
  statusText: Record<string, string>           // 当前轮次的思考/状态文案（如"正在思考…"）
  cancelled: Record<string, boolean>           // 该助理当前轮次是否被参与者中断
  /** 用户是否已与任意 AI 助手发生过对话（用于"搜索景点"任务完成判定，发送消息时同步置位并持久化） */
  hasUsedAI: boolean

  addMessage: (agentId: string, message: ChatMessageData) => void
  setStreaming: (agentId: string, streaming: boolean) => void
  /** 工具开始调用：推入一条"调用中"状态日志 */
  addToolCall: (agentId: string, activity: ToolActivity) => void
  /** 工具调用完成：把同工具最后一条"调用中"日志翻转为"完成" */
  completeToolCall: (agentId: string, tool: string, status: string, result: any) => void
  /** 新一轮对话开始时清空状态日志 */
  resetToolActivity: (agentId: string) => void
  /** 写入当前轮次的思考状态文案 */
  setStatusText: (agentId: string, text: string) => void
  /** 标记该助理当前轮次已被中断 */
  setCancelled: (agentId: string, value: boolean) => void
  clearChat: (agentId: string) => void
  /** 退出登录等场景下清空所有助理的聊天记录（含本地持久化） */
  resetAll: () => void
  /** 兜底：若本地已有历史聊天记录（升级前数据无 hasUsedAI 标记），挂载时回填标志 */
  ensureAIUsedFlag: () => void
  /** 一次新的登录：切换至全新空会话（聊天记录按会话隔离） */
  startNewSession: () => void
  /** 流式输出时原地更新最后一条 assistant 消息，避免每条 token 都追加成新气泡 */
  updateAssistantContent: (agentId: string, content: string) => void
}

export interface ChatMessageData {
  role: 'user' | 'assistant' | 'tool'
  content: string
  tool_calls?: any
}

export interface ToolActivity {
  id: string
  tool: string
  /** 来自后端的中文状态文案（如"正在调用搜索引擎…"） */
  status: string
  arguments?: any
  result?: any
  /** calling = 调用中（前端显示转圈）；done = 已完成（显示绿勾） */
  state: 'calling' | 'done'
  timestamp: string
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: {},
      isStreaming: {},
      toolActivity: {},
      statusText: {},
      cancelled: {},
      hasUsedAI: false,

      addMessage: (agentId, message) =>
        set((state) => ({
          // 用户发出任意消息即视为已使用 AI 助手（用于"搜索景点"任务完成判定）
          hasUsedAI: state.hasUsedAI || message.role === 'user',
          messages: {
            ...state.messages,
            [agentId]: [...(state.messages[agentId] || []), message],
          },
        })),

      setStreaming: (agentId, streaming) =>
        set((state) => ({
          isStreaming: { ...state.isStreaming, [agentId]: streaming },
        })),

      addToolCall: (agentId, activity) =>
        set((state) => ({
          toolActivity: {
            ...state.toolActivity,
            [agentId]: [...(state.toolActivity[agentId] || []), activity],
          },
        })),

      completeToolCall: (agentId, tool, status, result) =>
        set((state) => {
          const list = state.toolActivity[agentId] || []
          // 找到该工具最后一条仍处于 calling 的日志并翻转为 done
          let targetIdx = -1
          for (let i = list.length - 1; i >= 0; i--) {
            if (list[i].tool === tool && list[i].state === 'calling') {
              targetIdx = i
              break
            }
          }
          if (targetIdx === -1) return {}
          const updated = list.slice()
          updated[targetIdx] = { ...updated[targetIdx], state: 'done', status, result }
          return { toolActivity: { ...state.toolActivity, [agentId]: updated } }
        }),

      resetToolActivity: (agentId) =>
        set((state) => ({
          toolActivity: { ...state.toolActivity, [agentId]: [] },
          statusText: { ...state.statusText, [agentId]: '' },
          cancelled: { ...state.cancelled, [agentId]: false },
        })),

      setStatusText: (agentId, text) =>
        set((state) => ({
          statusText: { ...state.statusText, [agentId]: text },
        })),

      setCancelled: (agentId, value) =>
        set((state) => ({
          cancelled: { ...state.cancelled, [agentId]: value },
        })),

      clearChat: (agentId) =>
        set((state) => ({
          messages: { ...state.messages, [agentId]: [] },
          toolActivity: { ...state.toolActivity, [agentId]: [] },
          statusText: { ...state.statusText, [agentId]: '' },
          cancelled: { ...state.cancelled, [agentId]: false },
        })),

      resetAll: () => {
        try {
          localStorage.removeItem(`agent-chat-${sessionRef.id}`)
        } catch {
          // 忽略存储异常
        }
        set({
          messages: {},
          isStreaming: {},
          toolActivity: {},
          statusText: {},
          cancelled: {},
          hasUsedAI: false,
        })
      },

      startNewSession: () => {
        // 生成新会话 ID，旧会话数据留在旧键下不再读取 → 全新空聊天
        const newId = genSessionId()
        sessionRef.id = newId
        localStorage.setItem(CHAT_SESSION_KEY, newId)
        set({
          messages: {},
          isStreaming: {},
          toolActivity: {},
          statusText: {},
          cancelled: {},
          hasUsedAI: false,
        })
      },

      ensureAIUsedFlag: () =>
        set((state) => {
          const has = Object.values(state.messages).some((arr) => arr && arr.length > 0)
          return has ? { hasUsedAI: true } : {}
        }),

      updateAssistantContent: (agentId, content) =>
        set((state) => {
          const list = state.messages[agentId] || []
          const last = list[list.length - 1]
          if (last && last.role === 'assistant') {
            // 流式过程中：原地更新最后一条 assistant 消息
            const updated = list.slice()
            updated[updated.length - 1] = { ...last, content }
            return { messages: { ...state.messages, [agentId]: updated } }
          }
          // 尚无 assistant 消息：创建一条
          return {
            messages: { ...state.messages, [agentId]: [...list, { role: 'assistant', content }] },
          }
        }),
    }),
    {
      // 注意：实际存储键由 sessionStorage 动态拼接 sessionRef.id（见上方）
      name: 'agent-chat',
      version: 1,
      storage: sessionStorage,
      // 仅持久化对话记录与 hasUsedAI 标记；流式/工具状态刷新后重置，避免中断的流留下卡死的转圈
      partialize: (state) => ({ messages: state.messages, hasUsedAI: state.hasUsedAI }),
      onRehydrateStorage: () => (_, error) => {
        // hydration 完成后：若本地已有聊天记录（升级前数据无 hasUsedAI），立即回填标记
        if (!error) {
          useChatStore.getState().ensureAIUsedFlag()
        }
      },
    },
  ),
)
