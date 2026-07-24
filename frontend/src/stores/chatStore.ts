import { create } from 'zustand'

interface ChatState {
  messages: Record<string, ChatMessageData[]>  // keyed by agent_id
  isStreaming: Record<string, boolean>
  toolActivity: Record<string, ToolActivity[]>

  addMessage: (agentId: string, message: ChatMessageData) => void
  setStreaming: (agentId: string, streaming: boolean) => void
  addToolActivity: (agentId: string, activity: ToolActivity) => void
  clearChat: (agentId: string) => void
}

export interface ChatMessageData {
  role: 'user' | 'assistant' | 'tool'
  content: string
  tool_calls?: any
}

export interface ToolActivity {
  tool: string
  arguments: any
  result?: any
  timestamp: string
}

export const useChatStore = create<ChatState>((set) => ({
  messages: {},
  isStreaming: {},
  toolActivity: {},

  addMessage: (agentId, message) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [agentId]: [...(state.messages[agentId] || []), message],
      },
    })),

  setStreaming: (agentId, streaming) =>
    set((state) => ({
      isStreaming: { ...state.isStreaming, [agentId]: streaming },
    })),

  addToolActivity: (agentId, activity) =>
    set((state) => ({
      toolActivity: {
        ...state.toolActivity,
        [agentId]: [...(state.toolActivity[agentId] || []), activity],
      },
    })),

  clearChat: (agentId) =>
    set((state) => ({
      messages: { ...state.messages, [agentId]: [] },
      toolActivity: { ...state.toolActivity, [agentId]: [] },
    })),
}))
