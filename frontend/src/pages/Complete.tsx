import { useUserStore } from '../stores/userStore'

export default function Complete() {
  const { user, logout } = useUserStore()

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-blue-100 px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-gray-800 mb-2">实验完成</h1>
        <p className="text-gray-500 mb-6">
          感谢您的参与！您的实验数据已成功提交。
        </p>
        <div className="bg-gray-50 rounded-lg p-4 mb-6 text-left">
          <p className="text-sm text-gray-600">您的参与对我们的研究非常有价值。所有数据将匿名处理，仅用于学术研究。</p>
        </div>
        <button
          onClick={logout}
          className="w-full py-3 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition"
        >
          退出
        </button>
      </div>
    </div>
  )
}
