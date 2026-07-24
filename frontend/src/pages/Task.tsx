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
  Layout, Plus, MapPin, Luggage, CalendarDays, ChevronRight, Trash2,
  MoreHorizontal, Maximize2, Check
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import ChatWindow from '../components/ChatWindow'

type SubTabKey = 'overview' | 'search' | 'doc' | 'reminder' | 'email'

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
      if (typeof d.activeSubTab === 'string') setActiveSubTab(d.activeSubTab)
    } catch {
      // 草稿损坏则忽略
    }
  }, [draftKey])

  useEffect(() => {
    if (!draftKey) return
    const draft = {
      searchQuery, searchResults, docContent, docGenerated,
      reminderDate, reminderContent, reminderSet, emailSent, emailTo,
      activeSubTab,
    }
    localStorage.setItem(draftKey, JSON.stringify(draft))
  }, [draftKey, searchQuery, searchResults, docContent, docGenerated, reminderDate, reminderContent, reminderSet, emailSent, emailTo, activeSubTab])

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
    logPlanEdit({ manualEditCount: editCountRef.current, contentSnippet: docContent.substring(0, 100) })
    try {
      const res = await documentApi.generate(planTitle, docContent)
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
      logPlanSubmit({ finalPlanText: docContent })
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
    { key: 'search', label: '搜索景点', icon: Search, done: searchResults.length > 0 },
    { key: 'doc', label: '生成文档', icon: FileText, done: docGenerated },
    { key: 'reminder', label: '设置提醒', icon: Bell, done: reminderSet },
    { key: 'email', label: '发送邮件', icon: Mail, done: emailSent },
  ]

  const aiSteps = [
    { label: '了解你的需求', done: true },
    { label: '查找目的地信息', done: true },
    {
      label: activeSubTab === 'search' ? '查询热门景点'
        : activeSubTab === 'doc' ? '生成行程文档'
        : activeSubTab === 'reminder' ? '设置旅行提醒'
        : activeSubTab === 'email' ? '发送行程邮件'
        : '协助完成行程规划',
      done: false,
    },
  ]

  const renderOverview = () => (
    <div className="grid gap-4">
      <p className="text-sm text-gray-500">点击标签页可快速切换到对应子任务。</p>
      <div className="grid sm:grid-cols-2 gap-4">
        {subTabs.filter(t => t.key !== 'overview').map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveSubTab(t.key)}
            className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm hover:shadow-md transition text-left flex items-center gap-4"
          >
            <span className={`w-11 h-11 rounded-full flex items-center justify-center shrink-0 ${t.done ? 'bg-black text-white' : 'bg-blue-50 text-blue-600'}`}>
              <t.icon size={20} />
            </span>
            <div className="flex-1">
              <h4 className="font-semibold text-gray-800">{t.label}</h4>
              <p className="text-xs text-gray-500 mt-0.5">{t.done ? '已完成' : '点击开始'}</p>
            </div>
            <ChevronRight size={18} className="text-gray-300" />
          </button>
        ))}
      </div>
    </div>
  )

  const renderSearch = () => (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="w-10 h-10 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center">
          <MapPin size={20} />
        </span>
        <div>
          <h4 className="font-semibold text-gray-900">搜索景点</h4>
          <p className="text-xs text-gray-500">输入关键词查找 {dest} 景点信息</p>
        </div>
      </div>
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
        <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
          {searchResults.map((r, i) => (
            <div
              key={i}
              onClick={() => log({ action_type: 'search_result_click', action_target: r.title })}
              className="p-4 bg-gray-50 rounded-xl hover:bg-blue-50 cursor-pointer transition"
            >
              <h4 className="text-sm font-semibold text-blue-600">{r.title}</h4>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">{r.snippet}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400">暂无结果</p>
      )}
    </div>
  )

  const renderDoc = () => (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="w-10 h-10 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center">
          <Luggage size={20} />
        </span>
        <div>
          <h4 className="font-semibold text-gray-900">生成行程文档</h4>
          <p className="text-xs text-gray-500">将规划内容导出为 Word 文档</p>
        </div>
      </div>
      <textarea
        value={docContent}
        onChange={(e) => { setDocContent(e.target.value); editCountRef.current += 1 }}
        className="w-full h-40 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-mono leading-relaxed"
        placeholder={`在此输入行程规划内容...\n例如：\n# ${planTitle}\n## 第一天\n- 上午：西湖风景区\n- 下午：灵隐寺`}
      />
      <div className="flex gap-2">
        <button
          onClick={handleGenerateDoc}
          disabled={!docContent.trim()}
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
      {/* 左侧 AI 助手 —— 仅 SOA/MOA */}
      {showAI && (
        <aside className="w-[400px] lg:w-[440px] bg-white border-r border-gray-100 flex flex-col shrink-0">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <Sparkles size={18} className="text-blue-600" />
              <h2 className="font-bold text-lg text-gray-900">AI 助手</h2>
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <MoreHorizontal size={18} />
              <Maximize2 size={16} />
            </div>
          </div>

          <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 shrink-0">
            <div className="space-y-3">
              {aiSteps.map((s, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                    s.done ? 'bg-blue-600 text-white' : 'border-2 border-blue-600 text-blue-600'
                  }`}>
                    {s.done ? <Check size={12} /> : i + 1}
                  </div>
                  <span className={`text-sm ${s.done ? 'text-gray-900 font-medium' : 'text-blue-600 font-medium'}`}>
                    {s.label}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-hidden">
            {isMOA ? (
              <div className="h-full overflow-y-auto p-3 space-y-3">
                <MOAAgentPanel agentId="moa_a" title="信息检索专员" color="blue" />
                <MOAAgentPanel agentId="moa_b" title="行程编排专员" color="green" />
                <MOAAgentPanel agentId="moa_c" title="事务处理专员" color="purple" />
              </div>
            ) : (
              <ChatWindow agentId="soa" className="h-full" />
            )}
          </div>
        </aside>
      )}

      {/* 右侧行程详情 */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto p-6 pb-24">
          {/* 顶部标题栏 */}
          <div className="flex items-center justify-between mb-5">
            <div>
              <h1 className="text-xl font-bold text-gray-900">行程详情</h1>
              <p className="text-xs text-gray-500 mt-0.5">完成四项子任务以提交任务</p>
            </div>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5 text-xs text-gray-400">
                <Clock size={14} /> 用时
              </span>
              <span className="font-mono text-base font-semibold text-blue-600">{formatted}</span>
              <span className="flex items-center gap-1 text-xs text-gray-400" title="任务进度自动保存在本机">
                <CheckCircle2 size={13} /> 自动保存
              </span>
            </div>
          </div>

          {/* 任务指令 */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 mb-5">
            <div className="flex items-start gap-4">
              <span className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0">
                <Target size={20} />
              </span>
              <div className="flex-1">
                <h2 className="font-bold text-lg text-gray-900 mb-1">
                  任务：规划 {dest}{days}日游，预算 <span className="text-blue-600">{budget} 元</span>
                </h2>
                <p className="text-sm text-gray-500">
                  请完成以下 4 项子任务，完成后点击底部提交。
                </p>
              </div>
            </div>
          </div>

          {/* 子任务标签 */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 mb-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
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
              <button
                className="w-9 h-9 rounded-full bg-blue-600 text-white flex items-center justify-center hover:bg-blue-700 shrink-0 ml-3"
                title="快速新建"
                onClick={() => setActiveSubTab('search')}
              >
                <Plus size={18} />
              </button>
            </div>
          </div>

          {/* 当前子任务内容 */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-4">
            {activeSubTab === 'overview' && renderOverview()}
            {activeSubTab === 'search' && renderSearch()}
            {activeSubTab === 'doc' && renderDoc()}
            {activeSubTab === 'reminder' && renderReminder()}
            {activeSubTab === 'email' && renderEmail()}
          </div>

          {/* 提交按钮 */}
          <button
            onClick={handleSubmit}
            disabled={!allDone || submitting}
            className="w-full py-3.5 bg-black text-white rounded-2xl font-medium hover:bg-gray-800 disabled:opacity-40 disabled:hover:bg-black transition"
          >
            {submitting ? '提交中...' : allDone ? '提交任务' : '完成所有子任务后可提交'}
          </button>

          {/* 进度总览 */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 mt-4">
            <h3 className="font-bold text-gray-900 mb-4">任务进度</h3>
            <div className="space-y-3">
              {subTabs.filter(t => t.key !== 'overview').map((t) => (
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
