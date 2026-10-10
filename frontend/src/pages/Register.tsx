import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../stores/userStore'

export default function Register() {
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const { register, loginByEmail, loading } = useUserStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!email.trim()) {
      setError('请输入邮箱')
      return
    }

    try {
      if (isLogin) {
        // 邮箱直登（实验平台免密登录）
        await loginByEmail(email)
        // 登录后根据当前实验状态跳转：registered → /consent（新合并页），其他 → 继续后续流程
        const status = useUserStore.getState().user?.status
        if (status === 'registered') {
          navigate('/consent')
        } else {
          navigate('/demo')
        }
      } else {
        // 注册：仅邮箱（基本信息将在「知情同意」页统一收集）
        await register(email)
        navigate('/consent')
      }
    } catch (e: any) {
      const detail = e.response?.data?.detail
      if (detail) {
        // 双向智能引导：邮箱已注册则引导去登录，未注册则引导去注册
        if (!isLogin && detail.includes('已注册')) {
          setError('该邮箱已注册，请使用下方「去登录」以已有账号进入')
          setIsLogin(true)
          setEmail(email)
          return
        }
        if (isLogin && detail.includes('未注册')) {
          setError('该邮箱尚未注册，请使用「去注册」创建账号')
          setIsLogin(false)
          setEmail(email)
          return
        }
        setError(detail)
      } else if (e.code === 'ERR_NETWORK' || !e.response) {
        setError('无法连接到服务器，请检查网络连接后重试')
      } else {
        setError(isLogin ? '登录失败，请稍后重试' : '注册失败，请稍后重试')
      }
    }
  }

  const fieldCls =
    'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
  const labelCls = 'block text-sm font-medium text-gray-700 mb-1'

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-blue-100 px-4 py-8">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gray-800">
            {isLogin ? '邮箱登录' : '注册账号'}
          </h1>
          <p className="text-gray-500 mt-2">参与旅行规划实验研究</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={labelCls}>邮箱</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className={fieldCls}
              placeholder="请输入邮箱"
            />
          </div>

          <p className="text-xs text-gray-500 leading-relaxed">
            实验平台支持免密登录，仅需输入注册邮箱即可进入。
            登录后将进入「知情同意与基本信息」页面，请完整填写后再开始任务。
          </p>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition"
          >
            {loading ? (isLogin ? '登录中...' : '注册中...') : (isLogin ? '登录' : '注册')}
          </button>

          <p className="text-center text-sm text-gray-500 mt-3">
            {isLogin ? (
              <>
                还没有账号？
                <button
                  type="button"
                  onClick={() => { setIsLogin(false); setError('') }}
                  className="text-blue-600 hover:underline ml-1"
                >
                  去注册
                </button>
              </>
            ) : (
              <>
                已有账号？
                <button
                  type="button"
                  onClick={() => { setIsLogin(true); setError('') }}
                  className="text-blue-600 hover:underline ml-1"
                >
                  去登录
                </button>
              </>
            )}
          </p>

          <p className="text-center text-sm text-gray-500">
            <a href="/admin/login" className="text-blue-600 hover:underline">管理员入口</a>
          </p>
        </form>
      </div>
    </div>
  )
}
