import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../stores/userStore'
import { useQuestionnaire } from '../hooks/useQuestionnaire'
import { constructLabel } from '../constants/questionnaire'
import QuestionRenderer from '../components/QuestionRenderer'

export default function Consent() {
  const [agreed, setAgreed] = useState(false)
  const [error, setError] = useState('')
  const { consent, loading } = useUserStore()
  const navigate = useNavigate()

  const q = useQuestionnaire('pre', async (responses) => {
    await consent(true, responses)
    navigate('/demo')
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!agreed) {
      setError('请先勾选「我已阅读并同意」')
      return
    }
    if (!q.allAnswered) {
      setError(`请完成前置问卷全部题目（已完成 ${q.answeredCount}/${q.items.length}）`)
      return
    }
    try {
      await q.handleSubmit()
    } catch (e: any) {
      setError(e.response?.data?.detail || '提交失败')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-2xl mx-auto bg-white rounded-2xl shadow-lg p-8">
        <h1 className="text-2xl font-bold text-gray-800 mb-1">知情同意与前置问卷</h1>
        <p className="text-gray-500 mb-6 text-sm">
          请仔细阅读知情同意书，并完成实验前置问卷后再开始后续任务。
        </p>

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
            <p>如有疑问，请联系研究者。勾选下方“我已阅读并同意”即表示您已阅读并同意参与本研究。</p>
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

        {/* —— 前置问卷 —— */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">二、实验前置问卷</h2>
          <p className="text-xs text-gray-500 mb-4">
            本部分共 {q.items.length} 题，用于实验研究分析，所有信息匿名处理。
          </p>

          {q.loading && <p className="text-sm text-gray-500 py-6 text-center">问卷加载中…</p>}
          {q.loadError && <p className="text-sm text-red-500 py-6 text-center">{q.loadError}</p>}

          {!q.loading && !q.loadError && (
            <div className="space-y-6">
              {q.withHeaders.map(({ item, showHeader }) => (
                <div key={item.id}>
                  {showHeader && (
                    <h3 className="text-sm font-semibold text-blue-600 tracking-wide mb-3 pb-2 border-b border-blue-100">
                      {constructLabel(item.construct)}
                    </h3>
                  )}
                  <QuestionRenderer
                    item={item}
                    label={`Q${String(item.sort_order).padStart(2, '0')}.`}
                    value={q.answers[item.id]}
                    onChange={(v) => q.setAnswer(item.id, v)}
                  />
                </div>
              ))}
            </div>
          )}
        </section>

        {error && (
          <p className="text-red-500 text-sm mb-4 text-center bg-red-50 py-2 rounded-lg">{error}</p>
        )}

        <button
          onClick={handleSubmit}
          disabled={loading || q.loading || q.submitting}
          className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {loading || q.submitting ? '提交中...' : '提交并开始任务'}
        </button>
      </div>
    </div>
  )
}
