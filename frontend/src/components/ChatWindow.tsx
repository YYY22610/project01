import { useState, useRef, useEffect } from 'react'
import { useAgentChat } from '../hooks/useAgentChat'
import { useBehaviorLogger } from '../hooks/useBehaviorLogger'
import ReactMarkdown from 'react-markdown'
import { Sparkles, Send } from 'lucide-react'

interface ChatWindowProps {
  agentId: string
  className?: string
}

export default function ChatWindow({ agentId, className = '' }: ChatWindowProps) {
  const { messages, isStreaming, sendMessage, loading } = useAgentChat(agentId)
  const { log } = useBehaviorLogger()
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const msg = input
    setInput('')
    log({ action_type: 'agent_message', input_content: msg, agent_id: agentId })
    await sendMessage(msg)
  }

  return (
    <div className={`flex flex-col bg-white ${className}`}>
      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
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
                  <ReactMarkdown>{msg.content || ''}</ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        {isStreaming && (
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
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="w-9 h-9 rounded-full bg-blue-600 text-white flex items-center justify-center hover:bg-blue-700 disabled:opacity-50 shrink-0"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
