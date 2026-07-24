import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../stores/userStore'

export default function Consent() {
  const [agreed, setAgreed] = useState(false)
  const [demographics, setDemographics] = useState({
    age: '',
    gender: '',
    education: '',
    tech_frequency: '',
    ai_experience: '',
  })
  const { consent, updateDemographics, loading } = useUserStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!agreed) return

    try {
      await consent()
      await updateDemographics({
        age: parseInt(demographics.age),
        gender: demographics.gender,
        education: demographics.education,
        tech_frequency: demographics.tech_frequency,
        ai_experience: demographics.ai_experience,
      })
      navigate('/demo')
    } catch (e: any) {
      alert(e.response?.data?.detail || '操作失败')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-2xl mx-auto bg-white rounded-2xl shadow-lg p-8">
        <h1 className="text-2xl font-bold text-gray-800 mb-6">知情同意书</h1>

        <div className="bg-gray-50 rounded-lg p-6 mb-6 max-h-64 overflow-y-auto text-sm text-gray-600 leading-relaxed">
          <p className="mb-3">尊敬的参与者：</p>
          <p className="mb-3">感谢您参与本研究。本研究旨在探索人机协作在旅行规划任务中的效果。实验过程约30-60分钟。</p>
          <p className="mb-3"><strong>实验内容：</strong>您需要完成一个杭州三日游行程规划任务，包括搜索景点、生成行程文档、设置提醒和发送邮件。</p>
          <p className="mb-3"><strong>数据收集：</strong>实验过程中将记录您的操作行为（如搜索关键词、编辑操作等），用于研究分析。所有数据匿名处理，不会泄露个人身份。</p>
          <p className="mb-3"><strong>权利保障：</strong>您有权随时退出实验，不影响您的任何权益。实验数据仅用于学术研究。</p>
          <p className="mb-3"><strong>保密承诺：</strong>研究者承诺对所有收集的数据严格保密，仅用于学术研究目的。</p>
          <p>如有疑问，请联系研究者。点击"同意并继续"即表示您已阅读并同意参与本研究。</p>
        </div>

        <label className="flex items-center gap-2 mb-6 cursor-pointer">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-sm text-gray-700">我已阅读并同意上述知情同意书内容</span>
        </label>

        {agreed && (
          <div className="border-t border-gray-200 pt-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">基本信息采集</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">年龄</label>
                <input
                  type="number"
                  value={demographics.age}
                  onChange={(e) => setDemographics({ ...demographics, age: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="如 22"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">性别</label>
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
                <label className="block text-sm font-medium text-gray-700 mb-1">学历</label>
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
                <label className="block text-sm font-medium text-gray-700 mb-1">技术使用频率</label>
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
                <label className="block text-sm font-medium text-gray-700 mb-1">AI工具使用经验</label>
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

        <button
          onClick={handleSubmit}
          disabled={!agreed || loading || !demographics.age || !demographics.gender || !demographics.education || !demographics.tech_frequency || !demographics.ai_experience}
          className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {loading ? '提交中...' : '同意并继续'}
        </button>
      </div>
    </div>
  )
}
