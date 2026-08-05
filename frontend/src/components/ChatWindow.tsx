import { useState, useRef, useEffect } from 'react'
import { useAgentChat } from '../hooks/useAgentChat'
import { useBehaviorLogger } from '../hooks/useBehaviorLogger'
import { useUserStore } from '../stores/userStore'
import ReactMarkdown from 'react-markdown'
import { api } from '../services/api'
import { Sparkles, Send, Check, Square, Ban, LogIn, FileDown } from 'lucide-react'
import type { ToolActivity } from '../stores/chatStore'

/** 引导词：按助理 + 对话阶段（开场/推进/收尾）切换，点击即发送，帮助推进攻略流程 */
const SUGGESTION_SETS: Record<string, { start: string[]; progress: string[]; done: string[] }> = {
  soa: {
    start: [
      '我想安排休闲一点的 3 日游',
      '我预算紧，控制在 1000 元以内',
      '带老人小孩，不要太累',
      '我更爱自然风光和美食',
    ],
    progress: [
      '这个方案不错，把第二天调轻松些',
      '帮我算一下目前总预算',
      '多推荐几个西湖周边免费景点',
      '住宿和交通大概花多少',
    ],
    done: [
      '就按这个生成 Word 攻略',
      '把攻略导出成 Word 文档',
      '给我设个出发前提醒',
      '把攻略发到我邮箱',
    ],
  },
  moa_a: {
    start: [
      '帮我搜杭州经典必游景点',
      '有哪些免费又值得去的景点',
      '适合带老人的轻松景点',
      '西湖周边有什么好逛的',
    ],
    progress: [
      '再多推荐几个自然风光类',
      '这些景点门票大概多少',
      '怎么去这些景点最方便',
      '帮我对比灵隐寺和西溪湿地',
    ],
    done: [
      '信息够了，交给编排专员出方案',
      '把景点清单整理一下',
    ],
  },
  moa_b: {
    start: [
      '根据已有景点帮我排 3 天行程',
      '做一份预算 1000 内的行程',
      '我要休闲不赶的节奏',
      '把住宿和交通也排进去',
    ],
    progress: [
      '把第一天和第二天再优化下',
      '帮我算一下 3 天总预算',
      '行程别太紧凑，留点自由时间',
      '加入几个必吃的美食点',
    ],
    done: [
      '就按这个生成 Word 攻略',
      '把攻略导出成 Word 文档',
      '顺便算下预算是否超 1000',
    ],
  },
}

/** 文档下载按钮：浏览器直接点 <a> 不会带 JWT，因此用 axios 取 blob 后触发下载 */
function DocxDownloadButton({ href }: { href: string }) {
  const [downloading, setDownloading] = useState(false)

  const handleClick = async (e: React.MouseEvent) => {
    e.preventDefault()
    setDownloading(true)
    try {
      // api 实例 baseURL 已是 /api，href 若带 /api 前缀需去掉，避免拼成 /api/api/document/...
      const path = href.startsWith('/api/') ? href.slice(4) : href
      const response = await api.get(path, { responseType: 'blob' })
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = decodeURIComponent(href.split('/').pop() || 'document.docx')
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      // eslint-disable-next-line no-console
      console.error('Docx download failed', 'href=', href, 'status=', err?.response?.status, err?.response?.data, err?.message)
      const status = err?.response?.status ?? 'network'
      // blob 形式的错误响应需要手动读文本才能展示 detail
      let detail = ''
      if (err?.response?.data instanceof Blob) {
        try {
          detail = await err.response.data.text()
        } catch {
          detail = '(无法读取错误详情)'
        }
      } else if (typeof err?.response?.data === 'string') {
        detail = err.response.data
      } else if (err?.response?.data?.detail) {
        detail = err.response.data.detail
      }
      alert(`文档下载失败 [${status}]\n请求文件: ${decodeURIComponent(href.split('/').pop() || '')}\n${detail || err?.message || '请确认已登录后重试'}`)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={downloading}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 disabled:opacity-60 transition"
    >
      <FileDown size={14} />
      {downloading ? '下载中…' : '点击下载 Word 文档'}
    </button>
  )
}

/** ReactMarkdown 链接渲染：仅对 /api/document/download/ 开头的链接做 JWT 下载 */
function MarkdownLink({ href, children, ...rest }: React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  if (typeof href === 'string' && href.startsWith('/api/document/download/')) {
    return <DocxDownloadButton href={href} />
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" {...rest}>
      {children}
    </a>
  )
}

interface ChatWindowProps {
  agentId: string
  className?: string
  /** 当用户使用 AI 助手（发送任意消息）时触发，用于在任务进度中标记"搜索景点"完成 */
  onAIMessageSent?: () => void
}

/** 单个工具调用步骤：调用中转圈，完成后绿勾，中断时红叉 */
function ActivityStep({ activity, cancelled }: { activity: ToolActivity; cancelled: boolean }) {
  const calling = activity.state === 'calling'
  return (
    <li className="flex items-center gap-2 text-xs">
      {calling && !cancelled ? (
        <span className="w-3.5 h-3.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin shrink-0" />
      ) : calling && cancelled ? (
        <span className="w-3.5 h-3.5 rounded-full bg-red-400 flex items-center justify-center shrink-0">
          <Ban size={9} className="text-white" strokeWidth={3} />
        </span>
      ) : (
        <span className="w-3.5 h-3.5 rounded-full bg-green-500 flex items-center justify-center shrink-0">
          <Check size={10} className="text-white" strokeWidth={3} />
        </span>
      )}
      <span className={
        calling && !cancelled ? 'text-blue-600 font-medium'
          : calling && cancelled ? 'text-red-400'
          : 'text-gray-600'
      }>
        {calling && cancelled ? '已中断' : activity.status}
      </span>
    </li>
  )
}

/** 助理实时执行状态面板（流式期间显示，完成后保留为"执行过程"） */
function AgentStatusPanel({
  activities,
  thinkingText,
  showThinking,
  cancelled,
}: {
  activities: ToolActivity[]
  thinkingText: string
  showThinking: boolean
  cancelled: boolean
}) {
  // 被中断且没有任何步骤：显示"已中断"提示框
  if (activities.length === 0 && !showThinking && !cancelled) return null
  return (
    <div className="flex justify-start">
      <div className="w-7 h-7 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px] font-bold mr-2 shrink-0 mt-0.5">
        AI
      </div>
      <div className={`max-w-[85%] rounded-2xl rounded-bl-none px-4 py-3 ${
        cancelled
          ? 'bg-red-50 border border-red-100'
          : 'bg-gray-50 border border-gray-100'
      }`}>
        {activities.length > 0 ? (
          <>
            <div className="text-[11px] font-semibold text-gray-400 mb-2 tracking-wide">执行状态</div>
            <ul className="space-y-1.5">
              {activities.map((a) => (
                <ActivityStep key={a.id} activity={a} cancelled={cancelled} />
              ))}
            </ul>
          </>
        ) : (
          <div className={`flex items-center gap-2 text-xs font-medium ${
            cancelled ? 'text-red-500' : 'text-blue-600'
          }`}>
            {cancelled ? (
              <Ban size={14} strokeWidth={2.5} />
            ) : (
              <span className="w-3.5 h-3.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            )}
            {cancelled
              ? (thinkingText || '操作已被你中断，请重新下达指令。')
              : (thinkingText || '正在思考如何帮你完成行程规划任务…')}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ChatWindow({ agentId, className = '', onAIMessageSent }: ChatWindowProps) {
  const { messages, isStreaming, toolActivity, statusText, cancelled, sendMessage, cancel, loading, error, needsRelogin } = useAgentChat(agentId)
  const { log } = useBehaviorLogger()
  const logout = useUserStore((s) => s.logout)
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(true)
  const userScrollingRef = useRef(false)
  const scrollTimerRef = useRef<number | null>(null)

  // 检测滚动容器是否接近底部（阈值 50px）
  const checkAtBottom = () => {
    const el = scrollRef.current
    if (!el) return true
    return el.scrollHeight - el.scrollTop - el.clientHeight < 50
  }

  // 平滑滚动到底部
  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior })
  }

  // 监听用户滚动：若用户主动向上翻看历史，暂停自动跟底；若滚回底部，恢复自动跟底
  const handleScroll = () => {
    if (scrollTimerRef.current) window.clearTimeout(scrollTimerRef.current)
    userScrollingRef.current = true
    isAtBottomRef.current = checkAtBottom()
    scrollTimerRef.current = window.setTimeout(() => {
      userScrollingRef.current = false
    }, 150)
  }

  // 当消息或执行状态变化时，仅在用户未主动翻看历史且原本已在底部时才自动滚动
  useEffect(() => {
    if (userScrollingRef.current || !isAtBottomRef.current) return
    scrollToBottom(messages.length <= 1 ? 'auto' : 'smooth')
  }, [messages, toolActivity])

  useEffect(() => {
    return () => {
      if (scrollTimerRef.current) window.clearTimeout(scrollTimerRef.current)
    }
  }, [])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const msg = input
    setInput('')
    // 只要使用了 AI 助手（发送任意消息），即视为完成"搜索景点"任务
    onAIMessageSent?.()
    isAtBottomRef.current = true
    scrollToBottom('auto')
    log({ action_type: 'agent_message', input_content: msg, agent_id: agentId })
    await sendMessage(msg)
  }

  const handleStop = async () => {
    await cancel()
  }

  // 分组被后台修改后旧 token 失效，引导用户重新登录刷新分组信息
  const handleRelogin = () => {
    logout()
    window.location.href = '/register'
  }

  // 引导词：按助理与对话阶段（开场/推进/收尾）切换，点击即发送推进流程
  const userSaidExport = messages.some(
    (m) => m.role === 'user' && /生成|导出|word|保存攻略|发我|文档/i.test(m.content || '')
  )
  const stage: 'start' | 'progress' | 'done' =
    messages.length === 0 ? 'start' : userSaidExport ? 'done' : 'progress'
  const stageSet = SUGGESTION_SETS[agentId]
  // 开场只显示开场组；收尾只显示收尾组；推进组在显示推进词的同时自动追加收尾组引导词，
  // 用户可直接点击"生成 Word 攻略"而无需先手输"生成"
  const startSuggestions: string[] = stage === 'start' ? stageSet?.start ?? [] : []
  const progressSuggestions: string[] = stage === 'progress' ? stageSet?.progress ?? [] : []
  const doneSuggestions: string[] =
    stage === 'done' ? stageSet?.done ?? [] : stage === 'progress' ? stageSet?.done ?? [] : []

  const handleSuggestion = async (text: string) => {
    if (loading) return
    // 只要使用了 AI 助手（点击引导词也视为使用），即触发"搜索景点"完成
    onAIMessageSent?.()
    isAtBottomRef.current = true
    scrollToBottom('auto')
    log({ action_type: 'agent_message', input_content: text, agent_id: agentId })
    await sendMessage(text)
  }

  const hasAssistantBubble = messages.some((m) => m.role === 'assistant')
  // 流式且尚无任何工具调用/回答时，显示"正在思考…"
  const showThinking = isStreaming && toolActivity.length === 0 && !hasAssistantBubble

  return (
    <div className={`flex flex-col bg-white ${className}`}>
      {/* Messages */}
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !isStreaming && (
          <div className="text-center text-gray-400 py-10">
            <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-500 flex items-center justify-center mx-auto mb-3">
              <Sparkles size={20} />
            </div>
            <p className="text-sm">在下方输入框中发送消息</p>
            <p className="text-xs mt-1">AI 助手将帮助你完成行程规划任务</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px] font-bold mr-2 shrink-0 mt-0.5">
                AI
              </div>
            )}
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white rounded-br-none'
                : 'bg-gray-100 text-gray-800 rounded-bl-none'
            }`}>
              {msg.role === 'assistant' ? (
                <div className="markdown-content">
                  <ReactMarkdown components={{ a: MarkdownLink }}>{msg.content || ''}</ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {/* 实时执行状态面板 */}
        <AgentStatusPanel
          activities={toolActivity}
          thinkingText={statusText}
          showThinking={showThinking}
          cancelled={cancelled}
        />

        {/* AI 服务异常提示：真实 LLM API 偶发超时/限流时给出明确反馈，避免"无声无息没输出" */}
        {error && (
          <div className="flex justify-start">
            <div className="w-7 h-7 rounded-full bg-red-500 text-white flex items-center justify-center text-[10px] font-bold mr-2 shrink-0 mt-0.5">
              !
            </div>
            <div className="max-w-[80%] rounded-2xl rounded-bl-none px-4 py-2.5 text-sm bg-red-50 text-red-700 border border-red-200">
              {(() => {
                const isNetwork =
                  /Failed to fetch|NetworkError|Load failed|net::ERR|timeout/i.test(error || '')
                const isGroup = /无效的助理ID|当前用户组不支持/i.test(error || '')
                if (isNetwork) {
                  return (
                    <>
                      <p className="font-medium">无法连接后端服务</p>
                      <p className="mt-1 text-xs leading-relaxed">{error}</p>
                      <p className="mt-1.5 text-xs text-red-500">
                        请确认后端 uvicorn 已启动（在本机终端运行：<code className="bg-red-100 px-1 rounded">uvicorn app.main:app --host 127.0.0.1 --port 8000</code>），然后刷新页面重试。
                      </p>
                      <button
                        onClick={() => window.location.reload()}
                        className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 transition"
                      >
                        <LogIn size={13} />
                        刷新重试
                      </button>
                    </>
                  )
                }
                if (isGroup || needsRelogin) {
                  return (
                    <>
                      <p className="font-medium">AI 助手暂时无法回复</p>
                      <p className="mt-1 text-xs leading-relaxed">{error}</p>
                      <p className="mt-1.5 text-xs text-red-500">
                        当前登录账号的分组与 AI 助理不匹配，重新登录即可同步最新分组。
                      </p>
                      <button
                        onClick={handleRelogin}
                        className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 transition"
                      >
                        <LogIn size={13} />
                        重新登录
                      </button>
                    </>
                  )
                }
                return (
                  <>
                    <p className="font-medium">AI 助手暂时无法回复</p>
                    <p className="mt-1 text-xs leading-relaxed">{error}</p>
                    <p className="mt-1.5 text-xs text-red-500">可能是模型服务繁忙或网络波动，请稍后点击发送重试。</p>
                  </>
                )
              })()}
            </div>
          </div>
        )}

        {isStreaming && hasAssistantBubble && (
          <div className="flex justify-start">
            <div className="w-7 h-7 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px] font-bold mr-2 shrink-0">
              AI
            </div>
            <div className="bg-gray-100 rounded-2xl rounded-bl-none px-4 py-2.5">
              <span className="inline-block w-1.5 h-4 bg-gray-400 animate-pulse rounded-full" />
            </div>
          </div>
        )}
      </div>

      {/* Input — 携程风格底部输入条 */}
      <div className="border-t border-gray-100 p-3">
        {/* 引导词气泡：点击即发送，按阶段推进攻略流程 */}
        {(startSuggestions.length > 0 || progressSuggestions.length > 0 || doneSuggestions.length > 0) && (
          <div className="flex flex-wrap gap-2 mb-2">
            {startSuggestions.map((s) => (
              <button
                key={s}
                disabled={loading}
                onClick={() => handleSuggestion(s)}
                className="text-xs px-3 py-1.5 rounded-full bg-blue-50 text-blue-600 border border-blue-100 hover:bg-blue-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {s}
              </button>
            ))}
            {progressSuggestions.map((s) => (
              <button
                key={s}
                disabled={loading}
                onClick={() => handleSuggestion(s)}
                className="text-xs px-3 py-1.5 rounded-full bg-blue-50 text-blue-600 border border-blue-100 hover:bg-blue-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {s}
              </button>
            ))}
            {progressSuggestions.length > 0 && doneSuggestions.length > 0 && (
              <span className="w-full text-[10px] text-gray-400 mt-1">
                — 以下为收尾操作，点击即可直接生成攻略 —
              </span>
            )}
            {doneSuggestions.map((s) => (
              <button
                key={s}
                disabled={loading}
                onClick={() => handleSuggestion(s)}
                className="text-xs px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        <div className="flex items-center gap-2 bg-gray-100 rounded-full px-4 py-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            disabled={loading}
            className="flex-1 bg-transparent border-0 focus:ring-0 text-sm text-gray-800 placeholder:text-gray-400 outline-none"
            placeholder="任何旅游相关的问题都可以问我哦"
          />
          {isStreaming ? (
            <button
              onClick={handleStop}
              title="停止当前操作"
              className="w-9 h-9 rounded-full bg-red-500 text-white flex items-center justify-center hover:bg-red-600 shrink-0"
            >
              <Square size={15} fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="w-9 h-9 rounded-full bg-blue-600 text-white flex items-center justify-center hover:bg-blue-700 disabled:opacity-50 shrink-0"
            >
              <Send size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
