import { create } from 'zustand'
import { adminApi } from '../services/api'

interface AdminStore {
  token: string | null
  username: string | null
  loading: boolean
  error: string | null

  login: (username: string, password: string) => Promise<void>
  logout: () => void

  // Data
  dashboardStats: any
  openclawStatus: any
  participants: any[]
  submissions: any[]
  configs: Record<string, string>
  questionnaireItems: any[]

  fetchDashboard: () => Promise<void>
  fetchOpenClaw: () => Promise<void>
  toggleOpenClaw: (paused: boolean) => Promise<void>
  fetchParticipants: (params?: any) => Promise<any>
  fetchSubmissions: () => Promise<void>
  fetchConfigs: () => Promise<void>
  fetchQuestionnaireConfig: () => Promise<void>
  setScore: (userId: string, data: any) => Promise<void>
  updateConfig: (key: string, value: string) => Promise<void>
  updateParticipantGroup: (userId: string, group: string) => Promise<void>
}

export const useAdminStore = create<AdminStore>((set, get) => ({
  token: localStorage.getItem('admin_token'),
  username: localStorage.getItem('admin_username'),
  loading: false,
  error: null,
  dashboardStats: null,
  openclawStatus: null,
  participants: [],
  submissions: [],
  configs: {},
  questionnaireItems: [],

  login: async (username, password) => {
    set({ loading: true, error: null })
    try {
      const res = await adminApi.post('/login', { username, password })
      localStorage.setItem('admin_token', res.data.access_token)
      localStorage.setItem('admin_username', res.data.username)
      set({ token: res.data.access_token, username: res.data.username, loading: false })
    } catch (e: any) {
      set({ loading: false, error: e.response?.data?.detail || '登录失败' })
      throw e
    }
  },

  logout: () => {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_username')
    set({ token: null, username: null, dashboardStats: null, participants: [], submissions: [] })
  },

  fetchDashboard: async () => {
    try {
      const res = await adminApi.get('/dashboard')
      set({ dashboardStats: res.data })
    } catch (e) {
      // ignore
    }
  },

  fetchOpenClaw: async () => {
    try {
      const res = await adminApi.get('/openclaw/status')
      set({ openclawStatus: res.data })
    } catch (e) {
      // ignore
    }
  },

  toggleOpenClaw: async (paused: boolean) => {
    await adminApi.post('/openclaw/toggle', { paused })
    await get().fetchOpenClaw()
  },

  fetchParticipants: async (params) => {
    try {
      const res = await adminApi.get('/participants', { params })
      set({ participants: res.data.participants || [] })
      return res.data
    } catch (e) {
      // ignore
    }
  },

  fetchSubmissions: async () => {
    try {
      const res = await adminApi.get('/submissions')
      set({ submissions: res.data.submissions || [] })
    } catch (e) {
      // ignore
    }
  },

  fetchConfigs: async () => {
    try {
      const res = await adminApi.get('/config')
      set({ configs: res.data })
    } catch (e) {
      // ignore
    }
  },

  fetchQuestionnaireConfig: async () => {
    try {
      const res = await adminApi.get('/questionnaire-config')
      set({ questionnaireItems: res.data })
    } catch (e) {
      // ignore
    }
  },

  setScore: async (userId, data) => {
    await adminApi.post(`/scores/${userId}`, data)
  },

  updateConfig: async (key, value) => {
    await adminApi.put('/config', { key, value })
    await get().fetchConfigs()
  },

  updateParticipantGroup: async (userId, group) => {
    await adminApi.patch(`/participants/${userId}`, { group })
  },
}))
