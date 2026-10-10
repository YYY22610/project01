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
    title: '人工规划模式（A组）· 任务演示',
    points: [
      '本环节不提供 AI 助理，不得使用AI对话助手类工具',
      '使用「景点搜索」工具查找杭州景点及交通信息',
      '在文本框中手动撰写行程，点击「生成 Word 文档」导出',
      '使用「设置提醒」与「发送邮件」工具完成后续子任务',
    ],
  },
  MOA: {
    title: '智能体助理辅助模式（B组）· 任务演示',
    points: [
      '本环节提供智囊团群辩功能：5 位职能角色（主持人 + 4 位专家）同屏辩论后整合方案',
      '在左侧「智囊团」面板点击"展开讨论室"发起群辩，专家将围绕你的需求讨论',
      '讨论完成后生成整合方案，可导出为 Word 文档',
      '你始终掌握最终决定权，智囊团仅提供建议与执行辅助',
    ],
  },
  SOA: {
    title: '智能体助理辅助模式（单AI·C组）· 任务演示',
    points: [
      '本环节提供一位全能 AI 助理，可帮你搜索景点、规划行程、计算预算、生成 Word 文档、设置提醒与发送邮件',
      '在左侧「AI助手」面板与助理对话，描述你的需求即可获得方案与执行辅助',
      '助理具备全部工具能力，可一站式完成攻略各个环节',
      '你始终掌握最终决定权，AI 助理仅提供建议与执行辅助',
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
              请完成一份<strong>{taskConfig?.destination || '杭州'}{taskConfig?.task_days || 3}日游旅游攻略方案</strong>
            </p>
            <p className="text-blue-700 text-sm mb-1">
              预算上限：<strong>¥{taskConfig?.task_budget || 2000}</strong>（不含往返大交通，仅用于当地消费）
            </p>
            <p className="text-blue-700 text-sm mb-1">
              出行人数：<strong>{taskConfig?.travelers || '1 人'}</strong>
            </p>
            <p className="text-blue-600 text-xs mt-2">
              方案需统筹考虑：<strong>交通</strong>（景点间市内交通）· <strong>景点</strong>（游览选择与门票）· <strong>食宿</strong>（住宿与餐饮安排）
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
                  <span className="text-gray-700">搜索杭州景点及交通信息</span>
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

          <h2 className="text-lg font-semibold text-gray-800 mb-3">视频解说</h2>
          <div className="mb-6">
            <video
              controls
              className="w-full rounded-xl bg-gray-900"
              style={{ aspectRatio: '16 / 9' }}
              aria-label="任务演示视频"
            >
              <p className="text-center text-gray-300 py-12">
                视频解说暂未上传，请阅读上方文字说明。
              </p>
            </video>
            <p className="text-xs text-gray-400 mt-2 text-center">视频解说（待补充）</p>
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
              <strong>注意：</strong>攻略制定限时<strong>60分钟</strong>，可提前提交。请在完成所有子任务后点击"提交任务"。任务计时将从点击"开始任务"后开始。
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
