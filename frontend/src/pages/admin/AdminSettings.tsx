import { useEffect, useState } from 'react'
import { useAdminStore } from '../../stores/adminStore'

export default function AdminSettings() {
  const { fetchConfigs, configs, updateConfig } = useAdminStore()
  const [form, setForm] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    fetchConfigs()
  }, [])

  useEffect(() => {
    setForm({ ...configs })
  }, [configs])

  const configItems = [
    {
      key: 'experiment_status',
      label: '实验状态',
      type: 'select',
      options: [{ value: 'running', label: '运行中' }, { value: 'stopped', label: '已停止' }],
      description: '控制实验是否对外可参与',
    },
    {
      key: 'target_sample_size',
      label: '目标样本量',
      type: 'number',
      description: '三组总目标人数，按 1:1:1 分配',
    },
    {
      key: 'task_days',
      label: '行程天数 (N日)',
      type: 'number',
      description: '规划旅行的天数',
    },
    {
      key: 'task_budget',
      label: '预算金额 (M元)',
      type: 'number',
      description: '旅行规划预算',
    },
    {
      key: 'destination',
      label: '目的地',
      type: 'text',
      description: '旅行规划目的地',
    },
    {
      key: 'target_email',
      label: '收件邮箱',
      type: 'email',
      description: '子任务4邮件发送的目标邮箱',
    },
    {
      key: 'smtp_host',
      label: 'SMTP 服务器',
      type: 'text',
      description: '邮件发送SMTP服务器地址',
    },
    {
      key: 'search_api_key',
      label: '搜索API Key',
      type: 'password',
      description: '必应/Google搜索API密钥',
    },
    {
      key: 'llm_api_key',
      label: 'LLM API Key',
      type: 'password',
      description: '大语言模型API密钥',
    },
  ]

  const handleSave = async (key: string) => {
    setSaving(key)
    try {
      await updateConfig(key, form[key] || '')
      alert('保存成功')
    } catch {
      alert('保存失败')
    } finally {
      setSaving(null)
    }
  }

  const renderInput = (item: typeof configItems[0]) => {
    const value = form[item.key] || ''

    if (item.type === 'select') {
      return (
        <select
          value={value}
          onChange={(e) => setForm({ ...form, [item.key]: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
        >
          {item.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      )
    }

    return (
      <input
        type={item.type}
        value={value}
        onChange={(e) => setForm({ ...form, [item.key]: e.target.value })}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
        placeholder={item.label}
      />
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">系统配置</h1>

      {/* Experiment Control */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">实验控制</h2>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">实验状态</label>
            <select
              value={form['experiment_status'] || 'stopped'}
              onChange={(e) => setForm({ ...form, experiment_status: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="running">运行中</option>
              <option value="stopped">已停止</option>
            </select>
          </div>
          <button
            onClick={() => handleSave('experiment_status')}
            disabled={saving === 'experiment_status'}
            className="mt-6 px-6 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {saving === 'experiment_status' ? '保存中...' : '应用'}
          </button>
        </div>
      </div>

      {/* Task Parameters */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">任务参数</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {configItems.filter(i => ['task_days', 'task_budget', 'destination', 'target_email'].includes(i.key)).map((item) => (
            <div key={item.key}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{item.label}</label>
              {renderInput(item)}
              <div className="text-xs text-gray-400 mt-1">{item.description}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Sample Size */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">样本量设置</h2>
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">目标样本量</label>
            <input
              type="number"
              value={form['target_sample_size'] || '100'}
              onChange={(e) => setForm({ ...form, target_sample_size: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
            <div className="text-xs text-gray-400 mt-1">三组共 {form['target_sample_size'] || 100} 人，每组 {Math.ceil(parseInt(form['target_sample_size'] || '100') / 3)} 人</div>
          </div>
          <button
            onClick={() => handleSave('target_sample_size')}
            disabled={saving === 'target_sample_size'}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {saving === 'target_sample_size' ? '保存中...' : '保存'}
          </button>
        </div>
      </div>

      {/* API Configuration */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">API 配置</h2>
        <div className="space-y-4">
          {configItems.filter(i => ['smtp_host', 'search_api_key', 'llm_api_key'].includes(i.key)).map((item) => (
            <div key={item.key} className="flex items-end gap-3">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">{item.label}</label>
                {renderInput(item)}
                <div className="text-xs text-gray-400 mt-1">{item.description}</div>
              </div>
              <button
                onClick={() => handleSave(item.key)}
                disabled={saving === item.key}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 disabled:opacity-50 whitespace-nowrap"
              >
                {saving === item.key ? '...' : '保存'}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Danger Zone */}
      <div className="bg-red-50 rounded-xl p-6 border border-red-200">
        <h2 className="text-lg font-semibold text-red-800 mb-2">危险操作</h2>
        <p className="text-sm text-red-600 mb-4">以下操作不可逆，请谨慎执行</p>
        <div className="flex gap-3">
          <button
            onClick={() => { if (confirm('确认重置所有实验数据？此操作不可逆！')) alert('请联系系统管理员执行') }}
            className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700"
          >
            重置实验数据
          </button>
          <button
            onClick={() => { if (confirm('确认导出全部数据为 Excel？')) window.open('/api/admin/export/all/xlsx') }}
            className="px-4 py-2 bg-gray-600 text-white rounded-lg text-sm hover:bg-gray-700"
          >
            导出全部数据 (Excel)
          </button>
        </div>
      </div>
    </div>
  )
}
