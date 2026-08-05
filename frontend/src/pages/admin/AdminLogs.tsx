import { useEffect, useState, Fragment } from 'react'
import { adminApi } from '../../services/api'

export default function AdminLogs() {
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const [selectedLog, setSelectedLog] = useState<any>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [expandedUsers, setExpandedUsers] = useState<Set<string>>(new Set())
  const [userPage, setUserPage] = useState(1)
  // 一次性拉取足够多的日志，让前端可以按用户全局折叠（当前 656 条，10000 为安全上限）
  const pageSize = 10000
  const usersPerPage = 20

  const userKey = (log: any) => log.user_email || log.user_id || '未知用户'

  const groupedLogs = logs.reduce((acc, log) => {
    const key = userKey(log)
    if (!acc[key]) acc[key] = []
    acc[key].push(log)
    return acc
  }, {} as Record<string, any[]>)

  const groupedUsers = Object.keys(groupedLogs)

  const toggleUser = (key: string) => {
    setExpandedUsers((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const actionTypes = [
    'page_view', 'search_query', 'search_result_click', 'document_edit', 'document_save',
    'reminder_set', 'email_send', 'agent_message', 'agent_tool_call', 'task_submit',
    'task_start', 'demo_view', 'questionnaire_submit',
  ]

  useEffect(() => {
    loadLogs(1)
  }, [actionFilter])

  const loadLogs = async (p: number) => {
    setLoading(true)
    setPage(p)
    setUserPage(1)
    try {
      const res = await adminApi.get('/logs', {
        params: { page: p, page_size: pageSize, search, action_type: actionFilter }
      })
      setLogs(res.data.logs || [])
      setTotal(res.data.total || 0)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => loadLogs(1)

  const totalPages = Math.ceil(total / pageSize)

  // 按用户分页（折叠态每页显示 usersPerPage 位用户）
  const userTotalPages = Math.ceil(groupedUsers.length / usersPerPage)
  const displayedUsers = groupedUsers.slice((userPage - 1) * usersPerPage, userPage * usersPerPage)

  const actionColor = (a: string) => {
    if (a === 'error') return 'bg-red-100 text-red-700'
    if (a === 'task_submit' || a === 'questionnaire_submit') return 'bg-green-100 text-green-700'
    if (a === 'agent_message' || a === 'agent_tool_call') return 'bg-purple-100 text-purple-700'
    return 'bg-gray-100 text-gray-600'
  }

  const successBadge = (s: any) => {
    if (s === true) return <span className="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">成功</span>
    if (s === false) return <span className="px-2 py-0.5 rounded-full text-xs bg-red-100 text-red-700">失败</span>
    return <span className="text-xs text-gray-400">—</span>
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-800">行为日志</h1>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm p-4 flex flex-wrap gap-3 items-center">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="搜索邮箱或内容..."
          className="flex-1 min-w-[200px] px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
        />
        <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
          <option value="">全部操作</option>
          {actionTypes.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <button onClick={handleSearch} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">搜索</button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="text-center py-12 text-gray-400">加载中...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                <tr>
                  <th className="px-4 py-3 text-left">时间</th>
                  <th className="px-4 py-3 text-left">用户</th>
                  <th className="px-4 py-3 text-center">操作类型</th>
                  <th className="px-4 py-3 text-left">阶段</th>
                  <th className="px-4 py-3 text-left">延迟(ms)</th>
                  <th className="px-4 py-3 text-center">成败</th>
                  <th className="px-4 py-3 text-left">摘要</th>
                  <th className="px-4 py-3 text-center">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {logs.length === 0 ? (
                  <tr><td colSpan={8} className="text-center py-12 text-gray-400">暂无日志</td></tr>
                ) : (
                  displayedUsers.map((user) => {
                    const userLogs = groupedLogs[user]
                    const expanded = expandedUsers.has(user)
                    return (
                      <Fragment key={user}>
                        <tr className="bg-gray-50 hover:bg-gray-100 cursor-pointer transition" onClick={() => toggleUser(user)}>
                          <td className="px-4 py-3 text-sm" colSpan={8}>
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <span className="text-gray-800 font-medium">{user}</span>
                                <span className="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700">{userLogs.length} 条日志</span>
                                <span className="text-xs text-gray-400">最近：{new Date(userLogs[0].timestamp).toLocaleString('zh-CN')}</span>
                              </div>
                              <span className="text-xs text-blue-600 font-medium">{expanded ? '收起 ▲' : '展开 ▼'}</span>
                            </div>
                          </td>
                        </tr>
                        {expanded && userLogs.map((log: any) => (
                          <tr key={log.id} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">{new Date(log.timestamp).toLocaleString('zh-CN')}</td>
                            <td className="px-4 py-3 text-sm text-gray-800">{log.user_email || log.user_id}</td>
                            <td className="px-4 py-3 text-center">
                              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${actionColor(log.action_type)}`}>{log.action_type}</span>
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">{log.phase || '-'}</td>
                            <td className="px-4 py-3 text-sm text-gray-600">{log.request_latency_ms ?? '-'}</td>
                            <td className="px-4 py-3 text-center">{successBadge(log.is_success)}</td>
                            <td className="px-4 py-3 text-sm text-gray-600 max-w-xs truncate">{log.action_target || log.input_content || '-'}</td>
                            <td className="px-4 py-3 text-center">
                              <button onClick={(e) => { e.stopPropagation(); setSelectedLog(log) }} className="text-blue-600 hover:underline text-sm">详情</button>
                            </td>
                          </tr>
                        ))}
                      </Fragment>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination：按用户分页 */}
        {userTotalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
            <span className="text-sm text-gray-500">
              共 {groupedUsers.length} 位用户 / {total} 条日志，第 {userPage}/{userTotalPages} 页
            </span>
            <div className="flex gap-1">
              <button onClick={() => setUserPage((p) => Math.max(1, p - 1))} disabled={userPage <= 1} className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-40">上一页</button>
              <button onClick={() => setUserPage((p) => Math.min(userTotalPages, p + 1))} disabled={userPage >= userTotalPages} className="px-3 py-1 text-sm border border-gray-300 rounded disabled:opacity-40">下一页</button>
            </div>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setSelectedLog(null)}>
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-800">日志详情</h2>
              <button onClick={() => setSelectedLog(null)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div><span className="text-gray-500">日志ID:</span> <span className="text-gray-800">{selectedLog.id}</span></div>
                <div><span className="text-gray-500">时间:</span> <span className="text-gray-800">{new Date(selectedLog.timestamp).toLocaleString('zh-CN')}</span></div>
                <div><span className="text-gray-500">用户:</span> <span className="text-gray-800">{selectedLog.user_email || selectedLog.user_id}</span></div>
                <div><span className="text-gray-500">操作类型:</span> <span className="text-gray-800">{selectedLog.action_type}</span></div>
                <div><span className="text-gray-500">阶段:</span> <span className="text-gray-800">{selectedLog.phase || '-'}</span></div>
                <div><span className="text-gray-500">成败:</span> <span className="text-gray-800">{selectedLog.is_success === true ? '成功' : selectedLog.is_success === false ? '失败' : '-'}</span></div>
                {selectedLog.agent_id && <div><span className="text-gray-500">助理ID:</span> <span className="text-gray-800">{selectedLog.agent_id}</span></div>}
                {selectedLog.request_latency_ms != null && <div><span className="text-gray-500">延迟:</span> <span className="text-gray-800">{selectedLog.request_latency_ms} ms</span></div>}
                {selectedLog.results_viewed != null && <div><span className="text-gray-500">查看结果数:</span> <span className="text-gray-800">{selectedLog.results_viewed}</span></div>}
                {selectedLog.clicked_item_id && <div><span className="text-gray-500">点击项:</span> <span className="text-gray-800">{selectedLog.clicked_item_id}</span></div>}
                {selectedLog.user_action_on_ai && <div><span className="text-gray-500">对AI动作:</span> <span className="text-gray-800">{selectedLog.user_action_on_ai}</span></div>}
                {selectedLog.manual_edit_count != null && <div><span className="text-gray-500">手动编辑次数:</span> <span className="text-gray-800">{selectedLog.manual_edit_count}</span></div>}
                {selectedLog.ai_interaction_rounds != null && <div><span className="text-gray-500">AI交互轮次:</span> <span className="text-gray-800">{selectedLog.ai_interaction_rounds}</span></div>}
                {selectedLog.final_plan_submit_time && <div><span className="text-gray-500">方案提交时间:</span> <span className="text-gray-800">{new Date(selectedLog.final_plan_submit_time).toLocaleString('zh-CN')}</span></div>}
                {selectedLog.session_id && <div><span className="text-gray-500">会话ID:</span> <span className="text-gray-800 font-mono text-xs">{selectedLog.session_id}</span></div>}
                {selectedLog.error_detail && <div className="col-span-2"><span className="text-gray-500">错误详情:</span> <span className="text-red-600">{selectedLog.error_detail}</span></div>}
              </div>
              {selectedLog.action_target && (
                <div>
                  <div className="text-gray-500 mb-1">操作摘要</div>
                  <div className="bg-gray-50 rounded-lg p-3 text-gray-700">{selectedLog.action_target}</div>
                </div>
              )}
              {selectedLog.input_content && (
                <div>
                  <div className="text-gray-500 mb-1">输入内容</div>
                  <pre className="bg-gray-50 rounded-lg p-3 text-xs text-gray-700 overflow-auto max-h-40">{typeof selectedLog.input_content === 'string' ? selectedLog.input_content : JSON.stringify(selectedLog.input_content, null, 2)}</pre>
                </div>
              )}
              {selectedLog.ai_response && (
                <div>
                  <div className="text-gray-500 mb-1">AI返回</div>
                  <pre className="bg-gray-50 rounded-lg p-3 text-xs text-gray-700 overflow-auto max-h-40">{typeof selectedLog.ai_response === 'string' ? selectedLog.ai_response : JSON.stringify(selectedLog.ai_response, null, 2)}</pre>
                </div>
              )}
              {selectedLog.extra_data && (
                <div>
                  <div className="text-gray-500 mb-1">扩展数据</div>
                  <pre className="bg-gray-50 rounded-lg p-3 text-xs text-gray-700 overflow-auto max-h-40">{JSON.stringify(selectedLog.extra_data, null, 2)}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
