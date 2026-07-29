import { useState, useRef, useEffect } from 'react'
import {
  Plus,
  MapPin,
  BedDouble,
  Car,
  Sparkles,
  Send,
  MoreHorizontal,
  Trash2,
  X,
  Notebook,
  Pencil,
  Compass,
  Calendar,
} from 'lucide-react'
import {
  useBoardStore,
  type BoardItem,
  type DayColumnKey,
  type Day,
} from '../stores/boardStore'

type MobilePane = 'pending' | 'day' | 'notes'

const COLUMN_META: Record<
  DayColumnKey,
  { label: string; icon: typeof Car; color: string; promptHint: string; chipBg: string; chipText: string }
> = {
  transport: {
    label: '如何到达',
    icon: Car,
    color: '#3D6B7A',
    promptHint: '例如：地铁 1 号线龙翔桥站',
    chipBg: 'bg-[#E6EEF2]',
    chipText: 'text-[#3D6B7A]',
  },
  activities: {
    label: '玩什么',
    icon: Compass,
    color: '#1F4D3E',
    promptHint: '例如：西湖游船 50 元',
    chipBg: 'bg-[#E1ECE7]',
    chipText: 'text-[#1F4D3E]',
  },
  lodging: {
    label: '住哪里',
    icon: BedDouble,
    color: '#A8523A',
    promptHint: '例如：西湖大华饭店 480 元/晚',
    chipBg: 'bg-[#F3E4DC]',
    chipText: 'text-[#A8523A]',
  },
}

const CATEGORY_GLYPH: Record<NonNullable<BoardItem['category']>, string> = {
  attraction: '✦',
  food: '◍',
  hotel: '☾',
  transport: '→',
  other: '◆',
}

export default function ItineraryBoard() {
  const {
    pending,
    days,
    activeDayId,
    globalNotes,
    aiInput,
    addPending,
    removePending,
    movePendingToDay,
    addCustomToDay,
    removeFromDay,
    setDayTitle,
    setDayNotes,
    setActiveDay,
    setGlobalNotes,
    setAiInput,
    addDay,
    removeDay,
    reset,
  } = useBoardStore()

  const [mobilePane, setMobilePane] = useState<MobilePane>('day')
  const [newPending, setNewPending] = useState('')
  const [addingColumn, setAddingColumn] = useState<DayColumnKey | null>(null)
  const [draftLabel, setDraftLabel] = useState('')
  const [editingTitleId, setEditingTitleId] = useState<string | null>(null)
  const [titleDraft, setTitleDraft] = useState('')

  const activeDay: Day = days.find((d) => d.id === activeDayId) ?? days[0]

  // ============ Handlers ============

  const handleAddPending = () => {
    const t = newPending.trim()
    if (!t) return
    addPending({ title: t, category: 'attraction' })
    setNewPending('')
  }

  const handleMove = (itemId: string, column: DayColumnKey) => {
    movePendingToDay(itemId, activeDay.id, column)
  }

  const handleAddCustom = (column: DayColumnKey) => {
    const t = draftLabel.trim()
    if (!t) return
    addCustomToDay(activeDay.id, column, t)
    setDraftLabel('')
    setAddingColumn(null)
  }

  const beginEditTitle = (day: Day) => {
    setEditingTitleId(day.id)
    setTitleDraft(day.title)
  }
  const commitTitle = () => {
    if (editingTitleId && titleDraft.trim()) {
      setDayTitle(editingTitleId, titleDraft.trim())
    }
    setEditingTitleId(null)
    setTitleDraft('')
  }

  // 拖拽支持（桌面端）
  const onDragStart = (e: React.DragEvent, itemId: string) => {
    e.dataTransfer.setData('text/plain', itemId)
    e.dataTransfer.effectAllowed = 'move'
  }
  const onDropTo = (e: React.DragEvent, column: DayColumnKey) => {
    e.preventDefault()
    const itemId = e.dataTransfer.getData('text/plain')
    if (itemId) handleMove(itemId, column)
  }
  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }

  // 持久化提示
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    setSaved(true)
    const t = setTimeout(() => setSaved(false), 1200)
    return () => clearTimeout(t)
  }, [pending, days, globalNotes, aiInput])

  // ============ Sub Components ============

  const PendingCard = ({ item }: { item: BoardItem }) => {
    const cat = item.category ?? 'other'
    return (
      <div
        draggable
        onDragStart={(e) => onDragStart(e, item.id)}
        className="group relative bg-white/85 backdrop-blur-sm rounded-2xl border border-stone-200/80 shadow-[0_1px_2px_rgba(60,40,20,0.04)] hover:shadow-[0_8px_24px_-8px_rgba(60,40,20,0.18)] hover:-translate-y-0.5 hover:border-stone-300 transition-all duration-200 p-3.5 cursor-grab active:cursor-grabbing"
      >
        <div className="flex items-start gap-3">
          <span
            className="shrink-0 w-8 h-8 rounded-xl flex items-center justify-center text-base bg-[#FAF6EE] text-stone-700 font-serif"
            aria-hidden
          >
            {CATEGORY_GLYPH[cat]}
          </span>
          <div className="min-w-0 flex-1">
            <h4 className="font-semibold text-[15px] text-stone-900 truncate leading-tight">
              {item.title}
            </h4>
            {item.subtitle && (
              <p className="text-xs text-stone-500 mt-0.5 truncate">{item.subtitle}</p>
            )}
          </div>
        </div>
        <div className="mt-3 flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-wider text-stone-400 font-medium">
            拖至「{activeDay.title}」或选择 →
          </span>
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <DropMenu onPick={(col) => handleMove(item.id, col)} />
            <button
              type="button"
              onClick={() => removePending(item.id)}
              className="w-7 h-7 rounded-lg text-stone-400 hover:text-red-600 hover:bg-red-50 flex items-center justify-center transition"
              aria-label="删除"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>
      </div>
    )
  }

  const DayColumn = ({ column }: { column: DayColumnKey }) => {
    const meta = COLUMN_META[column]
    const Icon = meta.icon
    const items = activeDay[column]
    const isAdding = addingColumn === column
    return (
      <div
        onDragOver={onDragOver}
        onDrop={(e) => onDropTo(e, column)}
        className="rounded-2xl border border-stone-200/70 bg-white/60 backdrop-blur-sm transition-colors hover:bg-white/80"
      >
        <div className="flex items-center gap-2 px-3.5 py-2.5 border-b border-stone-100">
          <span
            className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: `${meta.color}15`, color: meta.color }}
          >
            <Icon size={13} />
          </span>
          <h5 className="text-[13px] font-semibold text-stone-800">{meta.label}</h5>
          <span className="ml-auto text-[11px] text-stone-400 font-mono">{items.length}</span>
        </div>
        <div className="p-3 space-y-2 min-h-[64px]">
          {items.map((it) => (
            <div
              key={it.id}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm ${meta.chipBg} ${meta.chipText}`}
            >
              <span className="text-xs font-bold shrink-0">{CATEGORY_GLYPH[it.category ?? 'other']}</span>
              <span className="truncate font-medium flex-1">{it.title}</span>
              <button
                type="button"
                onClick={() => removeFromDay(activeDay.id, column, it.id)}
                className="opacity-50 hover:opacity-100 transition shrink-0"
                aria-label="移除"
              >
                <X size={12} />
              </button>
            </div>
          ))}

          {isAdding ? (
            <div className="rounded-xl border border-stone-300 bg-white p-2 shadow-sm">
              <input
                value={draftLabel}
                onChange={(e) => setDraftLabel(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleAddCustom(column)
                  if (e.key === 'Escape') {
                    setAddingColumn(null)
                    setDraftLabel('')
                  }
                }}
                autoFocus
                placeholder={meta.promptHint}
                className="w-full text-sm px-2 py-1.5 bg-stone-50 rounded-lg outline-none focus:ring-2 focus:ring-stone-400 placeholder:text-stone-400"
              />
              <div className="flex justify-end gap-1.5 mt-1.5">
                <button
                  type="button"
                  onClick={() => {
                    setAddingColumn(null)
                    setDraftLabel('')
                  }}
                  className="px-2.5 py-1 text-xs text-stone-500 hover:bg-stone-100 rounded-md"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={() => handleAddCustom(column)}
                  className="px-2.5 py-1 text-xs bg-stone-900 text-white rounded-md hover:bg-stone-700"
                >
                  添加
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setAddingColumn(column)}
              className="w-full flex items-center justify-center gap-1.5 py-2 rounded-xl text-[13px] text-stone-500 hover:text-stone-800 hover:bg-stone-100 border border-dashed border-stone-300 transition"
            >
              <Plus size={13} /> 添加{meta.label.replace('如何', '').replace('玩什么', '景点').replace('住哪里', '住宿')}
            </button>
          )}
        </div>
      </div>
    )
  }

  const DayCard = () => (
    <div className="bg-white/85 backdrop-blur-md rounded-3xl border border-stone-200/70 shadow-[0_2px_8px_rgba(60,40,20,0.04)] overflow-hidden">
      {/* 顶部彩色细线 — 视觉锚点 */}
      <div className="h-1 bg-gradient-to-r from-[#1F4D3E] via-[#3D6B7A] to-[#A8523A]" />

      <div className="p-5 space-y-4">
        {/* 标题行 */}
        <div className="flex items-center gap-2">
          {editingTitleId === activeDay.id ? (
            <input
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={commitTitle}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitTitle()
                if (e.key === 'Escape') {
                  setEditingTitleId(null)
                  setTitleDraft('')
                }
              }}
              autoFocus
              className="text-base font-bold text-stone-900 bg-stone-50 px-2 py-1 rounded-lg outline-none focus:ring-2 focus:ring-[#1F4D3E]/40 min-w-0 flex-1"
            />
          ) : (
            <h3
              onClick={() => beginEditTitle(activeDay)}
              className="text-base font-bold text-stone-900 cursor-text hover:bg-stone-50 px-2 py-1 -mx-2 rounded-lg transition group inline-flex items-center gap-1.5"
              title="点击编辑标题"
            >
              {activeDay.title}
              <Pencil size={12} className="text-stone-400 opacity-0 group-hover:opacity-100 transition" />
            </h3>
          )}
          <button
            type="button"
            className="ml-auto w-7 h-7 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-100 flex items-center justify-center"
            aria-label="更多"
          >
            <MoreHorizontal size={15} />
          </button>
        </div>

        {/* 天数切换 tab */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 -mx-1 px-1">
          {days.map((d) => (
            <button
              key={d.id}
              type="button"
              onClick={() => setActiveDay(d.id)}
              className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition ${
                d.id === activeDay.id
                  ? 'bg-[#1F4D3E] text-white shadow-sm'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
              }`}
            >
              {d.title}
            </button>
          ))}
          <button
            type="button"
            onClick={addDay}
            className="shrink-0 w-7 h-7 rounded-full border border-dashed border-stone-300 text-stone-500 hover:border-stone-500 hover:text-stone-800 flex items-center justify-center"
            aria-label="新增一天"
            title="新增一天"
          >
            <Plus size={13} />
          </button>
          {days.length > 1 && (
            <button
              type="button"
              onClick={() => removeDay(activeDay.id)}
              className="shrink-0 w-7 h-7 rounded-full text-stone-400 hover:text-red-600 hover:bg-red-50 flex items-center justify-center ml-1"
              aria-label="删除当天"
              title="删除当天"
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>

        {/* 添加备注 */}
        <div className="text-[11px] uppercase tracking-wider text-stone-400 font-semibold">添加备注</div>
        <textarea
          value={activeDay.dayNotes}
          onChange={(e) => setDayNotes(activeDay.id, e.target.value)}
          placeholder="这一天的小提醒，比如几点起床、几点集合…"
          rows={2}
          className="w-full text-sm px-3.5 py-2.5 bg-stone-50 border border-stone-200 rounded-xl outline-none focus:ring-2 focus:ring-[#1F4D3E]/40 focus:border-[#1F4D3E]/40 resize-none placeholder:text-stone-400 transition"
        />

        {/* 三个分类列 */}
        <div className="space-y-2">
          <DayColumn column="transport" />
          <DayColumn column="activities" />
          <DayColumn column="lodging" />
        </div>
      </div>
    </div>
  )

  const PendingColumn = () => (
    <div className="bg-white/85 backdrop-blur-md rounded-3xl border border-stone-200/70 shadow-[0_2px_8px_rgba(60,40,20,0.04)] overflow-hidden">
      <div className="h-1 bg-gradient-to-r from-[#3D6B7A] to-[#7FB0BF]" />

      <div className="p-5 space-y-4">
        <div className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-[#E6EEF2] text-[#3D6B7A] flex items-center justify-center">
            <MapPin size={14} />
          </span>
          <h3 className="text-base font-bold text-stone-900">待安排</h3>
          <span className="ml-auto text-[11px] text-stone-400 font-mono">{pending.length}</span>
          <button
            type="button"
            className="w-7 h-7 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-100 flex items-center justify-center"
            aria-label="更多"
          >
            <MoreHorizontal size={15} />
          </button>
        </div>

        {/* 添加地点 */}
        <div className="flex items-center gap-2 bg-stone-100 rounded-full px-4 py-2 focus-within:ring-2 focus-within:ring-[#3D6B7A]/40 focus-within:bg-white transition">
          <Plus size={15} className="text-[#3D6B7A] shrink-0" />
          <input
            value={newPending}
            onChange={(e) => setNewPending(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddPending()}
            placeholder="添加待安排的地点…"
            className="flex-1 bg-transparent border-0 outline-none text-sm text-stone-800 placeholder:text-stone-400"
          />
        </div>

        {/* 地点列表 */}
        <div className="space-y-2 max-h-[640px] overflow-y-auto pr-1 -mr-1">
          {pending.length === 0 && (
            <p className="text-xs text-stone-400 text-center py-6">还没有待安排的地点</p>
          )}
          {pending.map((it) => (
            <PendingCard key={it.id} item={it} />
          ))}
        </div>
      </div>
    </div>
  )

  const NotesColumn = () => (
    <div className="bg-white/85 backdrop-blur-md rounded-3xl border border-stone-200/70 shadow-[0_2px_8px_rgba(60,40,20,0.04)] overflow-hidden">
      <div className="h-1 bg-gradient-to-r from-[#A8523A] to-[#E07A35]" />

      <div className="p-5 space-y-4">
        <div className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-[#F3E4DC] text-[#A8523A] flex items-center justify-center">
            <Notebook size={14} />
          </span>
          <h3 className="text-base font-bold text-stone-900">备注</h3>
          <button
            type="button"
            className="ml-auto w-7 h-7 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-100 flex items-center justify-center"
            aria-label="更多"
          >
            <MoreHorizontal size={15} />
          </button>
        </div>

        <p className="text-[11px] text-stone-500 leading-relaxed">
          在这里记录你的想法、计划、关注的信息…
        </p>

        <textarea
          value={globalNotes}
          onChange={(e) => setGlobalNotes(e.target.value)}
          placeholder="例如：提前订门票、带充电宝、需带学生证…"
          rows={10}
          className="w-full text-sm leading-relaxed px-3.5 py-3 bg-stone-50 border border-stone-200 rounded-xl outline-none focus:ring-2 focus:ring-[#A8523A]/40 focus:border-[#A8523A]/40 resize-none placeholder:text-stone-400 transition"
        />

        <div className="flex items-center justify-between pt-2 border-t border-stone-100">
          <span className="text-[11px] text-stone-400 font-mono">{globalNotes.length} 字</span>
          <button
            type="button"
            onClick={() => setGlobalNotes('')}
            className="text-[11px] text-stone-500 hover:text-red-600 transition"
          >
            清空
          </button>
        </div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen w-full text-stone-900 font-sans antialiased">
      {/* 全局背景：温暖象牙白 + 微妙渐变 + 噪点纹理 — 拒绝纯白纯灰 */}
      <div
        aria-hidden
        className="fixed inset-0 -z-10"
        style={{
          background:
            'radial-gradient(1200px 600px at 10% -10%, #F2E8D5 0%, transparent 60%), radial-gradient(900px 500px at 100% 0%, #E8DEC6 0%, transparent 55%), radial-gradient(800px 400px at 50% 100%, #EDE0CB 0%, transparent 55%), #FAF6EE',
        }}
      />
      <div
        aria-hidden
        className="fixed inset-0 -z-10 opacity-[0.035] mix-blend-multiply pointer-events-none"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.15 0 0 0 0 0.10 0 0 0 0 0.05 0 0 0 0.7 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>\")",
          backgroundSize: '160px 160px',
        }}
      />

      {/* 顶部 Hero */}
      <header className="px-5 lg:px-10 pt-6 pb-3">
        <div className="max-w-[1400px] mx-auto flex items-end justify-between gap-6 flex-wrap">
          <div className="flex items-end gap-5">
            <div className="flex items-center gap-1 pb-1">
              <button className="relative px-1 pb-2 text-[15px] font-semibold text-stone-900">
                行程详情
                <span className="absolute -bottom-0 left-0 right-0 h-[2px] bg-stone-900" />
              </button>
              <button className="px-1 pb-2 text-[15px] font-medium text-stone-400 hover:text-stone-700 transition ml-3">
                旅行灵感
              </button>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-3 text-xs text-stone-500">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/70 border border-stone-200/80">
              <Calendar size={12} /> 杭州 · 3 日
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/70 border border-stone-200/80">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              {saved ? '已自动保存' : '草稿'}
            </span>
            <button
              type="button"
              onClick={() => {
                if (confirm('重置所有数据？')) reset()
              }}
              className="px-2.5 py-1 rounded-full text-stone-500 hover:text-red-600 hover:bg-red-50 transition"
              title="重置"
            >
              重置
            </button>
          </div>
        </div>

        {/* 记忆点：超大衬线 + 中文错位 */}
        <div className="max-w-[1400px] mx-auto mt-6 lg:mt-10 mb-2">
          <h1 className="font-serif text-stone-900 leading-[0.9] tracking-tight">
            <span className="block text-[14vw] md:text-[88px] lg:text-[112px] font-light italic">
              Itinerary
            </span>
            <span className="block text-[20px] md:text-[26px] lg:text-[30px] font-semibold text-stone-700 mt-1 -ml-0.5">
              你的杭州三日手账
              <span className="text-stone-400 font-normal ml-2 text-[14px] md:text-[16px]">
                · 拖动卡片即可安排
              </span>
            </span>
          </h1>
        </div>
      </header>

      {/* 移动端分段控件 — Tab 切换三列 */}
      <div className="lg:hidden px-5 pt-2">
        <div className="flex bg-stone-100 rounded-full p-1 text-sm">
          <MobileTab pane="pending" current={mobilePane} onPick={setMobilePane} label="待安排" count={pending.length} color="#3D6B7A" />
          <MobileTab pane="day" current={mobilePane} onPick={setMobilePane} label={activeDay.title} count={activeDay.activities.length + activeDay.transport.length + activeDay.lodging.length} color="#1F4D3E" />
          <MobileTab pane="notes" current={mobilePane} onPick={setMobilePane} label="备注" count={globalNotes.length > 0 ? 1 : 0} color="#A8523A" />
        </div>
      </div>

      {/* 三栏看板 */}
      <main className="px-5 lg:px-10 pt-5 lg:pt-8 pb-44">
        <div className="max-w-[1400px] mx-auto grid gap-5 lg:gap-6 grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)_320px]">
          <div className={mobilePane === 'pending' ? 'block' : 'hidden lg:block'}>
            <PendingColumn />
          </div>
          <div className={mobilePane === 'day' ? 'block' : 'hidden lg:block'}>
            <DayCard />
          </div>
          <div className={mobilePane === 'notes' ? 'block' : 'hidden lg:block'}>
            <NotesColumn />
          </div>
        </div>
      </main>

      {/* 底部固定 AI 输入框 */}
      <div className="fixed bottom-4 left-4 right-4 lg:left-1/2 lg:-translate-x-1/2 lg:max-w-[640px] z-30">
        <div className="bg-white/90 backdrop-blur-xl rounded-2xl border border-stone-200 shadow-[0_12px_40px_-12px_rgba(60,40,20,0.25)] px-4 py-3 flex items-center gap-3">
          <Sparkles size={16} className="text-[#E07A35] shrink-0" />
          <input
            value={aiInput}
            onChange={(e) => setAiInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && aiInput.trim()) {
                alert(`（示例）AI 已收到你的问题：「${aiInput}」\n实际接入 LLM 后会真正回复。`)
                setAiInput('')
              }
            }}
            placeholder="任何旅游相关的问题都可以问我哦"
            className="flex-1 bg-transparent outline-none text-sm text-stone-800 placeholder:text-stone-400"
            aria-label="AI 助手输入"
          />
          <button
            type="button"
            onClick={() => {
              if (!aiInput.trim()) return
              alert(`（示例）AI 已收到你的问题：「${aiInput}」`)
              setAiInput('')
            }}
            className="w-9 h-9 rounded-full bg-stone-900 text-white flex items-center justify-center hover:bg-stone-700 disabled:opacity-40 transition shrink-0"
            aria-label="发送"
            disabled={!aiInput.trim()}
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}

// ==================== Sub: DropMenu (移动待安排卡片到指定列) ====================

function DropMenu({ onPick }: { onPick: (col: DayColumnKey) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-7 h-7 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-100 flex items-center justify-center transition"
        aria-label="添加到…"
        title="添加到…"
      >
        <Plus size={13} />
      </button>
      {open && (
        <div className="absolute right-0 top-8 z-20 bg-white rounded-xl shadow-xl border border-stone-200 py-1 min-w-[120px]">
          {(Object.keys(COLUMN_META) as DayColumnKey[]).map((k) => {
            const meta = COLUMN_META[k]
            return (
              <button
                key={k}
                type="button"
                onClick={() => {
                  onPick(k)
                  setOpen(false)
                }}
                className="w-full text-left px-3 py-1.5 text-xs hover:bg-stone-50 flex items-center gap-2"
              >
                <meta.icon size={12} style={{ color: meta.color }} />
                {meta.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ==================== Sub: MobileTab ====================

function MobileTab({
  pane,
  current,
  onPick,
  label,
  count,
  color,
}: {
  pane: MobilePane
  current: MobilePane
  onPick: (p: MobilePane) => void
  label: string
  count: number
  color: string
}) {
  const active = pane === current
  return (
    <button
      type="button"
      onClick={() => onPick(pane)}
      className={`relative flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full transition font-medium ${
        active ? 'bg-white shadow-sm text-stone-900' : 'text-stone-500'
      }`}
    >
      <span
        className="w-2 h-2 rounded-full"
        style={{ backgroundColor: active ? color : '#D6D3D1' }}
      />
      <span className="text-[13px]">{label}</span>
      {count > 0 && (
        <span
          className={`min-w-[18px] h-[18px] px-1 text-[10px] font-bold rounded-full flex items-center justify-center ${
            active ? 'text-white' : 'text-stone-500 bg-stone-200'
          }`}
          style={active ? { backgroundColor: color } : undefined}
        >
          {count}
        </span>
      )}
    </button>
  )
}