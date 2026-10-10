import React from 'react'

export interface Member {
  id: string
  name: string
  emoji: string
  color: string
  specialty: string
}

// 模式 B 角色（与后端 moa_personas.py 保持一致）
export const MOA_MEMBERS: Member[] = [
  { id: 'facilitator', name: '主持人', emoji: '🎯', color: '#1D4ED8', specialty: '群聊调度 · 整合' },
  { id: 'linxiaosuan', name: '财务总监', emoji: '💰', color: '#14B8A6', specialty: '预算 · 住宿 · 交通' },
  { id: 'sugege', name: '美食达人', emoji: '🍜', color: '#F97316', specialty: '美食推荐' },
  { id: 'laoxu', name: '人文使者', emoji: '📜', color: '#7C3AED', specialty: '人文景点' },
  { id: 'ahao', name: '风光猎人', emoji: '📷', color: '#22C55E', specialty: '风景机位 · 安全' },
]

const STAGES = ['opening', 'round1', 'round2', 'integrate', 'done']
const STAGE_LABELS = ['主持人开场', '专家首轮', '交叉辩论', '主持人整合', '方案完成']

interface Props {
  stage: string
  stageLabel: string
  speakingRoleId: string | null
  expanded: boolean
  onToggle: () => void
}

export default function MemberPanel({ stage, stageLabel, speakingRoleId, expanded, onToggle }: Props) {
  const stageIdx = STAGES.indexOf(stage)

  return (
    <div className="flex flex-col h-full bg-white">
      {/* 头部：标题 + 展开/收起按钮 */}
      <div className="h-14 px-4 border-b border-gray-100 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-1.5 text-base font-semibold text-gray-900">
          <span className="text-lg">👥</span> AI 智囊团
          <span className="text-[11px] font-normal text-gray-400 ml-1">模式 B</span>
        </div>
        <button
          onClick={onToggle}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 bg-blue-50 border border-blue-200 rounded-full px-3 py-1.5 hover:bg-blue-100 transition shrink-0"
        >
          <span>{expanded ? '✕' : '💬'}</span>
          <span>{expanded ? '收起讨论室' : '展开讨论室'}</span>
        </button>
      </div>

      {/* 阶段进度 */}
      <div className="px-4 py-3 border-b border-gray-100 shrink-0">
        <div className="flex items-center gap-1">
          {STAGES.map((s, i) => (
            <React.Fragment key={s}>
              <div className="flex flex-col items-center gap-1">
                <div
                  className={`w-2.5 h-2.5 rounded-full transition ${
                    stageIdx >= i ? 'bg-blue-600' : 'bg-gray-200'
                  }`}
                />
                <span className={`text-[10px] ${stageIdx >= i ? 'text-blue-600' : 'text-gray-400'}`}>
                  {STAGE_LABELS[i]}
                </span>
              </div>
              {i < STAGES.length - 1 && (
                <div className={`flex-1 h-0.5 ${stageIdx > i ? 'bg-blue-600' : 'bg-gray-200'}`} />
              )}
            </React.Fragment>
          ))}
        </div>
        {stageLabel && (
          <p className="text-[11px] text-gray-400 mt-2">当前阶段：{stageLabel}</p>
        )}
      </div>

      {/* 成员卡 */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {MOA_MEMBERS.map((m) => {
          const speaking = speakingRoleId === m.id
          return (
            <div
              key={m.id}
              className="flex items-center gap-3 p-2.5 rounded-xl border transition"
              style={{
                borderColor: speaking ? m.color : '#eef2f7',
                background: speaking ? `${m.color}0f` : '#fff',
                boxShadow: speaking ? `inset 0 0 0 1px ${m.color}` : 'none',
              }}
            >
              <div
                className="w-9 h-9 rounded-full flex items-center justify-center text-base shrink-0"
                style={{ background: `${m.color}1f`, color: m.color }}
              >
                {m.emoji}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-semibold" style={{ color: m.color }}>
                    {m.name}
                  </span>
                  {speaking && (
                    <span className="flex gap-0.5">
                      <span className="w-1 h-1 rounded-full bg-current animate-pulse" style={{ color: m.color }} />
                      <span className="w-1 h-1 rounded-full bg-current animate-pulse" style={{ color: m.color, animationDelay: '0.2s' }} />
                      <span className="w-1 h-1 rounded-full bg-current animate-pulse" style={{ color: m.color, animationDelay: '0.4s' }} />
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-gray-400 truncate">{m.specialty}</div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="px-4 py-2.5 border-t border-gray-100 text-[11px] text-gray-400 shrink-0">
        1 位主持人 + 4 位职能专家，群辩后由主持人整合方案
      </div>
    </div>
  )
}
