import { useEffect, useMemo, useState } from 'react'
import { useAdminStore } from '../../stores/adminStore'
import { adminApi } from '../../services/api'
import {
  CONSTRUCT_OPTIONS,
  PHASE_OPTIONS,
  TYPE_OPTIONS,
  constructLabel,
  phaseLabel,
  typeLabel,
} from '../../constants/questionnaire'

interface AdminItem {
  id?: string
  construct: string
  text: string
  type: string
  /** 单选/多选为 string[]；双极量表为 {left, right} */
  options?: string[] | { left: string; right: string } | null
  scale_level?: number
  sort_order?: number
  is_active?: boolean
  applicable_groups?: string | null
  phase?: 'pre' | 'post'
  is_reverse?: boolean
  section_note?: string | null
}

const isAnchors = (o: AdminItem['options']): o is { left: string; right: string } =>
  !!o && !Array.isArray(o) && typeof (o as any).left === 'string'

export default function AdminQuestionnaire() {
  const { fetchQuestionnaireConfig, questionnaireItems } = useAdminStore()
  const [editing, setEditing] = useState<AdminItem | null>(null)
  const [creating, setCreating] = useState(false)
  const [phaseFilter, setPhaseFilter] = useState<'all' | 'pre' | 'post'>('all')

  useEffect(() => {
    fetchQuestionnaireConfig()
  }, [])

  const items = questionnaireItems as AdminItem[]

  const visible = useMemo(() => {
    const filtered = phaseFilter === 'all'
      ? items
      : items.filter((it) => (it.phase || 'post') === phaseFilter)
    return [...filtered].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
  }, [items, phaseFilter])

  const handleSave = async (form: AdminItem) => {
    try {
      const payload = {
        construct: form.construct,
        text: form.text,
        type: form.type,
        // 双极量表必须把锚点一起提交，否则参与者看不到左右端词
        options: isAnchors(form.options)
          ? { left: form.options.left, right: form.options.right }
          : Array.isArray(form.options) && form.options.length > 0
            ? form.options
            : null,
        scale_level: form.type === 'likert7' ? 7 : 5,
        sort_order: form.sort_order ?? 0,
        is_active: form.is_active ?? true,
        applicable_groups: form.applicable_groups ?? 'ALL',
        phase: form.phase ?? 'post',
        is_reverse: form.is_reverse ?? false,
        section_note: form.section_note ?? null,
      }
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
    if (!confirm('确认删除该题项？该题的所有作答记录会一并删除（ON DELETE CASCADE）。')) return
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
        <div className="flex items-center gap-3">
          <select
            value={phaseFilter}
            onChange={(e) => setPhaseFilter(e.target.value as 'all' | 'pre' | 'post')}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
          >
            <option value="all">全部阶段</option>
            {PHASE_OPTIONS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          <button
            onClick={() => setCreating(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
            添加题项
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="px-4 py-3 text-left">阶段</th>
              <th className="px-4 py-3 text-left">题号</th>
              <th className="px-4 py-3 text-left">构念</th>
              <th className="px-4 py-3 text-left">题目</th>
              <th className="px-4 py-3 text-center">类型</th>
              <th className="px-4 py-3 text-center">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {visible.length === 0 ? (
              <tr><td colSpan={6} className="text-center py-12 text-gray-400">暂无题项</td></tr>
            ) : (
              visible.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      (item.phase || 'post') === 'pre'
                        ? 'bg-purple-50 text-purple-600'
                        : 'bg-gray-100 text-gray-600'
                    }`}>
                      {phaseLabel(item.phase || 'post')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    Q{String(item.sort_order ?? 0).padStart(2, '0')}
                    {item.is_reverse && (
                      <span className="ml-1 px-1.5 py-0.5 bg-amber-50 text-amber-600 rounded text-xs">反</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{constructLabel(item.construct) || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-800">
                    {item.section_note && (
                      <div className="text-xs text-gray-400 mb-1 border-l-2 border-blue-200 pl-2">
                        指导语：{item.section_note}
                      </div>
                    )}
                    {item.text}
                  </td>
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
          item={editing || { construct: '', text: '', type: 'likert5', options: [], phase: phaseFilter === 'pre' ? 'pre' : 'post' }}
          onSave={handleSave}
          onClose={() => { setEditing(null); setCreating(false) }}
        />
      )}
    </div>
  )
}

function QuestionnaireEditor({ item, onSave, onClose }: { item: AdminItem; onSave: (item: AdminItem) => void; onClose: () => void }) {
  const [form, setForm] = useState<AdminItem>({ ...item })

  const needsOptions = form.type === 'single_choice' || form.type === 'multiple_choice'
  const needsAnchors = form.type === 'bipolar5'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-gray-800 mb-4">{item.id ? '编辑题项' : '添加题项'}</h2>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">阶段</label>
              <select
                value={form.phase || 'post'}
                onChange={(e) => setForm({ ...form, phase: e.target.value as 'pre' | 'post' })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                {PHASE_OPTIONS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">题号（排序）</label>
              <input
                type="number"
                value={form.sort_order ?? 0}
                onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
            </div>
          </div>
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
              onChange={(e) => setForm({
                ...form,
                type: e.target.value,
                options: e.target.value === 'bipolar5'
                  ? (isAnchors(form.options) ? form.options : { left: '', right: '' })
                  : [],
              })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              {TYPE_OPTIONS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          {needsOptions && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">选项（每行一个）</label>
              <textarea
                value={(Array.isArray(form.options) ? form.options : []).join('\n')}
                onChange={(e) => setForm({ ...form, options: e.target.value.split('\n').filter(Boolean) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                rows={4}
                placeholder="选项A&#10;选项B&#10;选项C"
              />
            </div>
          )}
          {needsAnchors && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">左端锚点（1 分）</label>
                <input
                  value={isAnchors(form.options) ? form.options.left : ''}
                  onChange={(e) => setForm({
                    ...form,
                    options: {
                      left: e.target.value,
                      right: isAnchors(form.options) ? form.options.right : '',
                    },
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  placeholder="如：忧郁"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">右端锚点（5 分）</label>
                <input
                  value={isAnchors(form.options) ? form.options.right : ''}
                  onChange={(e) => setForm({
                    ...form,
                    options: {
                      left: isAnchors(form.options) ? form.options.left : '',
                      right: e.target.value,
                    },
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  placeholder="如：满足"
                />
              </div>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              题组指导语（选填，仅题组首题填写）
            </label>
            <textarea
              value={form.section_note ?? ''}
              onChange={(e) => setForm({ ...form, section_note: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              rows={2}
              placeholder="如：以下题目测量您对……（1=非常不同意，2=不同意……）"
            />
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_reverse ?? false}
              onChange={(e) => setForm({ ...form, is_reverse: e.target.checked })}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700">反向计分题（导出聚合时按 量表级数+1-原始分 翻转）</span>
          </label>
        </div>
        <div className="flex gap-2 mt-6">
          <button onClick={() => onSave(form)} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">保存</button>
          <button onClick={onClose} className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm hover:bg-gray-300">取消</button>
        </div>
      </div>
    </div>
  )
}
