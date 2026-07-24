import { create } from 'zustand'
import type { User, TaskConfig, TaskStatus } from '../types'
import { authApi, taskApi } from '../services'

interface UserStore {
  user: User | null
  token: string | null
  taskConfig: TaskConfig | null
  taskStatus: TaskStatus | null
  loading: boolean
  error: string | null

  // Actions
  register: (email: string, password: string) => Promise<void>
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  consent: () => Promise<void>
  updateDemographics: (data: any) => Promise<void>
  fetchMe: () => Promise<void>
  fetchTaskConfig: () => Promise<void>
  fetchTaskStatus: () => Promise<void>
  completeDemo: (watchSeconds?: number) => Promise<void>
  startTask: () => Promise<void>
  submitTask: (data: any) => Promise<void>
  setToken: (token: string) => void
}

export const useUserStore = create<UserStore>((set, get) => ({
  user: null,
  token: localStorage.getItem('access_token'),
  taskConfig: null,
  taskStatus: null,
  loading: false,
  error: null,

  setToken: (token) => {
    localStorage.setItem('access_token', token)
    set({ token })
  },

  register: async (email, password) => {
    set({ loading: true, error: null })
    try {
      const res = await authApi.register(email, password)
      localStorage.setItem('access_token', res.data.access_token)
      set({ token: res.data.access_token, loading: false })
      await get().fetchMe()
    } catch (e: any) {
      set({ loading: false, error: e.response?.data?.detail || '注册失败' })
      throw e
    }
  },

  login: async (email, password) => {
    set({ loading: true, error: null })
    try {
      const res = await authApi.login(email, password)
      localStorage.setItem('access_token', res.data.access_token)
      set({ token: res.data.access_token, loading: false })
      await get().fetchMe()
    } catch (e: any) {
      set({ loading: false, error: e.response?.data?.detail || '登录失败' })
      throw e
    }
  },

  logout: () => {
    localStorage.removeItem('access_token')
    set({ user: null, token: null, taskConfig: null, taskStatus: null })
  },

  consent: async () => {
    set({ loading: true, error: null })
    try {
      const res = await authApi.consent()
      if (res.data?.access_token) {
        localStorage.setItem('access_token', res.data.access_token)
        set({ token: res.data.access_token })
      }
      await get().fetchMe()
      set({ loading: false })
    } catch (e: any) {
      set({ loading: false, error: e.response?.data?.detail || '操作失败' })
      throw e
    }
  },

  updateDemographics: async (data) => {
    set({ loading: true, error: null })
    try {
      await authApi.demographics(data)
      await get().fetchMe()
      set({ loading: false })
    } catch (e: any) {
      set({ loading: false, error: e.response?.data?.detail || '操作失败' })
      throw e
    }
  },

  fetchMe: async () => {
    try {
      const res = await authApi.me()
      set({ user: res.data })
    } catch (e) {
      // Not logged in
    }
  },

  fetchTaskConfig: async () => {
    try {
      const res = await taskApi.config()
      set({ taskConfig: res.data })
    } catch (e) {
      // ignore
    }
  },

  fetchTaskStatus: async () => {
    try {
      const res = await taskApi.status()
      set({ taskStatus: res.data })
    } catch (e) {
      // ignore
    }
  },

  completeDemo: async (watchSeconds?: number) => {
    try {
      await taskApi.demoComplete(watchSeconds)
      await get().fetchMe()
    } catch (e: any) {
      set({ error: e.response?.data?.detail || '操作失败' })
      throw e
    }
  },

  startTask: async () => {
    set({ loading: true, error: null })
    try {
      await taskApi.start()
      await get().fetchTaskStatus()
      await get().fetchMe()
      set({ loading: false })
    } catch (e: any) {
      set({ loading: false, error: e.response?.data?.detail || '操作失败' })
      throw e
    }
  },

  submitTask: async (data) => {
    set({ loading: true, error: null })
    try {
      await taskApi.submit(data)
      await get().fetchTaskStatus()
      await get().fetchMe()
      set({ loading: false })
    } catch (e: any) {
      set({ loading: false, error: e.response?.data?.detail || '提交失败' })
      throw e
    }
  },
}))
