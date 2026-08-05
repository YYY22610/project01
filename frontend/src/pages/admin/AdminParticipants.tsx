import { useEffect, useState } from 'react'
import { useAdminStore } from '../../stores/adminStore'

export default function AdminParticipants() {
  const { fetchParticipants, participants, updateParticipantGroup, fetchParticipantDetail, downloadParticipantDocx, deleteParticipant } = useAdminStore()
  const [search, setSearch] = useState('')
  const [groupFilter, setGroupFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [selectedUser, setSelectedUser] = useState<any>(null)
  const [detail, setDetail] = useState<any>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [editGroup, setEditGroup] = useState<string>('')
  const [savingGroup, setSavingGroup] = useState(false)
  const pageSize = 20

  const openDetail = async (p: any) => {
    setSelectedUser(p)
    setDetail(null)
    setLoadingDetail(true)
    try {
      const d = await fetchParticipantDetail(p.id)
      setDetail(d)
    } finally {
      setLoadingDetail(false)
    }
  }

  // 打开详情时同步可编辑分组
  useEffect(() => {
    if (selectedUser) setEditGroup(selectedUser.group || '')
  }, [selectedUser])

  useEffect(() => {
    loadPage(1)
  }, [groupFilter, statusFilter])

  const loadPage = async (p: number) => {
    setPage(p)
    const res = await fetchParticipants({
      page: p,
      page_size: pageSize,
      search,
      group: groupFilter,
      status: statusFilter,
    })
    if (res?.total !== undefined) setTotal(res.total)
  }

  const handleSearch = () => loadPage(1)

  const handleSaveGroup = async () => {
    if (!selectedUser) return
    setSavingGroup(true)
    try {
      await updateParticipantGroup(selectedUser.id, editGroup)
      // 乐观更新：立即修改列表中该参与者的分组，避免后台列表刷新延迟导致"没调整"的错觉
      const nextUser = { ...selectedUser, group: editGroup }
      setSelectedUser(nextUser)
      useAdminStore.setState({
        participants: participants.map((p: any) => (p.id === selectedUser.id ? { ...p, group: editGroup } : p)),
      })
      await loadPage(page)
      alert('分组已更新')
    } catch {
      alert('更新失败')
    } finally {
      setSavingGroup(false)
    }
  }

  const totalPages = Math.ceil(total / pageSize)
  const groupLabel = (g: string) => {
    if (g === 'H') return 'H组'
    if (g === 'SOA') return 'SOA组'
    if (g === 'MOA') return 'MOA组'
    return '-'
  }
  const groupColor = (g: string) => {
    if (g === 'H') return 'bg-blue-100 text-blue-700'
    if (g === 'SOA') return 'bg-green-100 text-green-700'
    if (g === 'MOA') return 'bg-purple-100 text-purple-700'
    return 'bg-gray-100 text-gray-600'
  }

  const statusLabel = (s: string) => {
    const map: Record<string, string> = {
      registered: '已注册',
      consented: '已同意',
      demo_completed: '已完成演示',
      task_in_progress: '任务进行中',
      submitted: '已提交',
      completed: '已完成',
    }
    return map[s] || s
  }
  const statusColor = (s: string) => {
    if (s === 'registered') return 'bg-gray-100 text-gray-600'
    if (s === 'consented') return 'bg-blue-100 text-blue-700'
    if (s === 'demo_completed') return 'bg-indigo-100 text-indigo-700'
    if (s === 'task_in_progress') return 'bg-amber-100 text-amber-700'
    if (s === 'submitted') return 'bg-purple-100 text-purple-700'
    if (s === 'completed') return 'bg-green-100 text-green-700'
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

  // 详情弹窗里显示的人口统计学信息优先用详情接口数据
  const demoSource = detail?.user || selectedUser

  const [showStatusFlow, setShowStatusFlow] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<any>(null)
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteParticipant(deleteTarget.id)
      setDeleteTarget(null)
      loadPage(page)
    } catch {
      alert('删除失败')
    } finally {
      setDeleting(false)
    }
  }
  const statusFlow = [
    { key: 'registered', label: '已注册', desc: '完成账号注册' },
    { key: 'consented', label: '已同意', desc: '签署知情同意书' },
    { key: 'demo_completed', label: '已完成演示', desc: '完成实验演示环节' },
    { key: 'task_in_progress', label: '任务进行中', desc: '正在进行规划任务' },
    { key: 'submitted', label: '已提交', desc: '已提交任务成果' },
    { key: 'completed', label: '已完成', desc: '已完成问卷，实验结束' },
  ]

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-800">参与者管理</h1>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap gap-3 items-center">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="搜索邮箱..."
          className="flex-1 min-w-[200px] px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
        />
        <select value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
          <option value="">全部组别</option>
          <option value="H">H组</option>
          <option value="SOA">SOA组</option>
          <option value="MOA">MOA组</option>
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
          <option value="">全部状态</option>
          <option value="registered">已注册</option>
          <option value="consented">已同意</option>
          <option value="in_task">任务中</option>
          <option value="completed">已完成</option>
        </select>
        <button onClick={handleSearch} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">搜索</button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="px-4 py-3 text-left">邮箱</th>
              <th className="px-4 py-3 text-center">组别</th>
              <th
                className="px-4 py-3 text-center cursor-pointer hover:text-blue-600 select-none"
                onClick={() => setShowStatusFlow(true)}
                title="点击查看状态流程"
              >
                状态
              </th>
              <th className="px-4 py-3 text-center">注册时间</th>
              <th className="px-4 py-3 text-center">异常</th>
              <th className="px-4 py-3 text-center">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {participants.length === 0 ? (
              <tr><td colSpan={6} className="text-center py-12 text-gray-400">暂无数据</td></tr>
            ) : (
              participants.map((p: any) => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-800">{p.email}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${groupColor(p.group)}`}>{groupLabel(p.group)}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(p.status)}`}>{statusLabel(p.status)}</span>
                  </td>
                  <td className="px-4 py-3 text-center text-sm text-gray-500">{p.created_at ? new Date(p.created_at).toLocaleString('zh-CN') : '-'}</td>
                  <td className="px-4 py-3 text-center">
                    {p.is_abnormal ? <span className="text-red-600 font-bold">!</span> : <span className="text-gray-300">-</span>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => openDetail(p)} className="text-blue-600 hover:underline text-sm">详情</button>
                    <button onClick={() => setDeleteTarget(p)} className="text-red-500 hover:underline text-sm ml-3">删除</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
            <span className="text-sm text-gray-500">共 {total} 条，第 {page}/{totalPages} 页</span>
            <div className="flex gap-1">
              <button onClick={() => loadPage(page - 1)} disabled={page <= 1} className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-40">上一页</button>
              <button onClick={() => loadPage(page + 1)} disabled={page >= totalPages} className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-40">下一页</button>
            </div>
          </div>
        )}
      </div>

      {/* Status Flow Modal */}
      {showStatusFlow && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setShowStatusFlow(false)}>
          <div className="bg-white rounded-2xl max-w-5xl w-full px-6 py-14" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold text-gray-800">参与者状态流程</h2>
              <button onClick={() => setShowStatusFlow(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="flex flex-col md:flex-row items-stretch gap-3 overflow-x-auto">
              {statusFlow.map((s, idx) => (
                <div key={s.key} className="flex items-center gap-3">
                  <div className="flex-1 min-w-[110px] text-center px-3 py-6 rounded-xl border border-gray-200 bg-gray-50">
                    <div className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium mb-2 ${statusColor(s.key)}`}>{s.label}</div>
                    <div className="text-xs text-gray-500 leading-relaxed">{s.desc}</div>
                  </div>
                  {idx < statusFlow.length - 1 && (
                    <>
                      <div className="hidden md:flex text-gray-300 shrink-0">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                      </div>
                      <div className="flex md:hidden justify-center text-gray-300 shrink-0">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selectedUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setSelectedUser(null)}>
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-800">参与者详情</h2>
              <button onClick={() => setSelectedUser(null)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">邮箱</span><span className="text-gray-800 font-medium">{selectedUser.email}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">组别</span><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${groupColor(selectedUser.group)}`}>{groupLabel(selectedUser.group)}</span></div>
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
                    disabled={savingGroup || editGroup === selectedUser.group}
                    className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-40 whitespace-nowrap"
                  >
                    {savingGroup ? '保存中...' : '保存分组'}
                  </button>
                </div>
                <p className="text-xs text-gray-400 mt-2">新分组将在该参与者下次登录后生效（分组信息存于登录令牌中）。</p>
              </div>
              <div className="flex justify-between"><span className="text-gray-500">状态</span><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(selectedUser.status)}`}>{statusLabel(selectedUser.status)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">注册时间</span><span className="text-gray-800">{selectedUser.created_at ? new Date(selectedUser.created_at).toLocaleString('zh-CN') : '-'}</span></div>
              {(demoSource.age != null || demoSource.gender || demoSource.education || demoSource.tech_frequency || demoSource.ai_experience) && (
                <div className="pt-3 border-t border-gray-100">
                  <div className="text-gray-500 mb-2">注册信息</div>
                  <div className="grid grid-cols-2 gap-3 bg-gray-50 rounded-lg p-3 text-xs">
                    <div><span className="text-gray-400">年龄：</span><span className="text-gray-800 font-medium">{demoSource.age ?? '-'}</span></div>
                    <div><span className="text-gray-400">性别：</span><span className="text-gray-800 font-medium">{genderLabel(demoSource.gender)}</span></div>
                    <div><span className="text-gray-400">学历：</span><span className="text-gray-800 font-medium">{educationLabel(demoSource.education)}</span></div>
                    <div><span className="text-gray-400">技术使用频率：</span><span className="text-gray-800 font-medium">{techFrequencyLabel(demoSource.tech_frequency)}</span></div>
                    <div className="col-span-2"><span className="text-gray-400">AI工具使用经验：</span><span className="text-gray-800 font-medium">{aiExperienceLabel(demoSource.ai_experience)}</span></div>
                  </div>
                </div>
              )}
              {selectedUser.task_progress && (
                <div className="pt-3 border-t border-gray-100">
                  <div className="text-gray-500 mb-2">任务进度</div>
                  <div className="grid grid-cols-2 gap-2">
                    {['search', 'document', 'reminder', 'email'].map((t) => (
                      <div key={t} className={`px-3 py-1.5 rounded-lg text-xs text-center ${selectedUser.task_progress[t] ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-400'}`}>
                        {t === 'search' ? '景点搜索' : t === 'document' ? 'Word生成' : t === 'reminder' ? '提醒设置' : '邮件发送'}
                        {selectedUser.task_progress[t] ? ' ✓' : ' ✗'}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 提交物详情（研究员查看实物，需求5.1.1 / 5.2） */}
              {loadingDetail && <div className="pt-3 text-sm text-gray-400">加载详情中...</div>}
              {detail && (
                <>
                  <div className="pt-3 border-t border-gray-100">
                    <div className="text-gray-500 mb-2">行程 Word 文档</div>
                    {detail.submission?.docx_file_name ? (
                      <button
                        onClick={() => downloadParticipantDocx(selectedUser.id)}
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

      {/* Delete Confirm Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setDeleteTarget(null)}>
          <div className="bg-white rounded-2xl max-w-sm w-full p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 flex items-center justify-center shrink-0">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3" /></svg>
              </div>
              <h2 className="text-lg font-bold text-gray-800">删除参与者</h2>
            </div>
            <p className="text-sm text-gray-600 leading-relaxed">
              确定要删除参与者 <span className="font-medium text-gray-800">{deleteTarget.email}</span> 吗？
            </p>
            <p className="text-xs text-red-500 mt-2">
              此操作将同时删除该参与者的全部行为日志、任务提交、提醒、问卷、评分与聊天记录，且不可恢复。
            </p>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setDeleteTarget(null)} disabled={deleting} className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-40">取消</button>
              <button onClick={handleDelete} disabled={deleting} className="px-4 py-2 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 disabled:opacity-50">
                {deleting ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
