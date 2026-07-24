import { useEffect, useState, Fragment } from 'react'
import { useAdminStore } from '../../stores/adminStore'
import { adminApi } from '../../services/api'

// 8-factor 100-point scheme (GB/T 18972-2017 derived)
const FACTORS = [
  { key: 'scenic_score', label: '观赏游憩价值', weight: 30 },
  { key: 'historic_score', label: '历史文化价值', weight: 25 },
  { key: 'rarity_score', label: '珍稀奇特程度', weight: 15 },
  { key: 'scale_score', label: '规模与体量', weight: 10 },
  { key: 'integrity_score', label: '完整性', weight: 5 },
  { key: 'fame_score', label: '知名度/影响力', weight: 10 },
  { key: 'season_score', label: '适游期/使用范围', weight: 5 },
]
const FACTOR_WEIGHTS: Record<string, number> = Object.fromEntries(
  FACTORS.map((f) => [f.key, f.weight])
)

function emptyScore() {
  return {
    scenic_score: 0, historic_score: 0, rarity_score: 0, scale_score: 0,
    integrity_score: 0, fame_score: 0, season_score: 0, eco_score: 0, notes: '',
  }
}

function computeTotal(s: any): number {
  let sum = 0
  for (const k of Object.keys(FACTOR_WEIGHTS)) {
    sum += (Number(s[k]) || 0) * FACTOR_WEIGHTS[k] / 10
  }
  sum += Number(s.eco_score) || 0
  return Math.max(0, Math.min(100, Math.round(sum)))
}

export default function AdminSubmissions() {
  const { fetchSubmissions, setScore, submissions } = useAdminStore()
  const [scoring, setScoring] = useState<string | null>(null)
  const [scores, setScores] = useState<Record<string, any>>({})

  useEffect(() => {
    fetchSubmissions()
  }, [])

  const getScore = (userId: string) => scores[userId] || emptyScore()

  const setFactor = (userId: string, key: string, value: any) => {
    setScores({ ...scores, [userId]: { ...getScore(userId), [key]: value } })
  }

  const handleScore = async (userId: string) => {
    const s = getScore(userId)
    const payload = {
      scenic_score: Number(s.scenic_score) || 0,
      historic_score: Number(s.historic_score) || 0,
      rarity_score: Number(s.rarity_score) || 0,
      scale_score: Number(s.scale_score) || 0,
      integrity_score: Number(s.integrity_score) || 0,
      fame_score: Number(s.fame_score) || 0,
      season_score: Number(s.season_score) || 0,
      eco_score: Number(s.eco_score) || 0,
      notes: s.notes || '',
    }
    try {
      await setScore(userId, payload)
      setScoring(null)
      alert('评分已保存（总分 ' + computeTotal(payload) + '）')
    } catch {
      alert('评分失败')
    }
  }

  const handleExport = async () => {
    try {
      const res = await adminApi.get('/export/scores', { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `scores_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('导出失败')
    }
  }

  const formatDuration = (ms: number) => {
    if (!ms) return '-'
    const min = Math.floor(ms / 60000)
    return `${min}分钟`
  }

  const groupColor = (g: string) => {
    if (g === 'H') return 'bg-blue-100 text-blue-700'
    if (g === 'SOA') return 'bg-green-100 text-green-700'
    if (g === 'MOA') return 'bg-purple-100 text-purple-700'
    return 'bg-gray-100 text-gray-600'
  }

  const scoredSubmissions = submissions.filter((s: any) => s.scored)
  const avgTotal = scoredSubmissions.length
    ? scoredSubmissions.reduce((a: number, s: any) => a + (s.total_score || 0), 0) / scoredSubmissions.length
    : null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">任务提交与评分</h1>
        <button onClick={handleExport} className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
          导出评分
        </button>
      </div>

      {/* Score Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-4">
          <div className="text-sm text-gray-500">已提交</div>
          <div className="text-2xl font-bold text-gray-800">{submissions.length}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-4">
          <div className="text-sm text-gray-500">已评分</div>
          <div className="text-2xl font-bold text-blue-600">{scoredSubmissions.length}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-4">
          <div className="text-sm text-gray-500">待评分</div>
          <div className="text-2xl font-bold text-orange-500">{submissions.filter((s: any) => !s.scored).length}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-4">
          <div className="text-sm text-gray-500">平均总分</div>
          <div className="text-2xl font-bold text-gray-800">{avgTotal !== null ? avgTotal.toFixed(1) : '-'}</div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3 text-left">邮箱</th>
                <th className="px-4 py-3 text-center">组别</th>
                <th className="px-4 py-3 text-center">搜索</th>
                <th className="px-4 py-3 text-center">文档</th>
                <th className="px-4 py-3 text-center">提醒</th>
                <th className="px-4 py-3 text-center">邮件</th>
                <th className="px-4 py-3 text-left">用时</th>
                <th className="px-4 py-3 text-center">总分</th>
                <th className="px-4 py-3 text-left">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {submissions.length === 0 ? (
                <tr><td colSpan={9} className="text-center py-12 text-gray-400">暂无提交</td></tr>
              ) : (
                submissions.map((s: any) => (
                  <Fragment key={s.id}>
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm text-gray-800">{s.email}</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${groupColor(s.group)}`}>{s.group || '-'}</span>
                      </td>
                      <td className="px-4 py-3 text-center text-sm">{s.task1_search ? <span className="text-green-600">✓</span> : <span className="text-gray-300">✗</span>}</td>
                      <td className="px-4 py-3 text-center text-sm">{s.task2_document ? <span className="text-green-600">✓</span> : <span className="text-gray-300">✗</span>}</td>
                      <td className="px-4 py-3 text-center text-sm">{s.task3_reminder ? <span className="text-green-600">✓</span> : <span className="text-gray-300">✗</span>}</td>
                      <td className="px-4 py-3 text-center text-sm">{s.task4_email ? <span className="text-green-600">✓</span> : <span className="text-gray-300">✗</span>}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{formatDuration(s.duration_ms)}</td>
                      <td className="px-4 py-3 text-center text-sm">
                        {s.scored ? (
                          <span className="text-blue-600 font-bold">{s.total_score}</span>
                        ) : (
                          <span className="text-gray-300">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => setScoring(scoring === s.user_id ? null : s.user_id)}
                          className={`px-3 py-1 rounded text-xs ${scoring === s.user_id ? 'bg-gray-200 text-gray-700' : 'bg-blue-100 text-blue-700 hover:bg-blue-200'}`}
                        >
                          {scoring === s.user_id ? '收起' : s.scored ? '修改' : '评分'}
                        </button>
                      </td>
                    </tr>
                    {scoring === s.user_id && (
                      <tr className="bg-gray-50">
                        <td colSpan={9} className="px-4 py-4">
                          <div className="mb-3 flex items-center justify-between">
                            <span className="text-sm font-semibold text-gray-700">8 因子评分（各 0-10，权重合计 100）</span>
                            <span className="text-sm text-gray-500">实时总分：
                              <span className="text-lg font-bold text-blue-600 ml-1">{computeTotal(getScore(s.user_id))}</span> / 100
                            </span>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                            {FACTORS.map((f) => {
                              const val = getScore(s.user_id)[f.key]
                              return (
                                <div key={f.key}>
                                  <label className="block text-sm font-medium text-gray-700 mb-1">
                                    {f.label} <span className="text-xs text-gray-400">({f.weight})</span>
                                  </label>
                                  <div className="flex items-center gap-2">
                                    <input
                                      type="range" min="0" max="10"
                                      value={val}
                                      onChange={(e) => setFactor(s.user_id, f.key, parseInt(e.target.value))}
                                      className="flex-1"
                                    />
                                    <span className="text-sm font-bold text-blue-600 w-6 text-center">{val}</span>
                                  </div>
                                </div>
                              )
                            })}
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-1">环保附加值 (-5~+3)</label>
                              <div className="flex items-center gap-2">
                                <input
                                  type="range" min="-5" max="3"
                                  value={getScore(s.user_id).eco_score}
                                  onChange={(e) => setFactor(s.user_id, 'eco_score', parseInt(e.target.value))}
                                  className="flex-1"
                                />
                                <span className="text-sm font-bold text-blue-600 w-6 text-center">{getScore(s.user_id).eco_score}</span>
                              </div>
                            </div>
                            <div className="lg:col-span-3">
                              <label className="block text-sm font-medium text-gray-700 mb-1">备注</label>
                              <textarea
                                value={getScore(s.user_id).notes}
                                onChange={(e) => setFactor(s.user_id, 'notes', e.target.value)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                                rows={2}
                                placeholder="评分说明..."
                              />
                            </div>
                          </div>
                          <div className="flex gap-2 mt-3">
                            <button
                              onClick={() => handleScore(s.user_id)}
                              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
                            >保存评分</button>
                            <button
                              onClick={() => setScoring(null)}
                              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm hover:bg-gray-300"
                            >取消</button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
