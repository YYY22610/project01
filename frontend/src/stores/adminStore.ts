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
  fetchParticipantDetail: (userId: string) => Promise<any>
  fetchSubmissions: () => Promise<void>
  fetchConfigs: () => Promise<void>
  fetchQuestionnaireConfig: () => Promise<void>
  setScore: (userId: string, data: any) => Promise<void>
  updateConfig: (key: string, value: string) => Promise<void>
  updateParticipantGroup: (userId: string, group: string) => Promise<void>
  exportData: (format: 'xlsx' | 'csv', group?: string) => Promise<void>
  downloadParticipantDocx: (userId: string) => Promise<void>
  deleteParticipant: (userId: string) => Promise<void>
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

  fetchParticipantDetail: async (userId) => {
    try {
      const res = await adminApi.get(`/participants/${userId}`)
      return res.data
    } catch (e) {
      return null
    }
  },

  exportData: async (format, group) => {
    const params: any = {}
    if (group) params.group = group
    const res = await adminApi.get(
      `/export/all${format === 'xlsx' ? '/xlsx' : ''}`,
      { params, responseType: 'blob' }
    )
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `experiment_data_${new Date().toISOString().slice(0, 10)}.${format === 'xlsx' ? 'xlsx' : 'csv'}`
    a.click()
    URL.revokeObjectURL(url)
  },

  downloadParticipantDocx: async (userId) => {
    const res = await adminApi.get(`/participants/${userId}/docx`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `participant_${userId}.docx`
    a.click()
    URL.revokeObjectURL(url)
  },

  deleteParticipant: async (userId: string) => {
    await adminApi.delete(`/participants/${userId}`)
  },
}))
