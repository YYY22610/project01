import { useChatStore } from '../stores/chatStore'

interface ExecutionLogProps {
  agentId: string
}

export default function ExecutionLog({ agentId }: ExecutionLogProps) {
  const toolActivity = useChatStore((s) => s.toolActivity[agentId] || [])

  if (toolActivity.length === 0) return null

  const toolLabels: Record<string, string> = {
    search_attractions: '搜索景点',
    generate_docx: '生成文档',
    calculate_budget: '计算预算',
    set_reminder: '设置提醒',
    send_email: '发送邮件',
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 mt-3">
      <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">执行日志</h4>
      <div className="space-y-2 max-h-40 overflow-y-auto">
        {toolActivity.map((act, i) => (
          <div key={i} className="flex items-start gap-2 text-xs">
            <span className="text-gray-400">{new Date(act.timestamp).toLocaleTimeString('zh-CN')}</span>
            <span className="text-blue-600 font-medium">{toolLabels[act.tool] || act.tool}</span>
            {act.result && (
              <span className="text-green-600">✓ 完成</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
