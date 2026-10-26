import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../stores/userStore'
import { questionnaireApi } from '../services'
import { useBehaviorLogger } from '../hooks/useBehaviorLogger'
import { useQuestionnaire } from '../hooks/useQuestionnaire'
import { constructLabel } from '../constants/questionnaire'
import QuestionRenderer from '../components/QuestionRenderer'

export default function Questionnaire() {
  const navigate = useNavigate()
  const { log } = useBehaviorLogger()

  const q = useQuestionnaire('post', async (responses) => {
    await questionnaireApi.submit(responses)
    await useUserStore.getState().fetchMe()
    log({ action_type: 'questionnaire_submit' })
    navigate('/complete')
  })

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <h1 className="text-2xl font-bold text-gray-800 mb-2">实验后置问卷</h1>
          <p className="text-gray-500 mb-6 text-sm">
            请结合本次旅游规划任务的实际体验作答，最后一题「其他反馈」为选填。
          </p>

          {q.loading && <p className="text-sm text-gray-500 py-8 text-center">问卷加载中…</p>}
          {q.loadError && <p className="text-sm text-red-500 py-8 text-center">{q.loadError}</p>}

          {!q.loading && !q.loadError && (
            <>
              <div className="space-y-7">
                {q.withHeaders.map(({ item, showHeader }) => (
                  <div key={item.id}>
                    {showHeader && (
                      <h2 className="text-sm font-semibold text-blue-600 tracking-wide mb-3 pb-2 border-b border-blue-100">
                        {constructLabel(item.construct)}
                      </h2>
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

              <button
                onClick={q.handleSubmit}
                disabled={!q.allAnswered || q.submitting || q.submitted}
                className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 mt-8"
              >
                {q.submitting
                  ? '提交中...'
                  : q.submitted
                    ? '已提交'
                    : q.allAnswered
                      ? '提交问卷'
                      : `请完成所有题目 (${q.answeredCount}/${q.items.length})`}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
