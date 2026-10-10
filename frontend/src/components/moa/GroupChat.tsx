import React, { useEffect, useRef, useState } from 'react'
import { Send, Sparkles, Loader2 } from 'lucide-react'
import { MOA_MEMBERS, type Member } from './MemberPanel'
import type { GroupMsg, GroupContext } from '../../hooks/useGroupChat'

const NAME_COLOR: Record<string, string> = Object.fromEntries(
  MOA_MEMBERS.map((m: Member) => [m.name, m.color])
)
const MENTION_RE = /(@(?:财务总监|美食达人|人文使者|风光猎人|主持人))/g

/** @提及 染色 */
function renderMentions(text: string) {
  const parts = text.split(MENTION_RE)
  return parts.map((part, i) => {
    if (part.startsWith('@') && NAME_COLOR[part.slice(1)]) {
      return (
        <span key={i} className="font-semibold px-0.5 rounded" style={{ color: NAME_COLOR[part.slice(1)] }}>
          {part}
        </span>
      )
    }
    return <React.Fragment key={i}>{part}</React.Fragment>
  })
}

/** 段内处理 markdown 加粗（变 <strong>，不再显示字面 **），再叠加 @mention 染色 */
function renderInlineRich(text: string): React.ReactNode {
  const nodes: React.ReactNode[] = []
  const boldRe = /\*\*([^*]+)\*\*/g
  let last = 0
  let m: RegExpExecArray | null
  let k = 0
  while ((m = boldRe.exec(text)) !== null) {
    if (m.index > last) {
      nodes.push(<React.Fragment key={k++}>{renderMentions(text.slice(last, m.index))}</React.Fragment>)
    }
    nodes.push(<strong key={k++}>{m[1]}</strong>)
    last = boldRe.lastIndex
  }
  if (last < text.length) {
    nodes.push(<React.Fragment key={k++}>{renderMentions(text.slice(last))}</React.Fragment>)
  }
  return nodes
}

/**
 * 消息渲染：按任意 @ 切分成独立段落（每段 <div>，段间 mt-2 间距），
 * 段内渲染 **加粗** 和 @mention（仅团队成员名染色，其他 @xxx 当普通文本）。
 * 流式累加时段数自然变化，React 自动 reconcile。
 */
function renderMessage(text: string) {
  const segments = text.split(/(?=@)/)
  return (
    <>
      {segments.map((seg, i) => (
        <div key={i} className={i > 0 ? 'mt-2' : undefined}>
          {renderInlineRich(seg)}
        </div>
      ))}
    </>
  )
}

interface Props {
  messages: GroupMsg[]
  loading: boolean
  error: string | null
  ctx: GroupContext
  onSend: (text: string) => void
  awaitingUser?: null | { kind: 'user' | 'confirm'; prompt: string }
  onResume?: (text: string) => void
}

export default function GroupChat({ messages, loading, error, ctx, onSend, awaitingUser, onResume }: Props) {
  const [input, setInput] = useState('')
  // 长发言截断保护：超过 280 字的 AI 消息默认折叠为前 280 字 + 「展开全文」，
  // 避免一条消息占满屏幕。点击后展开。流式累加时若超出阈值再次折叠。
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const submit = () => {
    const t = input.trim()
    if (!t || loading) return
    // 群聊暂停等待用户输入时，本条输入走「恢复」接口回填给后端
    if (awaitingUser && onResume) {
      onResume(t)
    } else {
      onSend(t)
    }
    setInput('')
  }

  return (
    <div className="flex flex-col h-full min-h-0 bg-white border-r border-gray-100">
      {/* 顶部：讨论室标题 + 任务 chip */}
      <div className="h-14 px-4 border-b border-gray-100 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-1.5 text-base font-semibold text-gray-900">
          <Sparkles size={17} className="text-blue-600" /> 规划讨论室
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-gray-500">
          <span className="px-2 py-1 rounded-full bg-blue-50">📍 {ctx.dest}</span>
          <span className="px-2 py-1 rounded-full bg-blue-50">{ctx.days} 天</span>
          <span className="px-2 py-1 rounded-full bg-blue-50">¥{ctx.budget}</span>
          <span className="px-2 py-1 rounded-full bg-blue-50">{ctx.travelers}</span>
        </div>
      </div>

      {/* 消息区 */}
      <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !loading && (
          <div className="text-center text-gray-400 py-10">
            <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-500 flex items-center justify-center mx-auto mb-3 text-xl">
              💬
            </div>
            <p className="text-sm">点击下方输入你的旅行偏好，智囊团将展开群辩</p>
            <p className="text-xs mt-1">例如：一个人，喜欢人文和美食，不要太赶</p>
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.isUser ? 'justify-end' : 'justify-start'}`}>
            {!m.isUser && (
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 mr-2 mt-0.5"
                style={{ background: `${m.color}1f`, color: m.color }}
              >
                {m.emoji}
              </div>
            )}
            <div className={`max-w-[82%] ${m.isUser ? 'items-end' : ''}`}>
              {!m.isUser && (
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-xs font-semibold" style={{ color: m.color }}>
                    {m.name}
                  </span>
                  {m.specialty && <span className="text-[10px] text-gray-400">{m.specialty}</span>}
                </div>
              )}
              <div
                className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  m.isUser
                    ? 'bg-blue-600 text-white rounded-br-none'
                    : 'bg-white border text-gray-800 rounded-bl-none'
                }`}
                style={!m.isUser ? { borderColor: '#eef2f7', borderLeft: `3px solid ${m.color}` } : undefined}
              >
                {m.speaking && m.content === '' ? (
                  <span className="inline-flex items-center gap-1 text-gray-400">
                    <Loader2 size={13} className="animate-spin" /> 思考中…
                  </span>
                ) : !m.isUser && m.content.length > 280 && !expanded.has(m.id) ? (
                  <>
                    <span className="whitespace-pre-wrap">{renderMessage(m.content.slice(0, 280) + '…')}</span>
                    <button
                      onClick={() => setExpanded((s) => { const n = new Set(s); n.add(m.id); return n })}
                      className="block mt-1.5 text-[11px] text-blue-600 hover:underline"
                    >
                      展开全文（{m.content.length} 字）
                    </button>
                  </>
                ) : !m.isUser && m.content.length > 280 && expanded.has(m.id) ? (
                  <>
                    <span className="whitespace-pre-wrap">{renderMessage(m.content)}</span>
                    <button
                      onClick={() => setExpanded((s) => { const n = new Set(s); n.delete(m.id); return n })}
                      className="block mt-1.5 text-[11px] text-blue-600 hover:underline"
                    >
                      收起
                    </button>
                  </>
                ) : (
                  <span className="whitespace-pre-wrap">{renderMessage(m.content)}</span>
                )}
              </div>
            </div>
          </div>
        ))}

        {error && (
          <div className="text-center text-sm text-red-500 bg-red-50 border border-red-200 rounded-xl py-2">
            {error}
          </div>
        )}
      </div>

      {/* 输入条 */}
      <div className="p-3 border-t border-gray-100 shrink-0">
        {awaitingUser && (
          <div className="mb-2 px-3 py-2 rounded-xl bg-blue-50 border border-blue-200 text-[13px] text-blue-800 flex items-start gap-2">
            <span className="shrink-0">{awaitingUser.kind === 'confirm' ? '📋' : '🎯'}</span>
            <span>
              {awaitingUser.kind === 'confirm'
                ? '方案草案已生成：输入「确认」采用，或写下你的修改意见让主持人修订。'
                : awaitingUser.prompt}
            </span>
          </div>
        )}
        <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-2xl px-3 py-1.5 focus-within:ring-2 focus-within:ring-blue-200">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            disabled={loading}
            placeholder={
              loading
                ? '智囊团讨论中…'
                : awaitingUser
                  ? (awaitingUser.kind === 'confirm' ? '输入「确认」或你的修改意见…' : '输入你的回答…')
                  : '说说你的旅行偏好，如：喜欢人文和美食，预算紧'
            }
            className="flex-1 bg-transparent outline-none text-sm py-1.5 disabled:opacity-50"
          />
          <button
            onClick={submit}
            disabled={loading || !input.trim()}
            className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center hover:bg-blue-700 disabled:opacity-50 transition shrink-0"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
