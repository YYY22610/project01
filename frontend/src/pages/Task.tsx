import { useEffect, useState, useRef, Fragment } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../stores/userStore'
import { useBehaviorLogger } from '../hooks/useBehaviorLogger'
import { useTimer } from '../hooks/useTimer'
import { useAgentChat } from '../hooks/useAgentChat'
import { useChatStore } from '../stores/chatStore'
import { searchApi, documentApi, reminderApi, emailApi } from '../services'
import type { SearchResult } from '../types'
import {
  Search, Mail, Bell, FileText, Target, Sparkles, CheckCircle2, Clock,
  Luggage, CalendarDays, Trash2, ExternalLink
} from 'lucide-react'
import ChatWindow from '../components/ChatWindow'

type SubTabKey = 'overview' | 'doc' | 'reminder' | 'email'
type LeftTabKey = 'ai' | 'search'

export default function Task() {
  const { user, taskConfig, taskStatus, fetchTaskConfig, fetchTaskStatus, submitTask } = useUserStore()
  const { log, logSearch, logPlanEdit, logPlanSubmit } = useBehaviorLogger()
  const editCountRef = useRef(0)
  const navigate = useNavigate()
  const { formatted } = useTimer(taskStatus?.task_start_time || null)

  const dest = taskConfig?.destination || '杭州'
  const days = taskConfig?.task_days || 3
  const budget = taskConfig?.task_budget || 1000
  const email = taskConfig?.target_email || 'experiment@example.com'
  const planTitle = `${dest}${days}日游行程规划`

  const [activeSubTab, setActiveSubTab] = useState<SubTabKey>('overview')
  const [leftTab, setLeftTab] = useState<LeftTabKey>('ai')
  // 完成"搜索景点"任务的两种触发方式：
  //   1) 用户已与 AI 助手有过对话（chatStore.hasUsedAI + 直接检查 messages，双保险）
  //   2) 用户在搜索引擎中执行了搜索（searchTriggered）
  const hasUsedAI = useChatStore((s) => s.hasUsedAI)
  const chatMessages = useChatStore((s) => s.messages)
  const aiSearchTriggered = hasUsedAI || Object.values(chatMessages).some((arr) => arr && arr.length > 0)
  const [searchTriggered, setSearchTriggered] = useState(false)

  // 兜底：若本地已有历史聊天记录（升级前数据无 hasUsedAI 标记），挂载时回填标志，
  // 避免"之前问过 AI、升级后刷新仍显示未完成"的情况
  useEffect(() => {
    useChatStore.getState().ensureAIUsedFlag()
  }, [])

  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [docContent, setDocContent] = useState('')
  const [docGenerated, setDocGenerated] = useState(false)
  const [reminderDate, setReminderDate] = useState('')
  const [reminderContent, setReminderContent] = useState('')
  const [reminderSet, setReminderSet] = useState(false)
  const [emailSent, setEmailSent] = useState(false)
  const [emailTo, setEmailTo] = useState(user?.email || email)
  const [emailAttachments, setEmailAttachments] = useState<File[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [submitting, setSubmitting] = useState(false)

  // 从 JWT 同步初始化分组信息，避免首屏 showAI 为 false（尚未判定）时
  // 把默认 leftTab 通过下方兜底 effect 强制改回「搜索引擎」
  const getGroupFromToken = (): string | null => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) return null
      const payload = JSON.parse(atob(token.split('.')[1]))
      return payload.group || null
    } catch {
      return null
    }
  }
  const [showAI, setShowAI] = useState(() => {
    const g = getGroupFromToken()
    return g === 'SOA' || g === 'MOA'
  })
  const [isMOA, setIsMOA] = useState(() => getGroupFromToken() === 'MOA')
  const [moaAgent, setMoaAgent] = useState<'moa_a' | 'moa_b'>('moa_a')
  useAgentChat('soa')

  const draftKey = user?.id ? `task_draft_${user.id}` : null

  // 富文本编辑器相关
  const editorRef = useRef<HTMLDivElement>(null)
  const [saveTipShown, setSaveTipShown] = useState(false)

  // 简单去除 HTML 标签，用于行为日志存储纯文本
  const stripHtml = (s: string) =>
    s.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim()

  useEffect(() => {
    fetchTaskConfig()
    fetchTaskStatus()
  }, [])

  useEffect(() => {
    if (!draftKey) return
    try {
      const raw = localStorage.getItem(draftKey)
      if (!raw) return
      const d = JSON.parse(raw)
      if (typeof d.searchQuery === 'string') setSearchQuery(d.searchQuery)
      if (Array.isArray(d.searchResults)) setSearchResults(d.searchResults)
      if (typeof d.docContent === 'string') setDocContent(d.docContent)
      if (typeof d.docGenerated === 'boolean') setDocGenerated(d.docGenerated)
      if (typeof d.reminderDate === 'string') setReminderDate(d.reminderDate)
      if (typeof d.reminderContent === 'string') setReminderContent(d.reminderContent)
      if (typeof d.reminderSet === 'boolean') setReminderSet(d.reminderSet)
      if (typeof d.emailSent === 'boolean') setEmailSent(d.emailSent)
      if (typeof d.emailTo === 'string') setEmailTo(d.emailTo)
      if (typeof d.searchTriggered === 'boolean') setSearchTriggered(d.searchTriggered)
      if (typeof d.activeSubTab === 'string') {
        // 旧版草稿可能有已移除的 'search'，统一回到总览
        const tab: SubTabKey = ['overview', 'doc', 'reminder', 'email'].includes(d.activeSubTab)
          ? d.activeSubTab
          : 'overview'
        setActiveSubTab(tab)
      }
    } catch {
      // 草稿损坏则忽略
    }
  }, [draftKey])

  // 切到「生成文档」标签页时，把已恢复的 HTML 内容写回编辑器（DOM 在切回时会重建）
  useEffect(() => {
    if (activeSubTab === 'doc' && editorRef.current && !editorRef.current.innerHTML && docContent) {
      editorRef.current.innerHTML = docContent
    }
  }, [activeSubTab, docContent])

  useEffect(() => {
    if (!draftKey) return
    const draft = {
      searchQuery, searchResults, docContent, docGenerated,
      reminderDate, reminderContent, reminderSet, emailSent, emailTo,
      searchTriggered, activeSubTab,
    }
    localStorage.setItem(draftKey, JSON.stringify(draft))
  }, [draftKey, searchQuery, searchResults, docContent, docGenerated, reminderDate, reminderContent, reminderSet, emailSent, emailTo, searchTriggered, activeSubTab])

  // H 组无 AI 时，左侧只能停留在搜索引擎
  useEffect(() => {
    if (!showAI) setLeftTab('search')
  }, [showAI])

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        const group = payload.group
        setShowAI(group === 'SOA' || group === 'MOA')
        setIsMOA(group === 'MOA')
      } catch {}
    }
  }, [user])

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    const startTs = performance.now()
    log({ action_type: 'search_query', input_content: searchQuery })
    try {
      const res = await searchApi.search(searchQuery)
      const latency = Math.round(performance.now() - startTs)
      setSearchResults(res.data.results)
      // 用户在搜索引擎执行了搜索 → 触发"搜索景点"任务完成
      setSearchTriggered(true)
      logSearch({ query: searchQuery, resultsViewed: res.data.results.length, latencyMs: latency, success: true })
      log({ action_type: 'search_result_click', action_target: `${res.data.results.length} results` })
    } catch (e) {
      const latency = Math.round(performance.now() - startTs)
      logSearch({ query: searchQuery, latencyMs: latency, success: false })
      alert('搜索失败')
    }
  }

  const handleGenerateDoc = async () => {
    const html = editorRef.current?.innerHTML ?? ''
    if (!html.trim() || html === '<br>' || html === '<div><br></div>') {
      alert('请先输入行程规划内容再生成文档')
      return
    }
    logPlanEdit({ manualEditCount: editCountRef.current, contentSnippet: stripHtml(html).substring(0, 100) })
    try {
      const res = await documentApi.generate(planTitle, html, 'html')
      setDocGenerated(true)
      log({ action_type: 'document_save', action_target: res.data.file_name })
      saveLocalDoc(html)
      alert(`文档已生成并保存到本地: ${res.data.file_name}`)
    } catch (e) {
      alert('文档生成失败')
    }
  }

  const handleSetReminder = async () => {
    if (!reminderDate) return
    if (new Date(reminderDate) < new Date()) {
      alert('提醒时间不能早于当前时间')
      return
    }
    log({ action_type: 'reminder_set', action_target: reminderDate })
    try {
      await reminderApi.set(reminderDate, reminderContent)
      setReminderSet(true)
      log({ action_type: 'reminder_set', action_target: reminderDate })
    } catch (e: any) {
      alert(e.response?.data?.detail || '设置提醒失败')
    }
  }

  const handleSendEmail = async () => {
    if (!emailTo.trim()) {
      alert('请填写收件人邮箱')
      return
    }
    log({ action_type: 'email_send', action_target: emailTo })
    try {
      const res = await emailApi.send(
        emailTo.trim(),
        planTitle,
        `请查收附件中的${planTitle}。`,
        emailAttachments.length ? emailAttachments : undefined,
        taskStatus?.submission?.docx_file_path || undefined
      )
      if (res.data?.status === 'failed') {
        alert('邮件发送失败，请稍后重试')
        return
      }
      setEmailSent(true)
      log({ action_type: 'email_send', action_target: emailTo })
    } catch (e) {
      alert('邮件发送失败')
    }
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await submitTask({
        task1_search: aiSearchTriggered || searchTriggered,
        task2_document: docGenerated,
        task3_reminder: reminderSet,
        task4_email: emailSent,
      })
      logPlanSubmit({ finalPlanText: stripHtml(docContent) })
      log({ action_type: 'task_submit' })
      if (draftKey) localStorage.removeItem(draftKey)
      navigate('/questionnaire')
    } catch (e) {
      alert('提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  const allDone = (aiSearchTriggered || searchTriggered) && docGenerated && reminderSet && emailSent

  const taskProgress = [
    { key: 'search', label: '搜索景点', icon: Search, done: aiSearchTriggered || searchTriggered, subTab: 'overview' as SubTabKey },
    { key: 'doc', label: '生成文档', icon: FileText, done: docGenerated, subTab: 'doc' as SubTabKey },
    { key: 'reminder', label: '设置提醒', icon: Bell, done: reminderSet, subTab: 'reminder' as SubTabKey },
    { key: 'email', label: '发送邮件', icon: Mail, done: emailSent, subTab: 'email' as SubTabKey },
  ]

  const renderOverview = () => (
    <div className="space-y-4">
      {/* 任务概览（参照 travel-planner-ui 的 overview 设计） */}
      <div className="relative">
        <span className="tp-eyebrow absolute top-0 right-0">📍 任务 · TASK</span>
        <div className="flex items-start gap-3 pr-28">
          <span className="w-11 h-11 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0">
            <Target size={20} />
          </span>
          <div className="flex-1">
            <h2 className="font-bold text-2xl text-gray-900 mb-1.5">规划 {dest}{days} 日游</h2>
            <p className="text-base text-gray-500">
              预算 <span className="text-blue-600 font-semibold">{budget} 元</span> · 请完成左侧「搜索引擎」及下方 3 项子任务，完成后点击右上角「提交」。
            </p>
          </div>
        </div>
        <div className="flex gap-8 mt-5 pt-4 border-t border-[#e2ecf5]">
          <div><div className="text-xs text-gray-400">目的地</div><div className="text-lg font-semibold text-gray-900 mt-0.5">{dest}</div></div>
          <div><div className="text-xs text-gray-400">行程天数</div><div className="text-lg font-semibold text-gray-900 mt-0.5">{days} 天</div></div>
          <div><div className="text-xs text-gray-400">预算</div><div className="text-lg font-semibold text-gray-900 mt-0.5">¥ {budget}</div></div>
          <div><div className="text-xs text-gray-400">子任务</div><div className="text-lg font-semibold text-gray-900 mt-0.5">4 项</div></div>
        </div>
      </div>

    </div>
  )

  // 搜索引擎：接入 DuckDuckGo + Bing 实时搜索
  const renderSearchEngine = () => (
    <div className="border border-gray-200 rounded-2xl overflow-hidden bg-white flex flex-col h-full">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between shrink-0">
        <span className="flex items-center gap-1.5 text-sm font-semibold text-gray-700">
          <Search size={15} className="text-blue-600" /> 搜索引擎
        </span>
        <span className="text-xs text-gray-400">DuckDuckGo · Bing</span>
      </div>
      <div className="p-4 space-y-3 flex-1 min-h-0 flex flex-col">
        <div className="flex gap-2 shrink-0">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="flex-1 px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            placeholder="输入关键词，如：杭州西湖"
          />
          <button onClick={handleSearch} className="px-5 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 text-sm font-medium">
            搜索
          </button>
        </div>
        {searchResults.length > 0 ? (
          <div className="space-y-2 flex-1 min-h-0 overflow-y-auto pr-1">
            {searchResults.map((r, i) => (
              <a
                key={i}
                href={r.url || undefined}
                target={r.url ? '_blank' : undefined}
                rel="noopener noreferrer"
                onClick={() => log({ action_type: 'search_result_click', action_target: r.title })}
                className="block p-4 bg-gray-50 rounded-xl border border-transparent hover:bg-blue-50 hover:border-blue-200 hover:shadow-sm transition"
              >
                <div className="flex items-start justify-between gap-2">
                  <h4 className="text-sm font-semibold text-blue-600">{r.title}</h4>
                  <ExternalLink size={14} className="text-gray-400 shrink-0 mt-1" />
                </div>
                <p className="text-xs text-gray-500 mt-1 leading-relaxed">{r.snippet}</p>
                {r.url && <p className="text-[11px] text-gray-400 mt-1 truncate">{r.url}</p>}
                {r.source === 'mock' && (
                  <span className="inline-block mt-1.5 text-[10px] px-1.5 py-0.5 bg-amber-50 text-amber-600 rounded">示例数据</span>
                )}
                {r.source === 'search_engine' && (
                  <span className="inline-block mt-1.5 text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">实时搜索</span>
                )}
              </a>
            ))}
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-sm text-gray-400">暂无结果，输入关键词后点击搜索</p>
          </div>
        )}
      </div>
    </div>
  )

  // ===== 富文本编辑器工具函数 =====
  const handleEditorInput = () => {
    const html = editorRef.current?.innerHTML ?? ''
    setDocContent(html)
    editCountRef.current += 1
  }

  const execCmd = (cmd: string, val?: string) => {
    document.execCommand(cmd, false, val || undefined)
    editorRef.current?.focus()
  }

  const insertTable = () => {
    const rows = window.prompt('行数:', '3')
    if (!rows) return
    const cols = window.prompt('列数:', '3')
    if (!cols) return
    let html = '<table><tbody>'
    for (let i = 0; i < parseInt(rows, 10); i++) {
      html += '<tr>'
      for (let j = 0; j < parseInt(cols, 10); j++) html += '<td>&nbsp;</td>'
      html += '</tr>'
    }
    html += '</tbody></table>'
    execCmd('insertHTML', html)
  }

  // 浏览器端直接生成 .doc（所见即所得，Word/WPS 可打开），并提示已保存
  const saveLocalDoc = (content: string) => {
    const html = content.trim()
    if (!html || html === '<br>' || html === '<div><br></div>') {
      alert('编辑器内容为空，请先输入内容再保存。')
      return
    }
    const fullHtml =
      "<html xmlns:o='urn:schemas-microsoft-com:office:office' " +
      "xmlns:w='urn:schemas-microsoft-com:office:word' " +
      "xmlns='http://www.w3.org/TR/REC-html40'>\n<head>\n" +
      "<meta charset='utf-8'>\n<title>行程规划</title>\n<style>" +
      "body{font-family:'Microsoft YaHei',sans-serif;max-width:800px;margin:40px auto;padding:20px;line-height:1.8;}" +
      "table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ccc;padding:8px;}" +
      "</style>\n</head>\n<body>\n" + html + "\n</body>\n</html>"
    const blob = new Blob([fullHtml], { type: 'application/msword;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    const now = new Date()
    const ts =
      now.getFullYear() +
      String(now.getMonth() + 1).padStart(2, '0') +
      String(now.getDate()).padStart(2, '0') + '_' +
      String(now.getHours()).padStart(2, '0') +
      String(now.getMinutes()).padStart(2, '0')
    a.download = `行程规划_${ts}.doc`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(a.href)
    setSaveTipShown(true)
    setTimeout(() => setSaveTipShown(false), 2000)
  }

  const renderDoc = () => (
    <div className="h-full flex flex-col gap-4">
      <div className="flex items-center gap-3 shrink-0">
        <span className="w-11 h-11 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center">
          <Luggage size={20} />
        </span>
        <div>
          <h4 className="text-lg font-semibold text-gray-900">生成行程文档</h4>
          <p className="text-sm text-gray-500">在下方编辑器中整理行程，可导出为 Word 文档</p>
        </div>
      </div>

      {/* 富文本编辑器（仿 aitravel 内置文本编辑器） */}
      <div className="flex-1 min-h-0 flex flex-col">
        <div className="editor-toolbar shrink-0">
          <button type="button" className="tb-btn" title="加粗" onMouseDown={(e) => e.preventDefault()} onClick={() => execCmd('bold')}><b>B</b></button>
          <button type="button" className="tb-btn" title="斜体" onMouseDown={(e) => e.preventDefault()} onClick={() => execCmd('italic')}><i>I</i></button>
          <button type="button" className="tb-btn" title="下划线" onMouseDown={(e) => e.preventDefault()} onClick={() => execCmd('underline')}><u>U</u></button>
          <div className="tb-sep" />
          <button type="button" className="tb-btn" title="一级标题" onMouseDown={(e) => e.preventDefault()} onClick={() => execCmd('formatBlock', '<h2>')}>H1</button>
          <button type="button" className="tb-btn" title="二级标题" onMouseDown={(e) => e.preventDefault()} onClick={() => execCmd('formatBlock', '<h3>')}>H2</button>
          <button type="button" className="tb-btn" title="正文" onMouseDown={(e) => e.preventDefault()} onClick={() => execCmd('formatBlock', '<p>')}>P</button>
          <div className="tb-sep" />
          <button type="button" className="tb-btn" title="无序列表" onMouseDown={(e) => e.preventDefault()} onClick={() => execCmd('insertUnorderedList')}>&#8226;</button>
          <button type="button" className="tb-btn" title="有序列表" onMouseDown={(e) => e.preventDefault()} onClick={() => execCmd('insertOrderedList')}>1.</button>
          <div className="tb-sep" />
          <button type="button" className="tb-btn" title="插入表格" onMouseDown={(e) => e.preventDefault()} onClick={insertTable}>▦</button>
          <button type="button" className="tb-btn" title="清除格式" onMouseDown={(e) => e.preventDefault()} onClick={() => execCmd('removeFormat')}>&#x2715;</button>
        </div>
        <span className={`save-tip ${saveTipShown ? 'show' : ''}`}>已保存</span>
        <div
          ref={editorRef}
          className="doc-editor flex-1"
          contentEditable
          suppressContentEditableWarning
          data-placeholder="请在此处整理您的行程规划内容…"
          onInput={handleEditorInput}
        />
      </div>

      <div className="flex gap-3 shrink-0">
        <button
          onClick={handleGenerateDoc}
          disabled={!docContent.trim() || docContent === '<br>'}
          className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 text-base font-medium"
        >
          生成 Word
        </button>
      </div>
    </div>
  )

  const renderReminder = () => (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="w-11 h-11 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center">
          <CalendarDays size={20} />
        </span>
        <div>
          <h4 className="text-lg font-semibold text-gray-900">设置旅行提醒</h4>
          <p className="text-sm text-gray-500">设定提醒时间和内容</p>
        </div>
      </div>
      <input
        type="datetime-local"
        value={reminderDate}
        min={new Date(new Date().getTime() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16)}
        onChange={(e) => setReminderDate(e.target.value)}
        className="w-full px-5 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-base"
      />
      <input
        type="text"
        value={reminderContent}
        onChange={(e) => setReminderContent(e.target.value)}
        className="w-full px-5 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-base"
        placeholder="提醒内容（如：出发前往杭州）"
      />
      <button
        onClick={handleSetReminder}
        disabled={!reminderDate || reminderSet}
        className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 text-base font-medium"
      >
        {reminderSet ? '已设置' : '设置提醒'}
      </button>
    </div>
  )

  const renderEmail = () => (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="w-11 h-11 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center">
          <Mail size={20} />
        </span>
        <div>
          <h4 className="text-lg font-semibold text-gray-900">发送行程邮件</h4>
          <p className="text-sm text-gray-500">将行程文档发送给指定收件人</p>
        </div>
      </div>
      <div>
        <label className="block text-base font-medium text-gray-700 mb-2">收件人</label>
        <input
          type="email"
          value={emailTo}
          onChange={(e) => setEmailTo(e.target.value)}
          className="w-full px-5 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-base"
          placeholder="收件人邮箱"
        />
        <p className="text-sm text-gray-400 mt-1.5">默认使用注册邮箱，可修改</p>
      </div>
      <div>
        <label className="block text-base font-medium text-gray-700 mb-2">附件（可选）</label>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={(e) => {
            const picked = e.target.files ? Array.from(e.target.files) : []
            if (picked.length) setEmailAttachments((prev) => [...prev, ...picked])
            e.target.value = ''
          }}
          className="block w-full text-base text-gray-500 file:mr-4 file:py-2.5 file:px-5 file:rounded-xl file:border-0 file:bg-blue-50 file:text-blue-600 hover:file:bg-blue-100"
        />
        {emailAttachments.length > 0 && (
          <ul className="mt-3 space-y-2">
            {emailAttachments.map((f, i) => (
              <li key={i} className="flex items-center justify-between text-sm text-gray-600 bg-gray-50 rounded-lg px-4 py-2.5">
                <span className="truncate">{f.name}</span>
                <button
                  type="button"
                  onClick={() => setEmailAttachments((prev) => prev.filter((_, idx) => idx !== i))}
                  className="text-gray-400 hover:text-red-500 ml-2 shrink-0"
                >
                  <Trash2 size={16} />
                </button>
              </li>
            ))}
          </ul>
        )}
        {taskStatus?.submission?.docx_file_path && (
          <p className="text-sm text-gray-400 mt-2">已自动附加生成的行程文档</p>
        )}
      </div>
      <button
        onClick={handleSendEmail}
        disabled={!emailTo.trim() || emailSent}
        className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 text-base font-medium"
      >
        {emailSent ? '已发送' : '发送邮件'}
      </button>
    </div>
  )

  const completedCount = [searchResults.length > 0, docGenerated, reminderSet, emailSent].filter(Boolean).length

  return (
    <div className="task-page h-screen bg-[#f4f8fd] flex overflow-hidden">
      <style>{`
        .editor-toolbar { display: flex; flex-wrap: wrap; gap: 4px; padding: 6px 8px;
          border: 1px solid #d0d4dc; border-bottom: none; background: #f9f9fb; border-radius: 3px 3px 0 0; }
        .editor-toolbar .tb-btn { display: inline-flex; align-items: center; justify-content: center;
          width: 30px; height: 28px; border: 1px solid #d0d4dc; background: #fff; border-radius: 3px;
          cursor: pointer; font-size: 13px; color: #444; transition: all .15s; user-select: none; }
        .editor-toolbar .tb-btn:hover { background: #e8f0fe; border-color: #2f7cf6; }
        .editor-toolbar .tb-sep { width: 1px; height: 20px; background: #d0d4dc; margin: 4px 2px; }
        .doc-editor { min-height: 0; padding: 12px 14px; border: 1px solid #d0d4dc;
          border-radius: 0 0 3px 3px; font-size: 14px; line-height: 1.8; outline: none;
          overflow-y: auto; background: #fff; }
        .doc-editor:focus { border-color: #2f7cf6; }
        .doc-editor:empty::before { content: attr(data-placeholder); color: #b6bcc8; pointer-events: none; }
        .doc-editor h1, .doc-editor h2, .doc-editor h3 { margin: 10px 0 6px; }
        .doc-editor ul, .doc-editor ol { margin: 6px 0 6px 24px; }
        .doc-editor table { border-collapse: collapse; width: 100%; margin: 8px 0; }
        .doc-editor td, .doc-editor th { border: 1px solid #ccc; padding: 6px 10px; }
        .save-tip { font-size: 12px; color: #28a745; margin-left: 8px; opacity: 0; transition: opacity .3s; }
        .save-tip.show { opacity: 1; }

        /* ===== 白蓝设计系统（参照 travel-planner-ui.html） ===== */
        .task-page {
          --tp-ink:#16263d; --tp-text2:#5a7088; --tp-text3:#94a6ba;
          --tp-border:#e2ecf5; --tp-fill:#eef4fb;
          --tp-blue:#2577e3; --tp-blue-600:#1a63c9; --tp-blue-300:#5a9bf0; --tp-blue-200:#8fc0f7;
          --tp-bg:#f4f8fd;
        }
        .task-page { background: var(--tp-bg); }
        .task-page .bg-blue-600 { background-color: var(--tp-blue); }
        .task-page .text-blue-600 { color: var(--tp-blue); }
        .task-page .bg-blue-50 { background-color: var(--tp-fill); }
        .task-page .border-blue-200 { border-color: var(--tp-blue-200); }
        .task-page .bg-gray-50 { background-color: var(--tp-fill); }
        .task-page .bg-gray-100 { background-color: var(--tp-fill); }
        .task-page .text-gray-900 { color: var(--tp-ink); }
        .task-page .text-gray-500 { color: var(--tp-text2); }
        .task-page .text-gray-400 { color: var(--tp-text3); }
        .task-page .text-gray-600 { color: var(--tp-text2); }
        .task-page .border-gray-100 { border-color: var(--tp-border); }
        .task-page .border-gray-200 { border-color: var(--tp-border); }
        .task-page .shadow-sm { box-shadow: 0 1px 3px rgba(22,38,61,.06); }
        .task-page .hover\:bg-blue-700:hover { background-color: var(--tp-blue-600); }
        .task-page .hover\:text-blue-600:hover { color: var(--tp-blue); }
        .task-page .hover\:border-blue-300:hover { border-color: var(--tp-blue-300); }
        .task-page .focus\:ring-blue-500:focus { --tw-ring-color: var(--tp-blue); }
        .tp-section-title { display: flex; align-items: center; gap: 8px; }
        .tp-section-title::before { content: ''; width: 4px; height: 16px; border-radius: 4px; background: var(--tp-blue); display: inline-block; }
        .tp-eyebrow { font-size: 11px; color: var(--tp-blue-600); letter-spacing: 1px; display: inline-flex; align-items: center; gap: 5px; background: var(--tp-fill); padding: 4px 11px; border-radius: 20px; }
        .tp-ghost { border: 1px solid var(--tp-border); background: #fff; color: var(--tp-text2); border-radius: 12px; transition: all .15s; }
        .tp-ghost:hover { border-color: var(--tp-blue); color: var(--tp-blue); }
      `}</style>
      {/* 左侧边栏：AI助手 / 搜索引擎 */}
      <aside className="w-[480px] lg:w-[560px] bg-white border-r border-gray-100 flex flex-col shrink-0">
        <div className="h-14 border-b border-gray-100 flex items-center px-1 shrink-0">
          {showAI && (
            <button
              onClick={() => setLeftTab('ai')}
              className={`relative px-5 h-14 text-lg font-medium transition ${
                leftTab === 'ai'
                  ? 'text-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <Sparkles size={17} /> AI助手
              </span>
              {leftTab === 'ai' && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />
              )}
            </button>
          )}
          <button
            onClick={() => setLeftTab('search')}
              className={`relative px-5 h-14 text-lg font-medium transition ${
                leftTab === 'search'
                  ? 'text-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <Search size={17} /> 搜索引擎
            </span>
            {leftTab === 'search' && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />
            )}
          </button>
        </div>

        <div className="flex-1 overflow-hidden bg-white">
          {leftTab === 'ai' && showAI ? (
            isMOA ? (
              <div className="h-full flex flex-col">
                {/* 顶部双 AI 助理切换 */}
                <div className="flex shrink-0 border-b border-gray-100 bg-white">
                  {([
                    { id: 'moa_a', title: '信息检索专员', color: 'blue' },
                    { id: 'moa_b', title: '行程编排专员', color: 'green' },
                  ] as const).map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setMoaAgent(t.id)}
                      className={`relative flex-1 h-12 text-sm font-medium transition ${
                        moaAgent === t.id
                          ? 'text-blue-600 bg-blue-50'
                          : 'text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      <span className="flex items-center justify-center gap-1.5">
                        <Sparkles size={14} /> {t.title}
                      </span>
                      {moaAgent === t.id && (
                        <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />
                      )}
                    </button>
                  ))}
                </div>
                {/* 当前助理窗口：高度拉满剩余页面 */}
                <div className="flex-1 min-h-0">
                  <ChatWindow agentId={moaAgent} className="h-full" />
                </div>
              </div>
            ) : (
              <ChatWindow agentId="soa" className="h-full" />
            )
          ) : (
            <div className="h-full p-4 flex flex-col">
              {renderSearchEngine()}
            </div>
          )}
        </div>
      </aside>

      {/* 右侧行程详情 */}
      <main className="flex-1 flex flex-col overflow-hidden bg-[#f4f8fd]">
        {/* 顶部标题栏 */}
        <header className="h-[72px] px-6 bg-white border-b border-gray-100 flex items-center justify-between shrink-0">
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-6 rounded bg-[#2577e3]" />
              <h1 className="text-2xl font-bold text-gray-900">行程详情</h1>
            </div>
            {user?.email && (
              <span className="text-xs text-gray-400 ml-3.5">
                当前账号：<span className="font-mono text-gray-500">{user.email}</span>
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-5 py-2.5 bg-gray-50 rounded-full text-gray-500">
              <Clock size={17} className="text-gray-400" />
              <span className="font-mono font-semibold text-gray-900 text-lg">{formatted}</span>
            </div>
            <span className="flex items-center gap-1 text-base text-gray-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400" /> 自动保存
            </span>
            <button
              onClick={handleSubmit}
              disabled={!allDone || submitting}
              className="px-7 py-2.5 bg-blue-600 text-white text-lg font-medium rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:hover:bg-blue-600 transition shadow-sm"
            >
              {submitting ? '提交中...' : '提交'}
            </button>
          </div>
        </header>

        {/* 当前子任务内容 */}
        <div className="flex-1 overflow-y-auto">
          <div className="h-full p-4 space-y-3 flex flex-col">
            {/* 总进度（任务卡上方，常驻显示） */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 shrink-0">
              <h3 className="tp-section-title text-lg font-bold text-gray-900 mb-4">任务进度</h3>
              <div className="grid grid-cols-4 gap-3">
                {taskProgress.map((t) => {
                  const active = activeSubTab === t.subTab
                  return (
                    <button
                      key={t.key}
                      onClick={() => setActiveSubTab(t.subTab)}
                      className="flex flex-col items-center gap-2 text-center px-1 group cursor-pointer"
                    >
                      <div className={`w-12 h-12 rounded-full flex items-center justify-center transition ${active ? 'bg-blue-600 text-white ring-2 ring-blue-300 ring-offset-2' : t.done ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-400 group-hover:bg-gray-200'}`}>
                        {t.done ? <CheckCircle2 size={22} /> : <t.icon size={22} />}
                      </div>
                      <p className={`text-sm font-medium leading-tight transition ${active ? 'text-blue-600' : t.done ? 'text-gray-900' : 'text-gray-500'}`}>{t.label}</p>
                    </button>
                  )
                })}
              </div>
              <div className="mt-5 pt-4 border-t border-gray-100">
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-sm text-gray-500">总进度</span>
                  <span className="text-sm font-bold text-gray-900">{completedCount}/4</span>
                </div>
                <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-600 transition-all" style={{ width: `${(completedCount / 4) * 100}%` }} />
                </div>
              </div>
            </div>

            {/* 任务卡 */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex-1 min-h-0 flex flex-col">
              <div className="flex-1">
                {activeSubTab === 'overview' && renderOverview()}
                {activeSubTab === 'doc' && renderDoc()}
                {activeSubTab === 'reminder' && renderReminder()}
                {activeSubTab === 'email' && renderEmail()}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
