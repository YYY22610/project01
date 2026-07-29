import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import { useUserStore } from './stores/userStore'
import { useBehaviorLogger } from './hooks/useBehaviorLogger'

// Pages
import Register from './pages/Register'
import Consent from './pages/Consent'
import Demo from './pages/Demo'
import Task from './pages/Task'
import Questionnaire from './pages/Questionnaire'
import Complete from './pages/Complete'
import ItineraryBoard from './pages/ItineraryBoard'

// Admin pages
import AdminLogin from './pages/admin/AdminLogin'
import AdminLayout from './pages/admin/AdminLayout'
import AdminDashboard from './pages/admin/AdminDashboard'
import AdminParticipants from './pages/admin/AdminParticipants'
import AdminSubmissions from './pages/admin/AdminSubmissions'
import AdminQuestionnaire from './pages/admin/AdminQuestionnaire'
import AdminLogs from './pages/admin/AdminLogs'
import AdminSettings from './pages/admin/AdminSettings'

// Route guard
function RequireAuth({ children }: { children: JSX.Element }) {
  const token = useUserStore((s) => s.token)
  const user = useUserStore((s) => s.user)
  const location = useLocation()

  if (!token) {
    return <Navigate to="/register" state={{ from: location }} replace />
  }

  // Route guards based on status
  if (user) {
    const status = user.status
    const path = location.pathname

    if (path === '/consent' && status !== 'registered') {
      return <Navigate to="/demo" replace />
    }
    if (path === '/demo' && status === 'registered') {
      return <Navigate to="/consent" replace />
    }
    if (path === '/task' && !['demo_completed', 'task_in_progress', 'task_completed'].includes(status)) {
      return <Navigate to="/demo" replace />
    }
    if (path === '/questionnaire' && status !== 'task_completed') {
      return <Navigate to="/task" replace />
    }
    if (path === '/complete' && status !== 'questionnaire_completed') {
      return <Navigate to="/questionnaire" replace />
    }
  }

  return children
}

function AppRoutes() {
  const { log, start, stop } = useBehaviorLogger()
  const token = useUserStore((s) => s.token)

  useEffect(() => {
    if (token) {
      start()
      log({ action_type: 'page_view', action_target: window.location.pathname })
    }
    return () => stop()
  }, [token])

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/register" element={<Register />} />

      {/* Protected routes */}
      <Route path="/consent" element={<RequireAuth><Consent /></RequireAuth>} />
      <Route path="/demo" element={<RequireAuth><Demo /></RequireAuth>} />
      <Route path="/task" element={<RequireAuth><Task /></RequireAuth>} />
      <Route path="/questionnaire" element={<RequireAuth><Questionnaire /></RequireAuth>} />
      <Route path="/complete" element={<RequireAuth><Complete /></RequireAuth>} />

      {/* 新版行程看板（独立预览页面 — 参考携程 AI 行程助手） */}
      <Route path="/itinerary" element={<ItineraryBoard />} />

      {/* Admin routes */}
      <Route path="/admin/login" element={<AdminLogin />} />
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Navigate to="/admin/dashboard" replace />} />
        <Route path="dashboard" element={<AdminDashboard />} />
        <Route path="participants" element={<AdminParticipants />} />
        <Route path="submissions" element={<AdminSubmissions />} />
        <Route path="questionnaire" element={<AdminQuestionnaire />} />
        <Route path="logs" element={<AdminLogs />} />
        <Route path="settings" element={<AdminSettings />} />
      </Route>

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/register" replace />} />
      <Route path="*" element={<Navigate to="/register" replace />} />
    </Routes>
  )
}

export default function App() {
  const token = useUserStore((s) => s.token)
  const fetchMe = useUserStore((s) => s.fetchMe)

  useEffect(() => {
    if (token && !useUserStore.getState().user) {
      fetchMe()
    }
  }, [token])

  return <AppRoutes />
}
