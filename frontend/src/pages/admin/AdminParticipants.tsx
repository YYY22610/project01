import { useEffect, useState } from 'react'
import { useAdminStore } from '../../stores/adminStore'

export default function AdminParticipants() {
  const { fetchParticipants, participants, updateParticipantGroup } = useAdminStore()
  const [search, setSearch] = useState('')
  const [groupFilter, setGroupFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [selectedUser, setSelectedUser] = useState<any>(null)
  const [editGroup, setEditGroup] = useState<string>('')
  const [savingGroup, setSavingGroup] = useState(false)
  const pageSize = 20

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
      alert('分组已更新')
      setSelectedUser({ ...selectedUser, group: editGroup })
      loadPage(page)
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
              <th className="px-4 py-3 text-center">状态</th>
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
                  <td className="px-4 py-3 text-center text-sm text-gray-600">{p.status}</td>
                  <td className="px-4 py-3 text-center text-sm text-gray-500">{p.created_at ? new Date(p.created_at).toLocaleString('zh-CN') : '-'}</td>
                  <td className="px-4 py-3 text-center">
                    {p.is_abnormal ? <span className="text-red-600 font-bold">!</span> : <span className="text-gray-300">-</span>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => setSelectedUser(p)} className="text-blue-600 hover:underline text-sm">详情</button>
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
              <div className="flex justify-between"><span className="text-gray-500">状态</span><span className="text-gray-800">{selectedUser.status}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">注册时间</span><span className="text-gray-800">{selectedUser.created_at ? new Date(selectedUser.created_at).toLocaleString('zh-CN') : '-'}</span></div>
              {selectedUser.demographics && (
                <div className="pt-3 border-t border-gray-100">
                  <div className="text-gray-500 mb-2">基本信息</div>
                  <pre className="bg-gray-50 rounded-lg p-3 text-xs text-gray-700 overflow-auto">{JSON.stringify(selectedUser.demographics, null, 2)}</pre>
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
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
