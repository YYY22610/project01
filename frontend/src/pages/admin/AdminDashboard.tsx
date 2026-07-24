import { useEffect, useState } from 'react'
import { useAdminStore } from '../../stores/adminStore'

export default function AdminDashboard() {
  const { fetchDashboard, fetchOpenClaw, toggleOpenClaw, dashboardStats } = useAdminStore()
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(false)

  useEffect(() => {
    const load = async () => {
      await Promise.all([fetchDashboard(), fetchOpenClaw()])
      setLoading(false)
    }
    load()
    // Refresh every 30s
    const interval = setInterval(() => { fetchDashboard(); fetchOpenClaw() }, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleToggleOpenClaw = async () => {
    setToggling(true)
    try {
      await toggleOpenClaw(!oc.paused)
      await fetchDashboard()
    } finally {
      setToggling(false)
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-gray-400">加载中...</div>
  }

  const stats = dashboardStats || {
    total_participants: 0,
    group_distribution: { H: 0, SOA: 0, MOA: 0 },
    experiment_status: 'stopped',
    completion_rate: 0,
    avg_duration_ms: 0,
    api_status: { search: 'unknown', llm: 'unknown', email: 'unknown' },
    recent_registrations: [],
    abnormal_count: 0,
  }

  const oc = stats.openclaw_status || {
    status: 'unknown', paused: false, total_calls: 0,
    success_rate: null, avg_latency_ms: null, recent_failures: 0,
  }

  const targetPerGroup = Math.ceil(stats.total_participants / 3)
  const groups = [
    { key: 'H', label: 'H组（纯人工）', color: 'bg-blue-500', count: stats.group_distribution?.H || 0 },
    { key: 'SOA', label: 'SOA组（单AI）', color: 'bg-green-500', count: stats.group_distribution?.SOA || 0 },
    { key: 'MOA', label: 'MOA组（多AI）', color: 'bg-purple-500', count: stats.group_distribution?.MOA || 0 },
  ]

  const apiList = [
    { key: 'search', label: '搜索API', status: stats.api_status?.search || 'unknown' },
    { key: 'llm', label: 'LLM API', status: stats.api_status?.llm || 'unknown' },
    { key: 'email', label: '邮件API', status: stats.api_status?.email || 'unknown' },
  ]

  const statusColor = (s: string) => {
    if (s === 'ok' || s === 'healthy') return 'bg-green-100 text-green-700'
    if (s === 'error' || s === 'down') return 'bg-red-100 text-red-700'
    return 'bg-gray-100 text-gray-600'
  }

  const formatDuration = (ms: number) => {
    if (!ms) return '-'
    const min = Math.floor(ms / 60000)
    return `${min}分钟`
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">实验监控看板</h1>
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${stats.experiment_status === 'running' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
          {stats.experiment_status === 'running' ? '实验进行中' : '实验已停止'}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-5">
          <div className="text-sm text-gray-500 mb-1">总参与者</div>
          <div className="text-3xl font-bold text-gray-800">{stats.total_participants}</div>
          <div className="text-xs text-gray-400 mt-1">目标: 100人</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-5">
          <div className="text-sm text-gray-500 mb-1">完成率</div>
          <div className="text-3xl font-bold text-blue-600">{stats.completion_rate}%</div>
          <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full" style={{ width: `${stats.completion_rate}%` }} />
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-5">
          <div className="text-sm text-gray-500 mb-1">平均用时</div>
          <div className="text-3xl font-bold text-gray-800">{formatDuration(stats.avg_duration_ms)}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-5">
          <div className="text-sm text-gray-500 mb-1">异常数</div>
          <div className={`text-3xl font-bold ${stats.abnormal_count > 0 ? 'text-red-600' : 'text-gray-800'}`}>{stats.abnormal_count}</div>
          <div className="text-xs text-gray-400 mt-1">超3倍标准差</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Group Distribution */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">三组样本量监控</h2>
          <div className="space-y-4">
            {groups.map((g) => (
              <div key={g.key}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-gray-600">{g.label}</span>
                  <span className="font-medium text-gray-800">{g.count} / {targetPerGroup}</span>
                </div>
                <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                  <div className={`h-full ${g.color} rounded-full transition-all duration-500`} style={{ width: `${targetPerGroup > 0 ? (g.count / targetPerGroup) * 100 : 0}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-gray-100 text-sm text-gray-500">
            均衡比例 1:1:1 {stats.total_participants > 0 ? '✓' : ''}
          </div>
        </div>

        {/* API Status */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">AI助理API状态</h2>
          <div className="space-y-3">
            {apiList.map((api) => (
              <div key={api.key} className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{api.label}</span>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColor(api.status)}`}>{api.status}</span>
              </div>
            ))}
          </div>
        </div>

        {/* OpenClaw (AI agent) runtime status */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-800">OpenClaw 服务状态</h2>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
              oc.status === 'ok' ? 'bg-green-100 text-green-700'
              : oc.status === 'paused' ? 'bg-gray-100 text-gray-600'
              : oc.status === 'degraded' ? 'bg-amber-100 text-amber-700'
              : 'bg-gray-100 text-gray-500'
            }`}>
              {oc.status === 'ok' ? '正常' : oc.status === 'paused' ? '已暂停' : oc.status === 'degraded' ? '降级' : '未知'}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div>
              <div className="text-xs text-gray-500">成功率</div>
              <div className="text-xl font-bold text-gray-800">{oc.success_rate != null ? (oc.success_rate * 100).toFixed(1) + '%' : '-'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">平均延迟</div>
              <div className="text-xl font-bold text-gray-800">{oc.avg_latency_ms != null ? oc.avg_latency_ms + 'ms' : '-'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">近24h失败</div>
              <div className={`text-xl font-bold ${oc.recent_failures > 0 ? 'text-red-600' : 'text-gray-800'}`}>{oc.recent_failures}</div>
            </div>
          </div>
          <button
            onClick={handleToggleOpenClaw}
            disabled={toggling}
            className={`w-full py-2 rounded-lg text-sm font-medium ${
              oc.paused ? 'bg-green-600 text-white hover:bg-green-700' : 'bg-red-50 text-red-600 hover:bg-red-100'
            } disabled:opacity-50`}
          >
            {oc.paused ? '恢复 AI 助理服务' : '暂停 AI 助理服务'}
          </button>
          <p className="text-xs text-gray-400 mt-2">暂停后参与者调用 AI 助理将被拒绝（实验中断保护）</p>
        </div>
      </div>

      {/* Recent Registrations */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">最近注册</h2>
        {stats.recent_registrations && stats.recent_registrations.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-500 uppercase border-b border-gray-100">
                <tr>
                  <th className="px-3 py-2 text-left">邮箱</th>
                  <th className="px-3 py-2 text-left">注册时间</th>
                  <th className="px-3 py-2 text-left">状态</th>
                  <th className="px-3 py-2 text-left">完成度</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {stats.recent_registrations.map((r: any, i: number) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-3 py-2 text-gray-800">{r.email}</td>
                    <td className="px-3 py-2 text-gray-500">{new Date(r.created_at).toLocaleString('zh-CN')}</td>
                    <td className="px-3 py-2 text-gray-600">{r.status}</td>
                    <td className="px-3 py-2 text-gray-600">{r.progress || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-400">暂无注册数据</div>
        )}
      </div>
    </div>
  )
}
