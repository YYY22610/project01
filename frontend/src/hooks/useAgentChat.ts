import { useState, useCallback } from 'react'
import { agentApi } from '../services'
import { useChatStore } from '../stores/chatStore'
import { useBehaviorLogger } from './useBehaviorLogger'

export function useAgentChat(agentId: string) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { messages, isStreaming, toolActivity, addMessage, setStreaming, addToolActivity } = useChatStore()
  const { logAgent } = useBehaviorLogger()

  const sendMessage = useCallback(async (message: string) => {
    if (!message.trim() || loading) return

    setLoading(true)
    setError(null)

    // Add user message
    addMessage(agentId, { role: 'user', content: message })

    // Start streaming
    setStreaming(agentId, true)

    // Accumulate assistant response
    let assistantContent = ''
    const startTs = performance.now()

    try {
      await agentApi.chat(agentId, message, (event, data) => {
        switch (event) {
          case 'status':
            // Agent is thinking
            break
          case 'content':
            assistantContent += typeof data === 'string' ? data : JSON.stringify(data)
            // Update last assistant message or create new one
            addMessage(agentId, { role: 'assistant', content: assistantContent })
            break
          case 'tool_call':
            addToolActivity(agentId, {
              tool: data.tool,
              arguments: data.arguments,
              timestamp: new Date().toISOString(),
            })
            break
          case 'tool_result':
            addToolActivity(agentId, {
              tool: data.tool,
              arguments: {},
              result: data.result,
              timestamp: new Date().toISOString(),
            })
            break
          case 'done':
            setStreaming(agentId, false)
            break
          case 'error':
            setError(typeof data === 'string' ? data : data.error || '未知错误')
            setStreaming(agentId, false)
            break
        }
      })
      // Log a successful agent interaction (OpenClaw monitoring + AI interaction behavior)
      logAgent({
        agentId,
        latencyMs: Math.round(performance.now() - startTs),
        success: true,
        inputContent: message,
        aiResponse: assistantContent.slice(0, 500),
      })
    } catch (e: any) {
      setError(e.message || 'Agent通信失败')
      setStreaming(agentId, false)
      // Log a failed agent interaction
      logAgent({
        agentId,
        latencyMs: Math.round(performance.now() - startTs),
        success: false,
        errorDetail: e.message || 'Agent通信失败',
        inputContent: message,
      })
    } finally {
      setLoading(false)
    }
  }, [agentId, loading, addMessage, setStreaming, addToolActivity, logAgent])

  return {
    messages: messages[agentId] || [],
    isStreaming: isStreaming[agentId] || false,
    toolActivity: toolActivity[agentId] || [],
    sendMessage,
    loading,
    error,
  }
}
