import { useEffect, useState } from 'react'
import { useAdminStore } from '../../stores/adminStore'
import { adminApi } from '../../services/api'
import {
  CONSTRUCT_OPTIONS,
  TYPE_OPTIONS,
  constructLabel,
  typeLabel,
} from '../../constants/questionnaire'

interface QuestionnaireItem {
  id?: string
  construct: string
  text: string
  type: string
  options?: string[]
  scale_level?: number
  sort_order?: number
  is_active?: boolean
  applicable_groups?: string
}

export default function AdminQuestionnaire() {
  const { fetchQuestionnaireConfig, questionnaireItems } = useAdminStore()
  const [editing, setEditing] = useState<QuestionnaireItem | null>(null)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    fetchQuestionnaireConfig()
  }, [])

  const toBackendPayload = (form: QuestionnaireItem) => {
    const scaleLevel = form.type === 'likert7' ? 7 : 5
    return {
      construct: form.construct,
      text: form.text,
      type: form.type,
      options: form.options && form.options.length > 0 ? form.options : null,
      scale_level: scaleLevel,
      sort_order: form.sort_order ?? 0,
      is_active: form.is_active ?? true,
      applicable_groups: form.applicable_groups ?? 'ALL',
    }
  }

  const handleSave = async (form: QuestionnaireItem) => {
    try {
      const payload = toBackendPayload(form)
      if (form.id) {
        await adminApi.put(`/questionnaire-config/${form.id}`, payload)
      } else {
        await adminApi.post('/questionnaire-config', payload)
      }
      setEditing(null)
      setCreating(false)
      await fetchQuestionnaireConfig()
      alert('保存成功')
    } catch (e: any) {
      const detail = e.response?.data?.detail
      console.error('保存题项失败', e.response?.data || e)
      alert(detail ? `保存失败：${detail}` : '保存失败')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除该题项？')) return
    try {
      await adminApi.delete(`/questionnaire-config/${id}`)
      await fetchQuestionnaireConfig()
    } catch (e: any) {
      const detail = e.response?.data?.detail
      alert(detail ? `删除失败：${detail}` : '删除失败')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">问卷配置</h1>
        <button
          onClick={() => setCreating(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
          添加题项
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="px-4 py-3 text-left">序号</th>
              <th className="px-4 py-3 text-left">构念</th>
              <th className="px-4 py-3 text-left">题目</th>
              <th className="px-4 py-3 text-center">类型</th>
              <th className="px-4 py-3 text-center">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {questionnaireItems.length === 0 ? (
              <tr><td colSpan={5} className="text-center py-12 text-gray-400">暂无题项</td></tr>
            ) : (
              questionnaireItems.map((item: QuestionnaireItem, i: number) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-500">{i + 1}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{constructLabel(item.construct) || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-800">{item.text}</td>
                  <td className="px-4 py-3 text-center">
                    <span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">{typeLabel(item.type)}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => setEditing(item)} className="text-blue-600 hover:underline text-sm mr-3">编辑</button>
                    <button onClick={() => item.id && handleDelete(item.id)} className="text-red-600 hover:underline text-sm">删除</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Edit/Create Modal */}
      {(editing || creating) && (
        <QuestionnaireEditor
          item={editing || { construct: '', text: '', type: 'likert5', options: [] }}
          onSave={handleSave}
          onClose={() => { setEditing(null); setCreating(false) }}
        />
      )}
    </div>
  )
}

function QuestionnaireEditor({ item, onSave, onClose }: { item: QuestionnaireItem; onSave: (item: QuestionnaireItem) => void; onClose: () => void }) {
  const [form, setForm] = useState<QuestionnaireItem>({ ...item })

  const needsOptions = form.type === 'single_choice' || form.type === 'multiple_choice'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-gray-800 mb-4">{item.id ? '编辑题项' : '添加题项'}</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">构念</label>
            <select
              value={form.construct}
              onChange={(e) => setForm({ ...form, construct: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="">请选择</option>
              {CONSTRUCT_OPTIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">题目文本</label>
            <textarea
              value={form.text}
              onChange={(e) => setForm({ ...form, text: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              rows={3}
              placeholder="输入题目内容..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">题目类型</label>
            <select
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value, options: [] })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              {TYPE_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          {needsOptions && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">选项（每行一个）</label>
              <textarea
                value={(form.options || []).join('\n')}
                onChange={(e) => setForm({ ...form, options: e.target.value.split('\n').filter(Boolean) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                rows={4}
                placeholder="选项A&#10;选项B&#10;选项C"
              />
            </div>
          )}
        </div>
        <div className="flex gap-2 mt-6">
          <button onClick={() => onSave(form)} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">保存</button>
          <button onClick={onClose} className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm hover:bg-gray-300">取消</button>
        </div>
      </div>
    </div>
  )
}
