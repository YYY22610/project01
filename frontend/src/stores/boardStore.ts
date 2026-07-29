import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// ==================== Types ====================

export type BoardItem = {
  id: string
  title: string
  subtitle?: string
  category?: 'attraction' | 'food' | 'hotel' | 'transport' | 'other'
  note?: string
}

export type DayColumnKey = 'transport' | 'activities' | 'lodging'

export type Day = {
  id: string
  title: string
  dayNotes: string
  transport: BoardItem[]
  activities: BoardItem[]
  lodging: BoardItem[]
}

interface BoardState {
  pending: BoardItem[]
  days: Day[]
  activeDayId: string
  globalNotes: string
  aiInput: string

  // 待安排操作
  addPending: (item: Omit<BoardItem, 'id'>) => void
  removePending: (id: string) => void

  // 每天的子项操作
  movePendingToDay: (itemId: string, dayId: string, column: DayColumnKey) => void
  addCustomToDay: (dayId: string, column: DayColumnKey, label: string) => void
  removeFromDay: (dayId: string, column: DayColumnKey, itemId: string) => void

  // 每天的标题与备注
  setDayTitle: (dayId: string, title: string) => void
  setDayNotes: (dayId: string, notes: string) => void

  // 切换当前展示的天
  setActiveDay: (dayId: string) => void

  // 全局备注
  setGlobalNotes: (notes: string) => void

  // AI 输入
  setAiInput: (input: string) => void

  // 天数管理
  addDay: () => void
  removeDay: (dayId: string) => void

  reset: () => void
}

// ==================== Initial Seed ====================

const seedPending: BoardItem[] = [
  { id: 'p-1', title: '西湖', subtitle: '世界文化遗产 · 5A 景区', category: 'attraction' },
  { id: 'p-2', title: '灵隐寺', subtitle: '千年古刹 · 飞来峰造像', category: 'attraction' },
  { id: 'p-3', title: '雷峰塔', subtitle: '黄晓明版白蛇传取景地', category: 'attraction' },
  { id: 'p-4', title: '西溪国家湿地公园', subtitle: '城中次生湿地', category: 'attraction' },
  { id: 'p-5', title: '河坊街', subtitle: '南宋御街 · 特色小吃', category: 'food' },
  { id: 'p-6', title: '楼外楼（孤山路店）', subtitle: '百年老字号 · 西湖醋鱼', category: 'food' },
]

const seedDays: Day[] = [
  {
    id: 'day-1',
    title: '第1天',
    dayNotes: '抵达杭州，先去西湖边的断桥走走，感受一下「断桥残雪」的意境。',
    transport: [],
    activities: [],
    lodging: [],
  },
  {
    id: 'day-2',
    title: '第2天',
    dayNotes: '',
    transport: [],
    activities: [],
    lodging: [],
  },
  {
    id: 'day-3',
    title: '第3天',
    dayNotes: '',
    transport: [],
    activities: [],
    lodging: [],
  },
]

const initialState = {
  pending: seedPending,
  days: seedDays,
  activeDayId: 'day-1',
  globalNotes: '',
  aiInput: '',
}

// ==================== Helpers ====================

const uid = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`

// ==================== Store ====================

export const useBoardStore = create<BoardState>()(
  persist(
    (set) => ({
      ...initialState,

      addPending: (item) =>
        set((s) => ({
          pending: [...s.pending, { id: uid(), ...item }],
        })),

      removePending: (id) =>
        set((s) => ({
          pending: s.pending.filter((it) => it.id !== id),
        })),

      movePendingToDay: (itemId, dayId, column) =>
        set((s) => {
          const item = s.pending.find((it) => it.id === itemId)
          if (!item) return s
          return {
            pending: s.pending.filter((it) => it.id !== itemId),
            days: s.days.map((d) =>
              d.id === dayId ? { ...d, [column]: [...d[column], item] } : d,
            ),
          }
        }),

      addCustomToDay: (dayId, column, label) =>
        set((s) => ({
          days: s.days.map((d) =>
            d.id === dayId
              ? {
                  ...d,
                  [column]: [...d[column], { id: uid(), title: label, category: column === 'lodging' ? 'hotel' : column === 'transport' ? 'transport' : 'other' }],
                }
              : d,
          ),
        })),

      removeFromDay: (dayId, column, itemId) =>
        set((s) => ({
          days: s.days.map((d) =>
            d.id === dayId ? { ...d, [column]: d[column].filter((it) => it.id !== itemId) } : d,
          ),
        })),

      setDayTitle: (dayId, title) =>
        set((s) => ({
          days: s.days.map((d) => (d.id === dayId ? { ...d, title } : d)),
        })),

      setDayNotes: (dayId, dayNotes) =>
        set((s) => ({
          days: s.days.map((d) => (d.id === dayId ? { ...d, dayNotes } : d)),
        })),

      setActiveDay: (activeDayId) => set({ activeDayId }),

      setGlobalNotes: (globalNotes) => set({ globalNotes }),

      setAiInput: (aiInput) => set({ aiInput }),

      addDay: () =>
        set((s) => {
          const n = s.days.length + 1
          return {
            days: [
              ...s.days,
              { id: `day-${uid()}`, title: `第${n}天`, dayNotes: '', transport: [], activities: [], lodging: [] },
            ],
          }
        }),

      removeDay: (dayId) =>
        set((s) => {
          if (s.days.length <= 1) return s
          const remaining = s.days.filter((d) => d.id !== dayId)
          const nextActive = s.activeDayId === dayId ? remaining[0]?.id ?? '' : s.activeDayId
          return { days: remaining, activeDayId: nextActive }
        }),

      reset: () => set({ ...initialState, days: [...seedDays], pending: [...seedPending] }),
    }),
    { name: 'itinerary-board-v1' },
  ),
)