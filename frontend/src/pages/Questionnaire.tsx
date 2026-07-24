import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../stores/userStore'
import { questionnaireApi } from '../services'
import type { QuestionnaireItem } from '../types'
import { useBehaviorLogger } from '../hooks/useBehaviorLogger'

export default function Questionnaire() {
  const [items, setItems] = useState<QuestionnaireItem[]>([])
  const [responses, setResponses] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const { submitTask } = useUserStore()
  const { log } = useBehaviorLogger()
  const navigate = useNavigate()

  useEffect(() => {
    questionnaireApi.items().then(res => setItems(res.data)).catch(() => {})
  }, [])

  const allAnswered = items.length > 0 && items.every(item => responses[item.id])

  const handleSubmit = async () => {
    if (!allAnswered) return
    setSubmitting(true)
    try {
      const responsesArray = items.map(item => ({
        item_id: item.id,
        response_value: responses[item.id],
      }))
      await questionnaireApi.submit(responsesArray)
      await useUserStore.getState().fetchMe()
      setSubmitted(true)
      log({ action_type: 'questionnaire_submit' })
      navigate('/complete')
    } catch (e) {
      alert('提交失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  const constructLabels: Record<string, string> = {
    trust: '感知信任',
    autonomy: '感知自主性',
    satisfaction: '满意度',
    task_load: '任务负荷',
    future_use: '未来使用意愿',
    manipulation_check: '操纵检验',
  }

  let currentConstruct = ''

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-2xl shadow-lg p-8 mb-6">
          <h1 className="text-2xl font-bold text-gray-800 mb-2">实验问卷</h1>
          <p className="text-gray-500 mb-6">请根据您的真实感受回答以下问题</p>

          <div className="space-y-6">
            {items.map((item) => {
              const showHeader = item.construct !== currentConstruct
              currentConstruct = item.construct

              return (
                <div key={item.id}>
                  {showHeader && (
                    <h2 className="text-sm font-semibold text-blue-600 uppercase tracking-wide mb-3 pb-2 border-b border-blue-100">
                      {constructLabels[item.construct] || item.construct}
                    </h2>
                  )}
                  <div className="mb-4">
                    <p className="text-gray-700 mb-3">{item.question_text}</p>
                    {item.question_type === 'likert' && (
                      <div className="flex gap-2">
                        {Array.from({ length: item.scale_level }, (_, i) => i + 1).map((val) => (
                          <button
                            key={val}
                            onClick={() => setResponses({ ...responses, [item.id]: String(val) })}
                            className={`w-10 h-10 rounded-lg font-medium transition ${
                              responses[item.id] === String(val)
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                          >
                            {val}
                          </button>
                        ))}
                      </div>
                    )}
                    {item.question_type === 'choice' && Array.isArray(item.options) && (
                      <div className="flex flex-col gap-2">
                        {item.options.map((opt: string) => (
                          <button
                            key={opt}
                            onClick={() => setResponses({ ...responses, [item.id]: opt })}
                            className={`px-4 py-2 rounded-lg text-sm font-medium text-left transition ${
                              responses[item.id] === opt
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                          >
                            {opt}
                          </button>
                        ))}
                      </div>
                    )}
                    {item.question_type === 'likert' && item.scale_level === 5 && (
                      <div className="flex justify-between text-xs text-gray-400 mt-1">
                        <span>非常不同意</span>
                        <span>非常同意</span>
                      </div>
                    )}
                    {item.question_type === 'likert' && item.scale_level === 7 && (
                      <div className="flex justify-between text-xs text-gray-400 mt-1">
                        <span>非常低</span>
                        <span>非常高</span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          <button
            onClick={handleSubmit}
            disabled={!allAnswered || submitting || submitted}
            className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 mt-6"
          >
            {submitting ? '提交中...' : submitted ? '已提交' : allAnswered ? '提交问卷' : `请完成所有题目 (${Object.keys(responses).length}/${items.length})`}
          </button>
        </div>
      </div>
    </div>
  )
}
