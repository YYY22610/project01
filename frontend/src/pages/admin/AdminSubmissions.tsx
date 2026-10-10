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
    integrity_score: 0, fame_score: 0, season_score: 0, eco_score: 0,
    quality_score: 0, reminder_correct: false, notes: '',
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
  const { fetchSubmissions, setScore, submissions, fetchParticipantDetail, updateParticipantGroup, downloadParticipantDocx } = useAdminStore()
  const [scoring, setScoring] = useState<string | null>(null)
  const [scores, setScores] = useState<Record<string, any>>({})
  const [detailUser, setDetailUser] = useState<any>(null)
  const [detail, setDetail] = useState<any>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [editGroup, setEditGroup] = useState<string>('')
  const [savingGroup, setSavingGroup] = useState(false)

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
      quality_score: Number(s.quality_score) || 0,
      reminder_correct: !!s.reminder_correct,
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
    if (g === 'SOA') return 'bg-emerald-100 text-emerald-700'
    if (g === 'MOA') return 'bg-purple-100 text-purple-700'
    return 'bg-gray-100 text-gray-600'
  }

  const groupLabel = (g: string) => {
    if (g === 'H') return 'H组'
    if (g === 'SOA') return 'SOA组'
    if (g === 'MOA') return 'MOA组'
    return '-'
  }

  const statusLabel = (s: string) => {
    const map: Record<string, string> = {
      registered: '已注册',
      consented: '已同意',
      demo_completed: '已完成演示',
      task_in_progress: '任务进行中',
      task_completed: '任务已完成',
      questionnaire_completed: '已完成问卷',
      submitted: '已提交',
      completed: '已完成',
    }
    return map[s] || s || '-'
  }

  const statusColor = (s: string) => {
    if (s === 'registered') return 'bg-gray-100 text-gray-600'
    if (s === 'consented') return 'bg-blue-100 text-blue-700'
    if (s === 'demo_completed') return 'bg-indigo-100 text-indigo-700'
    if (s === 'task_in_progress') return 'bg-amber-100 text-amber-700'
    if (s === 'task_completed' || s === 'submitted') return 'bg-purple-100 text-purple-700'
    if (s === 'questionnaire_completed' || s === 'completed') return 'bg-green-100 text-green-700'
    return 'bg-gray-100 text-gray-600'
  }

  const genderLabel = (v?: string) =>
    ({ male: '男', female: '女', other: '其他' }[v || ''] || v || '-')
  const educationLabel = (v?: string) =>
    ({
      high_school: '高中及以下',
      college: '大专',
      bachelor: '本科',
      master: '硕士',
      phd: '博士',
    }[v || ''] || v || '-')
  const techFrequencyLabel = (v?: string) =>
    ({
      rarely: '很少使用',
      sometimes: '偶尔使用',
      often: '经常使用',
      daily: '每天使用',
    }[v || ''] || v || '-')
  const aiExperienceLabel = (v?: string) =>
    ({
      none: '从未使用',
      basic: '偶尔尝试',
      intermediate: '有一定经验',
      advanced: '熟练使用',
    }[v || ''] || v || '-')

  const openDetail = async (s: any) => {
    setDetailUser(s)
    setDetail(null)
    setLoadingDetail(true)
    setEditGroup(s.group || '')
    try {
      const d = await fetchParticipantDetail(s.user_id)
      setDetail(d)
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleSaveGroup = async () => {
    if (!detailUser) return
    setSavingGroup(true)
    try {
      await updateParticipantGroup(detailUser.user_id, editGroup)
      const nextUser = { ...detailUser, group: editGroup }
      setDetailUser(nextUser)
      if (detail) {
        setDetail({ ...detail, user: { ...detail.user, group: editGroup } })
      }
      await fetchSubmissions()
      alert('分组已更新')
    } catch {
      alert('更新失败')
    } finally {
      setSavingGroup(false)
    }
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
                          onClick={() => openDetail(s)}
                          className="px-3 py-1 rounded text-xs bg-gray-100 text-gray-700 hover:bg-gray-200 mr-2"
                        >
                          详情
                        </button>
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
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-1">综合完成质量评分 (1-10)</label>
                              <div className="flex items-center gap-2">
                                <input
                                  type="range" min="0" max="10"
                                  value={getScore(s.user_id).quality_score}
                                  onChange={(e) => setFactor(s.user_id, 'quality_score', parseInt(e.target.value))}
                                  className="flex-1"
                                />
                                <span className="text-sm font-bold text-blue-600 w-6 text-center">{getScore(s.user_id).quality_score}</span>
                              </div>
                            </div>
                            <div className="lg:col-span-3 flex items-end gap-6">
                              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer whitespace-nowrap pb-2">
                                <input
                                  type="checkbox"
                                  checked={!!getScore(s.user_id).reminder_correct}
                                  onChange={(e) => setFactor(s.user_id, 'reminder_correct', e.target.checked)}
                                  className="w-4 h-4"
                                />
                                提醒正确性（人工判定 ✓）
                              </label>
                              <div className="flex-1">
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

      {/* Participant Detail Modal */}
      {detailUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setDetailUser(null)}>
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-800">参与者详情</h2>
              <button onClick={() => setDetailUser(null)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">邮箱</span><span className="text-gray-800 font-medium">{detailUser.email}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">组别</span><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${groupColor(detailUser.group)}`}>{groupLabel(detailUser.group)}</span></div>
              <div className="pt-3 border-t border-gray-100">
                <div className="text-gray-500 mb-2">调整分组（实验平衡 / 修正误分配）</div>
                <div className="flex items-center gap-2">
                  <select
                    value={editGroup}
                    onChange={(e) => setEditGroup(e.target.value)}
                    className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm"
                  >
                    <option value="H">H组（纯人工）</option>
                    <option value="SOA">SOA组（单AI）</option>
                    <option value="MOA">MOA组（多AI）</option>
                  </select>
                  <button
                    onClick={handleSaveGroup}
                    disabled={savingGroup || editGroup === detailUser.group}
                    className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-40 whitespace-nowrap"
                  >
                    {savingGroup ? '保存中...' : '保存分组'}
                  </button>
                </div>
                <p className="text-xs text-gray-400 mt-2">新分组将在该参与者下次登录后生效（分组信息存于登录令牌中）。</p>
              </div>
              <div className="flex justify-between"><span className="text-gray-500">状态</span><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(detail?.user?.status || detailUser.status)}`}>{statusLabel(detail?.user?.status || detailUser.status)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">注册时间</span><span className="text-gray-800">{detail?.user?.created_at ? new Date(detail.user.created_at).toLocaleString('zh-CN') : detailUser.created_at ? new Date(detailUser.created_at).toLocaleString('zh-CN') : '-'}</span></div>

              {(detail?.user?.age != null || detail?.user?.gender || detail?.user?.education || detail?.user?.tech_frequency || detail?.user?.ai_experience) && (
                <div className="pt-3 border-t border-gray-100">
                  <div className="text-gray-500 mb-2">注册信息</div>
                  <div className="grid grid-cols-2 gap-3 bg-gray-50 rounded-lg p-3 text-xs">
                    <div><span className="text-gray-400">年龄：</span><span className="text-gray-800 font-medium">{detail.user.age ?? '-'}</span></div>
                    <div><span className="text-gray-400">性别：</span><span className="text-gray-800 font-medium">{genderLabel(detail.user.gender)}</span></div>
                    <div><span className="text-gray-400">学历：</span><span className="text-gray-800 font-medium">{educationLabel(detail.user.education)}</span></div>
                    <div><span className="text-gray-400">AI工具使用频率：</span><span className="text-gray-800 font-medium">{techFrequencyLabel(detail.user.tech_frequency)}</span></div>
                    <div className="col-span-2"><span className="text-gray-400">AI工具使用经验：</span><span className="text-gray-800 font-medium">{aiExperienceLabel(detail.user.ai_experience)}</span></div>
                  </div>
                </div>
              )}

              {loadingDetail && <div className="pt-3 text-sm text-gray-400">加载详情中...</div>}
              {detail && (
                <>
                  <div className="pt-3 border-t border-gray-100">
                    <div className="text-gray-500 mb-2">行程 Word 文档</div>
                    {detail.submission?.docx_file_name ? (
                      <button
                        onClick={() => downloadParticipantDocx(detailUser.user_id)}
                        className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700"
                      >
                        下载 {detail.submission.docx_file_name}
                      </button>
                    ) : (
                      <span className="text-gray-400 text-xs">未生成</span>
                    )}
                  </div>

                  <div className="pt-3 border-t border-gray-100">
                    <div className="text-gray-500 mb-2">提醒设置（共 {detail.reminders?.length || 0} 条）</div>
                    {detail.reminders && detail.reminders.length > 0 ? (
                      <ul className="space-y-1">
                        {detail.reminders.map((r: any) => (
                          <li key={r.id} className="text-xs text-gray-700">
                            <span className="font-medium">{r.reminder_datetime ? new Date(r.reminder_datetime).toLocaleString('zh-CN') : '-'}</span>
                            ：{r.content || '（无内容）'}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-gray-400 text-xs">未设置提醒</span>
                    )}
                  </div>

                  <div className="pt-3 border-t border-gray-100">
                    <div className="text-gray-500 mb-2">邮件发送</div>
                    {detail.submission?.email_status ? (
                      <div className="text-xs text-gray-700 space-y-1">
                        <div>收件人：{detail.submission.email_recipient || '-'}</div>
                        <div>状态：
                          <span className={detail.submission.email_status === 'sent' || detail.submission.email_status === 'mock_sent' ? 'text-green-600' : 'text-red-600'}>
                            {detail.submission.email_status}
                          </span>
                        </div>
                        <div>提交时间：{detail.submission.submitted_at ? new Date(detail.submission.submitted_at).toLocaleString('zh-CN') : '-'}</div>
                      </div>
                    ) : (
                      <span className="text-gray-400 text-xs">未发送</span>
                    )}
                  </div>

                  {detail.scores && detail.scores.length > 0 && (
                    <div className="pt-3 border-t border-gray-100">
                      <div className="text-gray-500 mb-2">研究员评分</div>
                      <div className="text-xs text-gray-700 space-y-1">
                        <div>行程合理性总分：{detail.scores[0].total_score ?? '-'}</div>
                        <div>综合完成质量评分 (1-10)：{detail.scores[0].quality_score ?? '-'}</div>
                        <div>提醒正确性（人工判定）：{detail.scores[0].reminder_correct ? '✓ 正确' : '✗ 不正确 / 未判定'}</div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
