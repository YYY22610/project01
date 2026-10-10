import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../stores/userStore'

// 10 题选项（与后端 schemas.auth.PreSurveySubmission 字段值一一对应）
const OPTIONS = {
  q1: [
    { value: 'yes', label: '是' },
    { value: 'no', label: '否' },
  ],
  q2: [
    { value: 'domestic', label: '具备国内旅行经验' },
    { value: 'abroad', label: '具备国外旅行经验' },
    { value: 'both', label: '同时具备国内外旅行经验' },
    { value: 'never', label: '从未旅行过' },
  ],
  q3: [
    { value: 'never', label: '从不使用' },
    { value: 'rarely', label: '不常使用（每月 1-2 次）' },
    { value: 'sometimes', label: '偶尔使用（每周 1-3 次）' },
    { value: 'often', label: '频繁使用（每周 4-6 次）' },
    { value: 'daily', label: '几乎每天使用（每周 ≥ 7 次）' },
  ],
  q4: [
    { value: 'agent_principle', label: '我了解人工智能智能体（AI Agent）的基本工作原理' },
    { value: 'agent_openclaw', label: '我了解或听说过 OpenClaw、ArkClaw 等"龙虾"系列 AI 智能体' },
    { value: 'agent_built', label: '我尝试过在智能体平台搭建智能体（Dify、Coze、Zapier、n8n 等）' },
    { value: 'agent_deployed', label: '我尝试过部署或配置智能体助理（如 Workbuddy、飞书 x claw、腾讯 QClaw、字节 ArkClaw、kimiclaw 等）' },
    { value: 'agent_helpful', label: '我认为智能体助理能够辅助完成旅游规划类任务' },
    { value: 'none', label: '以上均不认同' },
  ],
  q5: [
    { value: 'lt_1m', label: '少于 1 个月' },
    { value: 'm_1_3', label: '1-3 个月' },
    { value: 'm_3_6', label: '3-6 个月' },
    { value: 'gte_6m', label: '6 个月以上' },
  ],
  q6: [
    { value: 'male', label: '男' },
    { value: 'female', label: '女' },
  ],
  q7: [
    { value: '18-24', label: '18-24 岁' },
    { value: '25-34', label: '25-34 岁' },
    { value: '35-44', label: '35-44 岁' },
    { value: '45-54', label: '45-54 岁' },
    { value: '55-64', label: '55-64 岁' },
    { value: '65+', label: '65 岁以上' },
  ],
  q8: [
    { value: 'high_school', label: '高中及以下' },
    { value: 'bachelor', label: '大学本科' },
    { value: 'master', label: '硕士研究生' },
    { value: 'phd', label: '博士研究生' },
  ],
  q9: [
    { value: 'married', label: '已婚' },
    { value: 'unmarried', label: '未婚' },
  ],
  q10: [
    { value: 'student', label: '学生' },
    { value: 'full_time', label: '全职在职' },
    { value: 'part_time', label: '兼职实习' },
    { value: 'freelance', label: '自由职业' },
    { value: 'unemployed', label: '失业待业' },
    { value: 'retired', label: '退休' },
    { value: 'other', label: '其他' },
  ],
} as const

type Survey = {
  q1: string
  q2: string
  q3: string
  q4: string[]
  q5: string
  q6: string
  q7: string
  q8: string
  q9: string
  q10: string
}

const empty: Survey = { q1: '', q2: '', q3: '', q4: [], q5: '', q6: '', q7: '', q8: '', q9: '', q10: '' }

// 题目列表（统一驱动渲染）
const QUESTIONS: { key: keyof Survey; title: string; type: 'single' | 'multi'; required: boolean }[] = [
  { key: 'q1', title: 'A1 您是否使用过生成式人工智能（如 ChatGPT、DeepSeek、豆包、千问、Kimi 等）？', type: 'single', required: true },
  { key: 'q2', title: 'A2 您是否具备国内外旅行经验？', type: 'single', required: true },
  { key: 'q3', title: 'A3 在过去 6 个月中，您使用大语言模型（如 ChatGPT、DeepSeek、Kimi、文心一言等）的频率是？', type: 'single', required: true },
  { key: 'q4', title: 'A4 您对以下哪些陈述表示认同？（可多选）', type: 'multi', required: true },
  { key: 'q5', title: 'A5 您使用大语言模型的时长大约是？', type: 'single', required: true },
  { key: 'q6', title: 'A1 您的性别为', type: 'single', required: true },
  { key: 'q7', title: 'A2 您的年龄是', type: 'single', required: true },
  { key: 'q8', title: 'A3 您的最高学历是', type: 'single', required: true },
  { key: 'q9', title: 'A4 您的婚姻状况是', type: 'single', required: true },
  { key: 'q10', title: 'A5 您目前从事的职业', type: 'single', required: true },
]

export default function Consent() {
  const [agreed, setAgreed] = useState(false)
  const [survey, setSurvey] = useState<Survey>(empty)
  const [error, setError] = useState('')
  const { consent, loading } = useUserStore()
  const navigate = useNavigate()

  const setSingle = (k: keyof Survey, v: string) => setSurvey((s) => ({ ...s, [k]: v }))

  const toggleMulti = (k: keyof Survey, v: string) => {
    setSurvey((s) => {
      const cur = (s[k] as unknown as string[]) || []
      if (v === 'none') {
        // 选「以上均不认同」时清空其他；再次点击则取消
        return { ...s, [k]: cur.includes('none') ? [] : ['none'] }
      }
      // 非 none：先把 none 去掉，再切换当前项
      const withoutNone = cur.filter((x) => x !== 'none')
      return {
        ...s,
        [k]: withoutNone.includes(v) ? withoutNone.filter((x) => x !== v) : [...withoutNone, v],
      }
    })
  }

  const validate = (): string | null => {
    if (!agreed) return '请先勾选「我已阅读并同意」'
    for (const q of QUESTIONS) {
      if (!q.required) continue
      if (q.type === 'single' && !(survey[q.key] as string)) {
        return `请完成第 ${QUESTIONS.indexOf(q) + 1} 题`
      }
      if (q.type === 'multi' && (survey[q.key] as string[]).length === 0) {
        return `请完成第 ${QUESTIONS.indexOf(q) + 1} 题`
      }
    }
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    const msg = validate()
    if (msg) {
      setError(msg)
      // 滚动到第一个未答题
      window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
      return
    }
    try {
      await consent(true, survey)
      navigate('/demo')
    } catch (e: any) {
      setError(e.response?.data?.detail || '操作失败')
    }
  }

  const renderOption = (qKey: keyof Survey, optValue: string, optLabel: string, type: 'single' | 'multi') => {
    const checked =
      type === 'single'
        ? survey[qKey] === optValue
        : (survey[qKey] as unknown as string[]).includes(optValue)
    const inputId = `${qKey}-${optValue}`
    return (
      <label
        key={optValue}
        htmlFor={inputId}
        className={`flex items-start gap-2 px-3 py-2.5 rounded-lg border cursor-pointer transition text-sm leading-relaxed ${
          checked
            ? 'border-blue-500 bg-blue-50 text-blue-900'
            : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/40'
        }`}
      >
        <input
          id={inputId}
          type={type === 'single' ? 'radio' : 'checkbox'}
          name={qKey}
          value={optValue}
          checked={checked}
          onChange={() => (type === 'single' ? setSingle(qKey, optValue) : toggleMulti(qKey, optValue))}
          className="mt-0.5 w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 flex-shrink-0"
        />
        <span>{optLabel}</span>
      </label>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-2xl mx-auto bg-white rounded-2xl shadow-lg p-8">
        <h1 className="text-2xl font-bold text-gray-800 mb-1">知情同意与基本信息填写</h1>
        <p className="text-gray-500 mb-6 text-sm">请仔细阅读知情同意书并完成 10 题基本信息问卷，再开始后续任务。</p>

        {/* —— 知情同意书 —— */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-3">一、知情同意书</h2>
          <div className="bg-gray-50 rounded-lg p-5 mb-4 max-h-72 overflow-y-auto text-sm text-gray-600 leading-relaxed">
            <p className="mb-3">尊敬的参与者：</p>
            <p className="mb-3">感谢您参与本研究。本研究旨在探索智能体助理在旅行规划任务中的用户采纳机制。实验过程约 60-80 分钟。</p>
            <p className="mb-3"><strong>实验内容：</strong>您需要完成一份杭州三日游旅游攻略方案。方案需统筹考虑交通（景点间市内交通方式及费用）、景点（游览选择、顺序、停留时长、门票）和食宿（每晚住宿、每日三餐安排）三方面内容。预算上限 2000 元（不含往返大交通），仅用于杭州当地消费（住宿、餐饮、景点门票、市内交通等）。出行人数 1 人（单人出行）。</p>
            <p className="mb-3"><strong>数据收集：</strong>实验过程中将记录您的操作行为（如搜索关键词、编辑操作、任务耗时、交互次数等），用于研究分析。实验结束后需填写一份量表。所有数据匿名处理，不会泄露个人身份。</p>
            <p className="mb-3"><strong>评价说明：</strong>方案评分细则与权重不向受试者公开，以保持规划行为的自然性。受试者仅需知晓任务要求与方案要素即可。</p>
            <p className="mb-3"><strong>权利保障：</strong>您有权随时退出实验，不影响您的任何权益。实验数据仅用于学术研究。</p>
            <p className="mb-3"><strong>保密承诺：</strong>研究者承诺对所有收集的数据严格保密，仅用于学术研究目的。</p>
            <p>如有疑问，请联系研究者。勾选下方"我已阅读并同意"即表示您已阅读并同意参与本研究。</p>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700">我已阅读并同意上述知情同意书内容</span>
          </label>
        </section>

        {/* —— 基本信息问卷 10 题 —— */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">二、基本信息（实验前置问卷）</h2>
          <p className="text-xs text-gray-500 mb-4">本部分共 10 题，用于实验研究分析，所有信息匿名处理。</p>

          <div className="space-y-6">
            {QUESTIONS.map((q, idx) => (
              <div key={q.key}>
                <div className="flex items-baseline gap-2 mb-2">
                  <span className="text-sm font-medium text-gray-700">{q.title}</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {OPTIONS[q.key as keyof typeof OPTIONS].map((opt) =>
                    renderOption(q.key, opt.value, opt.label, q.type),
                  )}
                </div>
                {idx < QUESTIONS.length - 1 && <div className="border-b border-gray-100 mt-6" />}
              </div>
            ))}
          </div>
        </section>

        {error && (
          <p className="text-red-500 text-sm mb-4 text-center bg-red-50 py-2 rounded-lg">{error}</p>
        )}

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {loading ? '提交中...' : '提交并开始任务'}
        </button>
      </div>
    </div>
  )
}
