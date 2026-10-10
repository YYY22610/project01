import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { FileDown, Loader2, Sparkles } from 'lucide-react'
import type { GroupPlan, GroupContext } from '../../hooks/useGroupChat'
import { normalizeMarkdown, stripTagMarkers, plainText } from '../../utils/markdown'

interface Props {
  plan: GroupPlan | null
  /** 临时规划（讨论中实时汇总，六项要素 + days_draft 草案） */
  tempPlan: Record<string, any> | null
  /** 用户是否已确认最终方案（done 后为 true，右侧栏切换） */
  planConfirmed: boolean
  /** 任务上下文（用于临时规划阶段从配置填充 meta 等） */
  ctx: GroupContext
  exporting: boolean
  onExportWord: () => void
}

// 临时规划字段 → 六项要素展示配置（已废弃：临时规划与最终方案走同 CardView，此配置仅作日志参考）

/**
 * 六项要素（交通/住宿/餐饮/预算）的内容来自 LLM，里面常带 Markdown 标记：
 * **加粗** 小标题、## 分节标题、有序列表等。早期版本按纯文本渲染，
 * 导致 ** 和 ## 直接裸露在卡片里，这里统一走 Markdown 渲染。
 * 归一化逻辑见 utils/markdown（与 ChatWindow 共用同一份实现）。
 */
function MdBlock({ children, className = '' }: { children: string; className?: string }) {
  return (
    <div className={`markdown-content text-[13px] leading-relaxed text-gray-700 ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizeMarkdown(children)}</ReactMarkdown>
    </div>
  )
}

function MetaCard({ icon, label, value }: { icon: string; label: string; value?: string }) {
  return (
    <div className="bg-white rounded-2xl border border-blue-100 px-4 py-3 shadow-sm flex-1 min-w-[40%]">
      <div className="text-[11px] text-gray-500 mb-1">{icon} {label}</div>
      <div className="text-base font-semibold text-gray-900 truncate">{value || '—'}</div>
    </div>
  )
}

function DayCard({ index, day }: { index: number; day: any }) {
  const title = day?.title || `Day ${index}`
  const tag = day?.tag || ''
  const items: any[] = day?.items || []
  return (
    <div className="rounded-xl overflow-hidden border border-blue-100 shadow-sm" style={{ background: 'linear-gradient(to right, #eff6ff 0%, #f5faff 4%, #ffffff 12%)' }}>
      {/* 顶部标题条：左标题 + 右 tag */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-blue-50">
        <h3 className="text-sm font-bold text-gray-900">Day {index} · {title}</h3>
        {tag && (
          <span className="text-[11px] font-medium text-blue-600 bg-white border border-blue-100 rounded-full px-2.5 py-0.5 shadow-sm">
            {tag}
          </span>
        )}
      </div>
      {/* 行程列表：时段蓝色加粗 + 内容 */}
      {items.length === 0 ? (
        <p className="text-xs text-gray-400 px-4 py-3">⏳ 暂无安排</p>
      ) : (
        <ul className="px-4 py-2.5 space-y-1.5">
          {items.map((it, i) => (
            <li key={i} className="text-[13px] text-gray-700 leading-relaxed">
              <span className="text-blue-600 font-semibold mr-1.5">{it?.time || '-'}</span>
              <span>{it?.text || '-'}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// 将临时规划（文本行 list）拼为与最终方案相同结构的 data，供 CardView 渲染
function tempPlanToData(tempPlan: Record<string, any> | null, ctx: GroupContext) {
  const tp = tempPlan || {}
  // meta: 从任务上下文推一个半成品（具体风格等整合后才有，给一个直觉占位）
  const meta = {
    travelers: ctx.travelers || '1 人',
    total: `¥${ctx.budget}`,
    style: '⏳ 主持人整合',
    pace: '⏳ 主持人整合',
  }
  // days: 主持人已在讨论中排好草案（days_draft JSON 字符串），优先展示；否则 3 张占位
  let draftDays: any[] = []
  if (tp.days_draft) {
    try {
      const parsed = JSON.parse(tp.days_draft)
      if (Array.isArray(parsed)) draftDays = parsed
    } catch { /* 忽略解析失败，走占位 */ }
  }
  const days = draftDays.length > 0
    ? draftDays
    : Array.from({ length: ctx.days || 3 }, (_, i) => ({
        tag: '',
        title: `Day ${i + 1}`,
        items: [{ time: '—', text: '⏳ 讨论结束后由主持人整合生成完整行程' }],
      }))
  // spots: 临时规划时 list of strings；最终方案时 [{name, stay, fee}]
  const spots = ((tp.spots as string[]) || []).map((s) => ({ name: s, stay: '—', fee: '—' }))
  // 4 段：list of strings 直接当文本行
  const listToVal = (v: string[] | string | undefined) => v && v.length > 0 ? v : undefined
  return {
    meta,
    days,
    spots,
    transport: listToVal(tp.transport),
    lodging: listToVal(tp.lodging),
    dining: listToVal(tp.dining),
    budget: listToVal(tp.budget),
  }
}

/**
 * 后端用 【标签】 划分六项要素（见 services 的 _parse_tagged），这些标记对
 * 前端渲染毫无意义，却会原样出现在「团队讨论摘要」里（摘要取的是角色发言原文）。
 * 展示前剥掉；若剥完该段只剩标签，则整段丢弃，避免留下空条目。
 *
 * stripTagMarkers / plainText 已提取到 utils/markdown，与 ChatWindow 共用同一份实现。
 */

function FinalCardView({ data, markdown, quotes }: { data: any; markdown?: string; quotes?: any[] }) {
  // 无结构化数据 → 降级渲染 markdown
  if (!data || !data.days || data.days.length === 0) {
    if (markdown) {
      return (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <div className="markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizeMarkdown(markdown)}</ReactMarkdown>
          </div>
        </div>
      )
    }
    return null
  }
  const meta = data.meta || {}
  return (
    <div className="space-y-4">
      {/* 每日行程 */}
      <section>
        <h2 className="text-base font-bold text-gray-900 mb-2">每日行程</h2>
        <div className="space-y-3">
          {data.days.map((d: any, i: number) => (
            <DayCard key={i} index={i + 1} day={d} />
          ))}
        </div>
      </section>

      {/* 景点游览 / 交通 / 住宿 / 餐饮 / 预算 */}
      {data.spots && data.spots.length > 0 && (
        <section className="bg-white rounded-2xl border border-blue-100 shadow-sm p-4">
          <h3 className="text-sm font-bold text-gray-900 mb-2">🏞️ （二）景点游览方案</h3>
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-gray-500 border-b">
                <th className="text-left py-1 pr-2">#</th>
                <th className="text-left py-1 pr-2">景点</th>
                <th className="text-left py-1 pr-2">停留</th>
                <th className="text-left py-1">门票</th>
              </tr>
            </thead>
            <tbody>
              {data.spots.map((s: any, i: number) => (
                <tr key={i} className="border-b last:border-b-0">
                  <td className="py-1 pr-2 text-gray-500">{i + 1}</td>
                  <td className="py-1 pr-2 text-gray-800">{plainText(String(s?.name ?? ''))}</td>
                  <td className="py-1 pr-2 text-gray-600">{s?.stay}</td>
                  <td className="py-1 text-gray-600">{s?.fee}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {(['transport', 'lodging', 'dining', 'budget'] as const).map((k) => {
        const v = (data as any)[k]
        if (!v) return null
        const titleMap = { transport: '🚇 （三）交通方式', lodging: '🏨 （四）住宿选择', dining: '🍜 （五）餐饮安排', budget: '💰 （六）预算明细' } as const
        return (
          <section key={k} className="bg-white rounded-2xl border border-blue-100 shadow-sm p-4">
            <h3 className="text-sm font-bold text-gray-900 mb-2">{titleMap[k]}</h3>
            {Array.isArray(v) ? (
              <ul className="space-y-1.5">
                {v.map((it: any, i: number) => (
                  <li key={i} className="pl-2 border-l-2 border-blue-200">
                    <MdBlock>{String(it ?? '')}</MdBlock>
                  </li>
                ))}
              </ul>
            ) : (
              <MdBlock>{String(v)}</MdBlock>
            )}
          </section>
        )
      })}

      {/* 团队摘要（金句） */}
      {quotes && quotes.length > 0 && (
        <section className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
          <h3 className="text-base font-bold text-gray-900 mb-3">团队讨论摘要</h3>
          <div className="space-y-2.5">
            {quotes.map((q, i) => (
              <div
                key={i}
                className="pl-3 py-2 rounded-lg bg-gray-50"
                style={{ borderLeft: `3px solid ${q.color}` }}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span>{q.emoji}</span>
                  <span className="text-xs font-semibold" style={{ color: q.color }}>{q.name}</span>
                </div>
                <MdBlock className="text-gray-600">{stripTagMarkers(String(q.text ?? ''))}</MdBlock>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

export default function PlanDisplay({ plan, tempPlan, planConfirmed, ctx, exporting, onExportWord }: Props) {
  // 已确认 → 最终方案；否则 → 临时规划（讨论中实时汇总，与最终方案同卡片样式）
  const showFinal = planConfirmed && !!plan

  // 合并数据：临时规划阶段用 tempPlan + 任务配置拼出"半成品 data"，与最终方案卡片样式一致
  const viewData = showFinal && plan?.data
    ? plan.data
    : tempPlanToData(tempPlan, ctx)
  const viewMarkdown = showFinal ? plan?.markdown : undefined
  const viewQuotes = showFinal ? plan?.quotes : undefined

  return (
    <div className="flex flex-col h-full bg-[#f4f8fd]">
      {/* 头部 */}
      <div className="h-14 px-4 bg-white border-b border-gray-100 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-1.5 text-base font-semibold text-gray-900">
          <Sparkles size={17} className="text-blue-600" /> {showFinal ? '最终方案' : '临时规划'}
        </div>
        <button
          onClick={onExportWord}
          disabled={!plan || exporting}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded-lg px-3 py-1.5 hover:bg-blue-100 disabled:opacity-50 transition"
        >
          {exporting ? <Loader2 size={14} className="animate-spin" /> : <FileDown size={14} />}
          导出 Word
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <FinalCardView data={viewData} markdown={viewMarkdown} quotes={viewQuotes} />
      </div>
    </div>
  )
}