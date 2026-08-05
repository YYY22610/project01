import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../stores/userStore'

export default function Register() {
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [demographics, setDemographics] = useState({
    age: '',
    gender: '',
    education: '',
    tech_frequency: '',
    ai_experience: '',
  })
  const [error, setError] = useState('')
  const { register, loginByEmail, updateDemographics, loading } = useUserStore()
  const navigate = useNavigate()

  const validateDemographics = () => {
    return (
      demographics.age &&
      demographics.gender &&
      demographics.education &&
      demographics.tech_frequency &&
      demographics.ai_experience
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!email.trim()) {
      setError('请输入邮箱')
      return
    }

    try {
      if (isLogin) {
        await loginByEmail(email)
        // 登录后根据当前实验状态跳转：重置过或新用户走知情同意，否则继续任务
        const status = useUserStore.getState().user?.status
        navigate(status === 'consented' ? '/consent' : '/task')
      } else {
        if (!validateDemographics()) {
          setError('请完整填写基本信息')
          return
        }
        await register(email)
        await updateDemographics({
          age: parseInt(demographics.age),
          gender: demographics.gender,
          education: demographics.education,
          tech_frequency: demographics.tech_frequency,
          ai_experience: demographics.ai_experience,
        })
        navigate('/consent')
      }
    } catch (e: any) {
      const detail = e.response?.data?.detail
      if (detail) {
        // 双向智能引导：邮箱已注册则引导去登录，未注册则引导去注册
        // （避免用户想登录却误点「注册」、因邮箱已存在而失败、导致仍停留在旧账号会话）
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

          {!isLogin && (
            <div className="border-t border-gray-200 pt-4">
              <h2 className="text-base font-semibold text-gray-800 mb-3">基本信息采集</h2>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">年龄</label>
                  <input
                    type="number"
                    value={demographics.age}
                    onChange={(e) => setDemographics({ ...demographics, age: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="如 22"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">性别</label>
                  <select
                    value={demographics.gender}
                    onChange={(e) => setDemographics({ ...demographics, gender: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">请选择</option>
                    <option value="male">男</option>
                    <option value="female">女</option>
                    <option value="other">其他</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">学历</label>
                  <select
                    value={demographics.education}
                    onChange={(e) => setDemographics({ ...demographics, education: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">请选择</option>
                    <option value="high_school">高中及以下</option>
                    <option value="college">大专</option>
                    <option value="bachelor">本科</option>
                    <option value="master">硕士</option>
                    <option value="phd">博士</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">技术使用频率</label>
                  <select
                    value={demographics.tech_frequency}
                    onChange={(e) => setDemographics({ ...demographics, tech_frequency: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">请选择</option>
                    <option value="rarely">很少使用</option>
                    <option value="sometimes">偶尔使用</option>
                    <option value="often">经常使用</option>
                    <option value="daily">每天使用</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-gray-700 mb-1">AI工具使用经验</label>
                  <select
                    value={demographics.ai_experience}
                    onChange={(e) => setDemographics({ ...demographics, ai_experience: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">请选择</option>
                    <option value="none">从未使用</option>
                    <option value="basic">偶尔尝试</option>
                    <option value="intermediate">有一定经验</option>
                    <option value="advanced">熟练使用</option>
                  </select>
                </div>
              </div>
            </div>
          )}

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
