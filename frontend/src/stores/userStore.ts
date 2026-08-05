import { create } from 'zustand'
import type { User, TaskConfig, TaskStatus } from '../types'
import { authApi, taskApi } from '../services'
import { useChatStore } from './chatStore'

/** 解析 JWT payload（无需验证签名，仅用于读取 group/status） */
function parseJwt(token: string): Record<string, any> | null {
  try {
    const base64Url = token.split('.')[1]
    if (!base64Url) return null
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join(''),
    )
    return JSON.parse(json)
  } catch {
    return null
  }
}

interface UserStore {
  user: User | null
  token: string | null
  taskConfig: TaskConfig | null
  taskStatus: TaskStatus | null
  loading: boolean
  error: string | null

  // Actions
  register: (email: string) => Promise<void>
  login: (email: string, password: string) => Promise<void>
  loginByEmail: (email: string) => Promise<void>
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

  register: async (email) => {
    set({ loading: true, error: null })
    try {
      const res = await authApi.register(email)
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

  loginByEmail: async (email) => {
    set({ loading: true, error: null })
    try {
      const res = await authApi.loginByEmail(email)
      const token = res.data.access_token
      const payload = parseJwt(token)
      const newGroup = payload?.group as string | undefined
      const lastGroup = localStorage.getItem('last_group')

      // 先以新身份落盘 token，确保即便后续 reset 异常，用户也已切换为 10 身份
      localStorage.setItem('access_token', token)
      localStorage.setItem('last_group', newGroup || '')
      set({ token, loading: false })

      // 每次重新登录都开启新的 AI 会话：同一用户重登也是全新聊天记录
      useChatStore.getState().startNewSession()

      // 若管理员修改过分组，重置实验流程让参与者从头再来（用新 token 重置当前登录用户）
      if (lastGroup && newGroup && lastGroup !== newGroup) {
        try {
          await taskApi.reset()
        } catch {
          // 重置失败不影响登录主流程，用户仍以新身份进入
        }
      }

      await get().fetchMe()
    } catch (e: any) {
      set({ loading: false, error: e.response?.data?.detail || '登录失败' })
      throw e
    }
  },

  logout: () => {
    localStorage.removeItem('access_token')
    // 清空聊天记录（含本地持久化），避免不同参与者共用浏览器时串号看到彼此对话
    try {
      useChatStore.getState().resetAll()
      useChatStore.persist.clearStorage()
    } catch {
      // 忽略持久化异常，不影响登出主流程
    }
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
