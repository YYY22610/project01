import { useState, useCallback, useRef, useEffect } from 'react'
import { groupApi } from '../services'
import { useChatStore } from '../stores/chatStore'
import { useBehaviorLogger } from './useBehaviorLogger'

export interface GroupMsg {
  id: string
  role_id: string        // 'user' | persona id | 'facilitator'
  name: string
  emoji: string
  color: string
  specialty?: string
  content: string
  isUser?: boolean
  speaking?: boolean
}

export interface GroupPlan {
  markdown: string
  /** 结构化数据（用于右侧栏卡片化渲染）：meta + days[] + 其他六项字段 */
  data?: {
    meta?: { travelers?: string; total?: string; style?: string; pace?: string }
    days?: { tag?: string; title?: string; items?: { time?: string; text?: string }[] }[]
    spots?: { name?: string; stay?: string; fee?: string }[]
    transport?: string | string[]
    lodging?: string | string[]
    dining?: string | string[]
    budget?: string
  } | null
  quotes: { role_id: string; name: string; emoji: string; color: string; text: string }[]
}

export interface GroupContext {
  dest: string
  days: number
  budget: number
  travelers: string
}

// ---- 讨论现场数据库持久化（每用户一行，按 user_id 隔离；刷新后恢复现场） ----
interface GroupCache {
  messages: GroupMsg[]
  plan: GroupPlan | null
  tempPlan?: Record<string, any> | null
  planConfirmed?: boolean
  stage: string
  stageLabel: string
  started: boolean
  savedAt: number
}

// 刷新后无法续接的等待态（SSE 已断）：降级为「已中断」，可重新发起
const WAIT_STAGES = new Set(['ask_user', 'await_confirm'])

let _mid = 0
const nextId = () => `gm_${Date.now()}_${_mid++}`

export function useGroupChat(ctx: GroupContext) {
  const [messages, setMessages] = useState<GroupMsg[]>([])
  const [plan, setPlan] = useState<GroupPlan | null>(null)
  const [stage, setStage] = useState<string>('idle')
  const [stageLabel, setStageLabel] = useState<string>('')
  const [speakingRoleId, setSpeakingRoleId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [started, setStarted] = useState(false)
  // 跨请求等待用户输入：主持人反问用户(await_user) 或 确认门(await_confirm)
  const [awaitingUser, setAwaitingUser] = useState<null | { kind: 'user' | 'confirm'; prompt: string }>(null)
  // 临时规划（右侧栏实时汇总，六项要素骨架）：讨论中专家发言按【标签】归入
  const [tempPlan, setTempPlan] = useState<Record<string, any> | null>(null)
  // 是否已确认最终方案（done 事件后为 true）：决定右侧栏「临时规划」还是「最终方案」
  const [planConfirmed, setPlanConfirmed] = useState(false)

  const currentRoleRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  // 同步重入保护：setLoading(true) 是异步的，短时间内两次 submit（点按钮 + 按 Enter）
  // 都会看到 loading=false → 调 sendMessage 两次 → 消息/讨论被重复发起。sendingRef 立即置位防重入。
  const sendingRef = useRef<boolean>(false)
  const { logAgent } = useBehaviorLogger()

  // 挂载时从数据库恢复现场（刷新保留；等待态降级为「已中断」）
  useEffect(() => {
    let alive = true
    groupApi
      .getState()
      .then((res) => {
        if (!alive || !res?.context) return
        const c = res.context as GroupCache
        if (!Array.isArray(c.messages) || c.messages.length === 0) return
        // 恢复时清掉 speaking 残留（刷新前可能正卡在流式发言）
        setMessages(c.messages.map((m) => ({ ...m, speaking: false })))
        setPlan(c.plan ?? null)
        setTempPlan(c.tempPlan ?? null)
        setPlanConfirmed(!!c.planConfirmed)
        const wait = WAIT_STAGES.has(c.stage)
        setStage(wait ? 'interrupted' : (c.stage ?? 'idle'))
        setStageLabel(
          wait ? '讨论已中断（页面刷新），发送消息将重新开始一场群聊' : (c.stageLabel ?? '')
        )
        setStarted(!!c.started)
      })
      .catch(() => {
        /* 未登录/接口异常时静默，保持空白新讨论 */
      })
    return () => {
      alive = false
    }
  }, [])

  // 讨论状态变化时自动保存到数据库（防抖 500ms，流式过程中只在停顿/结束时落库）
  useEffect(() => {
    if (!started) return
    const t = setTimeout(() => {
      groupApi
        .saveState({
          messages,
          plan,
          tempPlan,
          planConfirmed,
          stage: awaitingUser ? (awaitingUser.kind === 'confirm' ? 'await_confirm' : 'ask_user') : stage,
          stageLabel,
          started,
          savedAt: Date.now(),
        })
        .catch(() => {
          /* 保存失败不影响前端交互，下次变化会重试 */
        })
    }, 500)
    return () => clearTimeout(t)
  }, [messages, plan, tempPlan, planConfirmed, stage, stageLabel, started, awaitingUser])

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return
    // 同步重入守门：在 setLoading(true) 异步生效前，第二次 submit 直接 return
    if (sendingRef.current) return
    sendingRef.current = true
    setLoading(true)
    setError(null)
    abortRef.current = new AbortController()
    setStarted(true)
    useChatStore.getState().markAIUsed()

    const userMsg: GroupMsg = {
      id: nextId(), role_id: 'user', name: '我', emoji: '🙋', color: '#2577e3',
      content: text, isUser: true,
    }
    setMessages((prev) => [...prev, userMsg])
    setStage('opening')
    setStageLabel('讨论开始')
    try {
      // 刷新后旧的 SSE 会话可能仍驻留后端（active 未清），先静默取消避免 409；
      // 正常流程无会话时调用也无副作用（仅置 cancelled 标志）。
      try {
        await groupApi.cancel()
      } catch {
        /* 无会话时 409/403 属正常，忽略 */
      }
      await groupApi.discuss(
        {
          message: text,
          dest: ctx.dest,
          days: ctx.days,
          budget: ctx.budget,
          travelers: ctx.travelers,
        },
        (event, data) => {
          switch (event) {
            case 'stage':
              setStage(data.stage)
              setStageLabel(data.label || '')
              break
            case 'role_start':
              currentRoleRef.current = data.role_id
              setSpeakingRoleId(data.role_id)
              setMessages((prev) => [
                ...prev,
                {
                  id: nextId(), role_id: data.role_id, name: data.name,
                  emoji: data.emoji, color: data.color, specialty: data.specialty,
                  content: '', speaking: true,
                },
              ])
              break
            case 'content': {
              // 并发场景下多位专家同时流式发言，必须按事件携带的 role_id 归属，
              // 不能依赖单一 currentRoleRef（会被后到的 role_start 覆盖）。
              const rid = data.role_id
              setMessages((prev) =>
                prev.map((m) =>
                  m.role_id === rid && m.speaking
                    ? { ...m, content: m.content + (data.delta || '') }
                    : m
                )
              )
              break
            }
            case 'role_end':
              setSpeakingRoleId(null)
              setMessages((prev) =>
                prev.map((m) =>
                  m.role_id === data.role_id && m.speaking
                    ? { ...m, speaking: false }
                    : m
                )
              )
              break
            case 'await_user':
              // 主持人/角色向用户提问：暂停群聊，等待用户在讨论室输入回答
              setStage('ask_user')
              setStageLabel('主持人向你提问')
              setSpeakingRoleId(null)
              setAwaitingUser({ kind: 'user', prompt: data.prompt || '请回答主持人的问题' })
              // 关键：反问等待期间必须解除 loading，否则输入框 disabled，用户无法回答
              setLoading(false)
              break
            case 'await_confirm':
              // 确认门：展示草案，等待用户「确认 / 修改意见」（右侧栏仍显示临时规划，确认后才切换）
              setPlan(data.plan)
              setStage('await_confirm')
              setStageLabel('方案草案已生成，请确认或提出修改')
              setSpeakingRoleId(null)
              setAwaitingUser({ kind: 'confirm', prompt: data.prompt || '确认方案，或输入修改意见' })
              // 关键：确认门等待期间必须解除 loading，否则输入框 disabled，用户无法确认/改意见
              setLoading(false)
              break
            case 'temp_plan':
              // 专家发言实时汇总到右侧栏「临时规划」（六项要素骨架）
              setTempPlan(data.plan)
              break
            case 'done':
              setPlan(data.plan)
              // 用户已确认 → 右侧栏从「临时规划」切换为「最终方案」
              setPlanConfirmed(true)
              setStage('done')
              setStageLabel('方案已生成')
              setSpeakingRoleId(null)
              setLoading(false)
              break
            case 'error':
              setError(typeof data === 'string' ? data : data.error || '讨论失败')
              setLoading(false)
              break
          }
        },
        abortRef.current.signal
      )
      logAgent({ agentId: 'moa_group', latencyMs: 0, success: true, inputContent: text })
    } catch (e: any) {
      const msg = e.message || '智囊团讨论失败'
      if (!/无效的|不支持|403/.test(msg)) setError(msg)
      setLoading(false)
    } finally {
      setLoading(false)
      abortRef.current = null
      sendingRef.current = false
    }
  }, [loading, ctx.dest, ctx.days, ctx.budget, ctx.travelers, logAgent])

  // 跨请求恢复：把用户的回答/确认意见回填给后端，恢复群聊
  const resume = useCallback(async (text: string) => {
    if (!text.trim() || loading) return
    setLoading(true)
    setError(null)
    const pending = awaitingUser
    setAwaitingUser(null)
    // 用户的回答/确认意见也作为一条消息展示在讨论室
    const userMsg: GroupMsg = {
      id: nextId(), role_id: 'user', name: '我', emoji: '🙋', color: '#2577e3',
      content: text, isUser: true,
    }
    setMessages((prev) => [...prev, userMsg])
    try {
      await groupApi.resume(text)
    } catch (e: any) {
      const msg = e.message || '恢复群聊失败'
      if (!/无效的|不支持|403/.test(msg)) setError(msg)
      setLoading(false)
    }
    // 后续事件（content/role_end/done）由仍在进行的 SSE 流继续推送
  }, [loading, awaitingUser])

  const reset = useCallback(() => {
    setMessages([])
    setPlan(null)
    setTempPlan(null)
    setPlanConfirmed(false)
    setStage('idle')
    setStageLabel('')
    setSpeakingRoleId(null)
    setError(null)
    setStarted(false)
    setAwaitingUser(null)
    currentRoleRef.current = null
    // 同步清除数据库中的上下文，避免重置后刷新又恢复出旧现场
    groupApi.clearState().catch(() => {})
  }, [])

  return { messages, plan, tempPlan, planConfirmed, stage, stageLabel, speakingRoleId, loading, error, started, awaitingUser, sendMessage, resume, reset }
}
