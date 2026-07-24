import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../stores/userStore'
import { useBehaviorLogger } from '../hooks/useBehaviorLogger'
import { useEffect, useRef, useState } from 'react'

function getGroupFromToken(): string {
  const token = localStorage.getItem('access_token')
  if (!token) return 'H'
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.group || 'H'
  } catch {
    return 'H'
  }
}

// 分组差异化演示内容（单盲操纵：不同组看到不同的辅助方式说明）
const DEMO_CONTENT: Record<string, { title: string; points: string[] }> = {
  H: {
    title: '纯人工模式 · 任务演示',
    points: [
      '本环节不提供 AI 助理，你将完全依靠平台自带的基础工具完成任务',
      '使用「景点搜索」工具查找杭州景点信息',
      '在文本框中手动撰写行程，点击「生成 Word 文档」导出',
      '使用「设置提醒」与「发送邮件」工具完成后续子任务',
    ],
  },
  SOA: {
    title: '单 AI 助理模式 · 任务演示',
    points: [
      '本环节提供 1 个 AI 助理，可帮你搜索、撰写、设置提醒与发送邮件',
      '在右侧 AI 助理面板中输入需求，例如「帮我规划杭州三日游」',
      'AI 会调用工具生成文档、设置提醒、发送邮件，你可随时修改',
      '你始终掌握最终决定权，AI 仅提供建议与执行辅助',
    ],
  },
  MOA: {
    title: '多 AI 助理模式 · 任务演示',
    points: [
      '本环节提供 3 个 AI 助理：信息检索专员、行程编排专员、事务处理专员',
      '信息检索专员负责搜索景点；行程编排专员负责生成文档；事务处理专员负责提醒与邮件',
      '根据需要在对应助理面板中输入指令，助理之间由你手动传递信息',
      '你统筹三个助理的分工，最终决策权在你手中',
    ],
  },
}

export default function Demo() {
  const { user, taskConfig, fetchTaskConfig, completeDemo, startTask } = useUserStore()
  const { log } = useBehaviorLogger()
  const navigate = useNavigate()
  const [confirmed, setConfirmed] = useState(false)
  const [group, setGroup] = useState<string>('H')
  const startTimeRef = useRef<number>(Date.now())

  useEffect(() => {
    fetchTaskConfig()
    log({ action_type: 'demo_view' })
    setGroup(getGroupFromToken())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleStart = async () => {
    if (!confirmed) return
    const watchSeconds = Math.max(1, Math.round((Date.now() - startTimeRef.current) / 1000))
    try {
      if (user?.status === 'consented') {
        await completeDemo(watchSeconds)
      }
      await startTask()
      log({ action_type: 'task_start', extra_data: { demo_watch_seconds: watchSeconds } })
      navigate('/task')
    } catch (e: any) {
      alert(e.response?.data?.detail || '操作失败')
    }
  }

  const content = DEMO_CONTENT[group] || DEMO_CONTENT.H
  const subTasks = taskConfig?.sub_tasks

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="bg-white rounded-2xl shadow-lg p-8 mb-6">
          <h1 className="text-2xl font-bold text-gray-800 mb-2">任务说明</h1>
          <p className="text-gray-500 mb-6">请仔细阅读以下任务要求与演示内容</p>

          <div className="bg-blue-50 rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold text-blue-900 mb-3">核心任务</h2>
            <p className="text-blue-800 mb-2">
              请完成一份<strong>{taskConfig?.destination || '杭州'}{taskConfig?.task_days || 3}日游行程规划</strong>
            </p>
            <p className="text-blue-700 text-sm">
              预算上限：<strong>¥{taskConfig?.task_budget || 1000}</strong>
            </p>
          </div>

          <h2 className="text-lg font-semibold text-gray-800 mb-3">{content.title}</h2>
          <div className="space-y-3 mb-6">
            {content.points.map((p, i) => (
              <div key={i} className="flex items-start gap-3 p-4 bg-gray-50 rounded-lg">
                <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-semibold">
                  {i + 1}
                </span>
                <span className="text-gray-700">{p}</span>
              </div>
            ))}
          </div>

          <h2 className="text-lg font-semibold text-gray-800 mb-3">需要完成的子任务</h2>
          <div className="space-y-3 mb-6">
            {subTasks && subTasks.length > 0 ? (
              subTasks.map((task, i) => (
                <div key={i} className="flex items-start gap-3 p-4 bg-gray-50 rounded-lg">
                  <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-semibold">
                    {i + 1}
                  </span>
                  <span className="text-gray-700">{task}</span>
                </div>
              ))
            ) : (
              <>
                <div className="flex items-start gap-3 p-4 bg-gray-50 rounded-lg">
                  <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-semibold">1</span>
                  <span className="text-gray-700">搜索杭州景点信息</span>
                </div>
                <div className="flex items-start gap-3 p-4 bg-gray-50 rounded-lg">
                  <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-semibold">2</span>
                  <span className="text-gray-700">生成3日游行程Word文档</span>
                </div>
                <div className="flex items-start gap-3 p-4 bg-gray-50 rounded-lg">
                  <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-semibold">3</span>
                  <span className="text-gray-700">设置旅行提醒</span>
                </div>
                <div className="flex items-start gap-3 p-4 bg-gray-50 rounded-lg">
                  <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-semibold">4</span>
                  <span className="text-gray-700">将行程发送至指定邮箱</span>
                </div>
              </>
            )}
          </div>

          <label className="flex items-center gap-2 mb-6 cursor-pointer">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700">我已理解上述演示内容，可以开始任务</span>
          </label>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
            <p className="text-amber-800 text-sm">
              <strong>注意：</strong>请在完成所有子任务后点击"提交任务"。任务计时将从点击"开始任务"后开始。
            </p>
          </div>

          <button
            onClick={handleStart}
            disabled={!confirmed}
            className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition"
          >
            开始任务
          </button>
        </div>
      </div>
    </div>
  )
}
