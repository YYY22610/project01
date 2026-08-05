import { useState, useCallback, useRef } from 'react'
import { agentApi } from '../services'
import { useChatStore } from '../stores/chatStore'
import { useBehaviorLogger } from './useBehaviorLogger'

export function useAgentChat(agentId: string) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [needsRelogin, setNeedsRelogin] = useState(false)
  const { messages, isStreaming, toolActivity, statusText, cancelled, addMessage, setStreaming, addToolCall, completeToolCall, resetToolActivity, setStatusText, setCancelled, updateAssistantContent } = useChatStore()
  const { logAgent } = useBehaviorLogger()
  // 当前轮次的 AbortController，用于中断 fetch 流读取
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (message: string) => {
    if (!message.trim() || loading) return

    setLoading(true)
    setError(null)
    setNeedsRelogin(false)

    // 新一轮：重置中断标志与状态日志，并新建 abort 控制器
    resetToolActivity(agentId)
    abortRef.current = new AbortController()

    // Add user message
    addMessage(agentId, { role: 'user', content: message })

    // Start streaming — 本轮重置状态日志
    setStreaming(agentId, true)
    setStatusText(agentId, '正在思考如何帮你完成行程规划任务…')

    // Accumulate assistant response
    let assistantContent = ''
    const startTs = performance.now()

    try {
      await agentApi.chat(agentId, message, (event, data) => {
        switch (event) {
          case 'status':
            // 后端推送的"正在思考…"等状态文案
            if (data?.message) setStatusText(agentId, data.message)
            break
          case 'content':
            assistantContent += typeof data === 'string' ? data : JSON.stringify(data)
            // 原地更新同一条 assistant 消息（流式），不要再追加成多条气泡
            updateAssistantContent(agentId, assistantContent)
            break
          case 'tool_call':
            addToolCall(agentId, {
              id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
              tool: data.tool,
              status: data.status || '正在执行操作…',
              arguments: data.arguments,
              state: 'calling',
              timestamp: new Date().toISOString(),
            })
            break
          case 'tool_result':
            completeToolCall(
              agentId,
              data.tool,
              data.status || '操作完成',
              data.result
            )
            break
          case 'cancelled':
            // 后端确认本轮已被中断
            setCancelled(agentId, true)
            setStatusText(agentId, data?.message || '操作已被你中断，可重新下达指令。')
            setStreaming(agentId, false)
            break
          case 'done':
            setStreaming(agentId, false)
            break
          case 'error':
            setError(typeof data === 'string' ? data : data.error || '未知错误')
            setStreaming(agentId, false)
            break
        }
      }, abortRef.current.signal)
      // Log a successful agent interaction (OpenClaw monitoring + AI interaction behavior)
      logAgent({
        agentId,
        latencyMs: Math.round(performance.now() - startTs),
        success: true,
        inputContent: message,
        aiResponse: assistantContent.slice(0, 500),
      })
    } catch (e: any) {
      // 用户主动中断（AbortController.abort）已被 services 层静默吞掉，不会进这里
      const msg = e.message || 'Agent通信失败'
      // 分组在后台被修改后，旧 token 与数据库不一致会导致 400/403；提示重新登录而非误导为网络问题
      if (/无效的助理ID|当前用户组不支持/.test(msg)) {
        setNeedsRelogin(true)
      }
      setError(msg)
      setStreaming(agentId, false)
      // Log a failed agent interaction
      logAgent({
        agentId,
        latencyMs: Math.round(performance.now() - startTs),
        success: false,
        errorDetail: msg,
        inputContent: message,
      })
    } finally {
      setLoading(false)
      abortRef.current = null
    }
  }, [agentId, loading, addMessage, setStreaming, addToolCall, completeToolCall, resetToolActivity, setStatusText, setCancelled, updateAssistantContent, logAgent])

  /** 干预能力：参与者随时中断助理当前操作，随后可重新下达指令 */
  const cancel = useCallback(async () => {
    if (!loading && !isStreaming[agentId]) return
    // 1) 通知后端置位取消标志（真正拦住运行中的工具，如发邮件/生成Word）
    try {
      await agentApi.cancel(agentId)
    } catch {
      // 即便后端调用失败，也照常中断前端读取，保证 UI 即时响应
    }
    // 2) 中断前端 fetch 流读取
    abortRef.current?.abort()
    abortRef.current = null
    // 3) 更新 UI 状态
    setCancelled(agentId, true)
    setStatusText(agentId, '操作已被你中断，请重新下达指令。')
    setStreaming(agentId, false)
    setLoading(false)
  }, [agentId, loading, isStreaming, setCancelled, setStatusText, setStreaming])

  return {
    messages: messages[agentId] || [],
    isStreaming: isStreaming[agentId] || false,
    toolActivity: toolActivity[agentId] || [],
    statusText: statusText[agentId] || '',
    cancelled: cancelled[agentId] || false,
    sendMessage,
    cancel,
    loading,
    error,
    needsRelogin,
  }
}
