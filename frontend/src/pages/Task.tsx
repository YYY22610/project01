import { useEffect, useState, useRef, Fragment } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../stores/userStore'
import { useBehaviorLogger } from '../hooks/useBehaviorLogger'
import { useTimer } from '../hooks/useTimer'
import { useAgentChat } from '../hooks/useAgentChat'
import { searchApi, documentApi, reminderApi, emailApi } from '../services'
import type { SearchResult } from '../types'
import {
  Search, Mail, Bell, FileText, Target, Sparkles, CheckCircle2, Clock,
  Layout, MapPin, Luggage, CalendarDays, Trash2, ExternalLink
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
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
  const [leftTab, setLeftTab] = useState<LeftTabKey>('search')

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

  const [showAI, setShowAI] = useState(false)
  const [isMOA, setIsMOA] = useState(false)
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
      activeSubTab,
    }
    localStorage.setItem(draftKey, JSON.stringify(draft))
  }, [draftKey, searchQuery, searchResults, docContent, docGenerated, reminderDate, reminderContent, reminderSet, emailSent, emailTo, activeSubTab])

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
      alert(`文档已生成: ${res.data.file_name}`)
    } catch (e) {
      alert('文档生成失败')
    }
  }

  const handleDownload = async () => {
    if (taskStatus?.submission?.docx_file_path) {
      const fileName = taskStatus.submission.docx_file_path.split('\\').pop()?.split('/').pop()
      if (fileName) {
        try {
          await documentApi.download(fileName)
          log({ action_type: 'document_download', action_target: fileName })
        } catch (e) {
          alert('下载失败，请稍后重试')
        }
      }
    } else {
      alert('文档尚未生成，请先生成 Word 文档')
    }
  }

  const handleSetReminder = async () => {
    if (!reminderDate) return
    log({ action_type: 'reminder_set', action_target: reminderDate })
    try {
      await reminderApi.set(reminderDate, reminderContent)
      setReminderSet(true)
      log({ action_type: 'reminder_set', action_target: reminderDate })
    } catch (e) {
      alert('设置提醒失败')
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
        task1_search: searchResults.length > 0,
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

  const allDone = searchResults.length > 0 && docGenerated && reminderSet && emailSent

  const subTabs: { key: SubTabKey; label: string; icon: LucideIcon; done: boolean }[] = [
    { key: 'overview', label: '总览', icon: Layout, done: allDone },
    { key: 'doc', label: '生成文档', icon: FileText, done: docGenerated },
    { key: 'reminder', label: '设置提醒', icon: Bell, done: reminderSet },
    { key: 'email', label: '发送邮件', icon: Mail, done: emailSent },
  ]

  const taskProgress = [
    { key: 'search', label: '搜索景点', icon: Search, done: searchResults.length > 0 },
    { key: 'doc', label: '生成文档', icon: FileText, done: docGenerated },
    { key: 'reminder', label: '设置提醒', icon: Bell, done: reminderSet },
    { key: 'email', label: '发送邮件', icon: Mail, done: emailSent },
  ]

  const renderOverview = () => (
    <div className="space-y-6">
      {/* 任务指令 */}
      <div className="flex items-start gap-4">
        <span className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0">
          <Target size={20} />
        </span>
        <div className="flex-1">
          <h2 className="font-bold text-lg text-gray-900 mb-1">
            任务：规划 {dest}{days}日游，预算 <span className="text-blue-600">{budget} 元</span>
          </h2>
          <p className="text-sm text-gray-500">
            请完成左侧「搜索引擎」及下方 3 项子任务，完成后点击右上角「提交」。
          </p>
        </div>
      </div>

      {/* 进度总览 */}
      <div>
        <h3 className="font-bold text-gray-900 mb-4">任务进度</h3>
        <div className="space-y-3">
          {taskProgress.map((t) => (
            <div key={t.key} className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs ${t.done ? 'bg-black text-white' : 'bg-gray-100 text-gray-400'}`}>
                {t.done ? <CheckCircle2 size={14} /> : <t.icon size={14} />}
              </div>
              <div className="flex-1">
                <p className={`text-sm font-medium ${t.done ? 'text-gray-900' : 'text-gray-500'}`}>{t.label}</p>
              </div>
              {t.done && <span className="text-xs text-gray-400">完成</span>}
            </div>
          ))}
        </div>
        <div className="mt-5 pt-4 border-t border-gray-100">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs text-gray-500">总进度</span>
            <span className="text-xs font-bold text-gray-900">{completedCount}/4</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-blue-600 transition-all" style={{ width: `${(completedCount / 4) * 100}%` }} />
          </div>
        </div>
      </div>
    </div>
  )

  // 搜索引擎：接入 DuckDuckGo + Bing 实时搜索
  const renderSearchEngine = () => (
    <div className="border border-gray-200 rounded-2xl overflow-hidden bg-white">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-700">搜索引擎</span>
        <span className="text-xs text-gray-400">DuckDuckGo · Bing</span>
      </div>
      <div className="p-4 space-y-3">
        <div className="flex gap-2">
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
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {searchResults.map((r, i) => (
              <a
                key={i}
                href={r.url || undefined}
                target={r.url ? '_blank' : undefined}
                rel="noopener noreferrer"
                onClick={() => log({ action_type: 'search_result_click', action_target: r.title })}
                className="block p-4 bg-gray-50 rounded-xl hover:bg-blue-50 transition"
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
          <p className="text-sm text-gray-400">暂无结果，输入关键词后点击搜索</p>
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
  const handleSaveLocal = () => {
    const content = editorRef.current?.innerHTML.trim() ?? ''
    if (!content || content === '<br>' || content === '<div><br></div>') {
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
      "</style>\n</head>\n<body>\n" + content + "\n</body>\n</html>"
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
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="w-10 h-10 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center">
          <Luggage size={20} />
        </span>
        <div>
          <h4 className="font-semibold text-gray-900">生成行程文档</h4>
          <p className="text-xs text-gray-500">在下方编辑器中整理行程，可导出为 Word 文档</p>
        </div>
      </div>

      {/* 富文本编辑器（仿 aitravel 内置文本编辑器） */}
      <div>
        <div className="editor-toolbar">
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
          <button type="button" className="tb-btn tb-save" onMouseDown={(e) => e.preventDefault()} onClick={handleSaveLocal}>保存到本地</button>
        </div>
        <span className={`save-tip ${saveTipShown ? 'show' : ''}`}>已保存</span>
        <div
          ref={editorRef}
          className="doc-editor"
          contentEditable
          suppressContentEditableWarning
          data-placeholder="请在此处整理您的行程规划内容…"
          onInput={handleEditorInput}
        />
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleGenerateDoc}
          disabled={!docContent.trim() || docContent === '<br>'}
          className="px-5 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
        >
          生成 Word
        </button>
        {docGenerated && (
          <button onClick={handleDownload} className="px-4 py-2.5 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 text-sm">
            下载文档
          </button>
        )}
      </div>
    </div>
  )

  const renderReminder = () => (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="w-10 h-10 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center">
          <CalendarDays size={20} />
        </span>
        <div>
          <h4 className="font-semibold text-gray-900">设置旅行提醒</h4>
          <p className="text-xs text-gray-500">设定提醒时间和内容</p>
        </div>
      </div>
      <input
        type="datetime-local"
        value={reminderDate}
        onChange={(e) => setReminderDate(e.target.value)}
        className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
      />
      <input
        type="text"
        value={reminderContent}
        onChange={(e) => setReminderContent(e.target.value)}
        className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        placeholder="提醒内容（如：出发前往杭州）"
      />
      <button
        onClick={handleSetReminder}
        disabled={!reminderDate || reminderSet}
        className="px-5 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
      >
        {reminderSet ? '已设置' : '设置提醒'}
      </button>
    </div>
  )

  const renderEmail = () => (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="w-10 h-10 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center">
          <Mail size={20} />
        </span>
        <div>
          <h4 className="font-semibold text-gray-900">发送行程邮件</h4>
          <p className="text-xs text-gray-500">将行程文档发送给指定收件人</p>
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">收件人</label>
        <input
          type="email"
          value={emailTo}
          onChange={(e) => setEmailTo(e.target.value)}
          className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          placeholder="收件人邮箱"
        />
        <p className="text-xs text-gray-400 mt-1">默认使用注册邮箱，可修改</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">附件（可选）</label>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={(e) => {
            const picked = e.target.files ? Array.from(e.target.files) : []
            if (picked.length) setEmailAttachments((prev) => [...prev, ...picked])
            e.target.value = ''
          }}
          className="block w-full text-sm text-gray-500 file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:bg-blue-50 file:text-blue-600 hover:file:bg-blue-100"
        />
        {emailAttachments.length > 0 && (
          <ul className="mt-2 space-y-1.5">
            {emailAttachments.map((f, i) => (
              <li key={i} className="flex items-center justify-between text-xs text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
                <span className="truncate">{f.name}</span>
                <button
                  type="button"
                  onClick={() => setEmailAttachments((prev) => prev.filter((_, idx) => idx !== i))}
                  className="text-gray-400 hover:text-red-500 ml-2 shrink-0"
                >
                  <Trash2 size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}
        {taskStatus?.submission?.docx_file_path && (
          <p className="text-xs text-gray-400 mt-1">已自动附加生成的行程文档</p>
        )}
      </div>
      <button
        onClick={handleSendEmail}
        disabled={!emailTo.trim() || emailSent}
        className="px-5 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
      >
        {emailSent ? '已发送' : '发送邮件'}
      </button>
    </div>
  )

  const completedCount = [searchResults.length > 0, docGenerated, reminderSet, emailSent].filter(Boolean).length

  return (
    <div className="h-screen bg-[#f7f8fa] flex overflow-hidden">
      <style>{`
        .editor-toolbar { display: flex; flex-wrap: wrap; gap: 4px; padding: 6px 8px;
          border: 1px solid #d0d4dc; border-bottom: none; background: #f9f9fb; border-radius: 3px 3px 0 0; }
        .editor-toolbar .tb-btn { display: inline-flex; align-items: center; justify-content: center;
          width: 30px; height: 28px; border: 1px solid #d0d4dc; background: #fff; border-radius: 3px;
          cursor: pointer; font-size: 13px; color: #444; transition: all .15s; user-select: none; }
        .editor-toolbar .tb-btn:hover { background: #e8f0fe; border-color: #2f7cf6; }
        .editor-toolbar .tb-sep { width: 1px; height: 20px; background: #d0d4dc; margin: 4px 2px; }
        .editor-toolbar .tb-save { width: auto; padding: 0 12px; background: #28a745; color: #fff;
          border-color: #28a745; font-weight: 500; margin-left: auto; }
        .editor-toolbar .tb-save:hover { background: #218838; border-color: #218838; }
        .doc-editor { min-height: 340px; padding: 14px 16px; border: 1px solid #d0d4dc;
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
      `}</style>
      {/* 左侧边栏：AI助手 / 搜索引擎 */}
      <aside className="w-[400px] lg:w-[440px] bg-white border-r border-gray-100 flex flex-col shrink-0">
        <div className="h-14 border-b border-gray-100 flex items-center px-1 shrink-0">
          {showAI && (
            <button
              onClick={() => setLeftTab('ai')}
              className={`relative px-5 h-14 text-sm font-medium transition ${
                leftTab === 'ai'
                  ? 'text-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <Sparkles size={15} /> AI助手
              </span>
              {leftTab === 'ai' && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />
              )}
            </button>
          )}
          <button
            onClick={() => setLeftTab('search')}
            className={`relative px-5 h-14 text-sm font-medium transition ${
              leftTab === 'search'
                ? 'text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <span className="flex items-center gap-1.5">
              <Search size={15} /> 搜索引擎
            </span>
            {leftTab === 'search' && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />
            )}
          </button>
        </div>

        <div className="flex-1 overflow-hidden bg-[#f7f8fa]">
          {leftTab === 'ai' && showAI ? (
            isMOA ? (
              <div className="h-full overflow-y-auto p-3 space-y-3">
                <MOAAgentPanel agentId="moa_a" title="信息检索专员" color="blue" />
                <MOAAgentPanel agentId="moa_b" title="行程编排专员" color="green" />
                <MOAAgentPanel agentId="moa_c" title="事务处理专员" color="purple" />
              </div>
            ) : (
              <ChatWindow agentId="soa" className="h-full" />
            )
          ) : (
            <div className="h-full overflow-y-auto p-4">
              {renderSearchEngine()}
            </div>
          )}
        </div>
      </aside>

      {/* 右侧行程详情 */}
      <main className="flex-1 flex flex-col overflow-hidden bg-[#f7f8fa]">
        {/* 顶部标题栏 */}
        <header className="h-14 px-6 bg-white border-b border-gray-100 flex items-center justify-between shrink-0">
          <div>
            <h1 className="text-lg font-bold text-gray-900">行程详情</h1>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Clock size={14} />
              <span className="font-mono font-semibold text-gray-900">{formatted}</span>
              <span className="text-xs text-gray-400 ml-1">自动保存</span>
            </div>
            <button
              onClick={handleSubmit}
              disabled={!allDone || submitting}
              className="px-5 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:hover:bg-blue-600 transition"
            >
              {submitting ? '提交中...' : '提交'}
            </button>
          </div>
        </header>

        {/* 子任务标签 */}
        <div className="px-6 py-3 bg-white border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2 overflow-x-auto">
            {subTabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setActiveSubTab(t.key)}
                className={`shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium transition border ${
                  activeSubTab === t.key
                    ? 'bg-black text-white border-black'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
                }`}
              >
                {t.done && activeSubTab !== t.key ? <CheckCircle2 size={14} /> : <t.icon size={14} />}
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* 当前子任务内容 */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto p-6">
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              {activeSubTab === 'overview' && renderOverview()}
              {activeSubTab === 'doc' && renderDoc()}
              {activeSubTab === 'reminder' && renderReminder()}
              {activeSubTab === 'email' && renderEmail()}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

function MOAAgentPanel({ agentId, title, color }: { agentId: string; title: string; color: string }) {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-600', green: 'bg-emerald-600', purple: 'bg-purple-600',
  }
  return (
    <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
      <div className={`${colorMap[color]} text-white px-4 py-2 flex items-center gap-2`}>
        <Sparkles size={14} /> <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <ChatWindow agentId={agentId} className="h-[260px]" />
    </div>
  )
}
