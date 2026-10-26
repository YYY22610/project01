// Shared mapping between backend construct values and Chinese display labels.
// Keep this in sync with:
//   - backend/app/models/questionnaire.py  (QuestionConstruct enum)
//   - backend/app/routers/admin.py          (QUESTIONNAIRE_CONSTRUCT_LABELS, export headers)
// Source instrument: 附件5 实验阶段问卷 (2026-10-14)
export const CONSTRUCT_LABELS: Record<string, string> = {
  // 前置问卷
  demographic: '人口统计',
  ai_experience: 'AI 使用经验',
  agent_awareness: '智能体认知',
  social_influence: '社会影响',
  anthropomorphism: '感知拟人化',
  // 后置问卷
  hedonic_motivation: '享乐动机',
  performance_expectancy: '绩效期望',
  effort_expectancy: '努力期望',
  perceived_risk: '感知风险',
  affective_experience: '情绪体验',
  acceptance_intention: '接受意愿',
  resistance_intention: '拒绝意愿',
  // 通用
  manipulation_check: '操纵检验',
  open_feedback: '其他反馈',
}

export const CONSTRUCT_OPTIONS = Object.entries(CONSTRUCT_LABELS).map(([value, label]) => ({
  value,
  label,
}))

// 问卷阶段
export const PHASE_OPTIONS = [
  { value: 'pre', label: '前置问卷' },
  { value: 'post', label: '后置问卷' },
]

export const phaseLabel = (value: string) =>
  PHASE_OPTIONS.find((p) => p.value === value)?.label || value

// Frontend type tokens ↔ DB question_type + scale_level
export const TYPE_OPTIONS = [
  { value: 'likert5', label: '5级量表 (1-5)' },
  { value: 'likert7', label: '7级量表 (1-7)' },
  { value: 'bipolar5', label: '双极量表 (1-5, 自定义锚点)' },
  { value: 'single_choice', label: '单选题' },
  { value: 'multiple_choice', label: '多选题' },
  { value: 'text', label: '文本题' },
]

export const typeLabel = (value: string) =>
  TYPE_OPTIONS.find((t) => t.value === value)?.label || value

export const constructLabel = (value: string) =>
  CONSTRUCT_LABELS[value] || value

/**
 * 「以上均不认同」类互斥选项的识别。
 * 选中它时前端会清空其他选项，避免出现「既认同又不认同」的矛盾作答。
 */
export const EXCLUSIVE_OPTION_KEYWORDS = ['以上均不认同', '以上都不认同', '均不认同', '以上均未选中']

export const isExclusiveOption = (label: string) =>
  EXCLUSIVE_OPTION_KEYWORDS.some((kw) => label.includes(kw))

/** 多选题提交给后端时的分隔符 —— 后端 _first_choice() 按此切分取首项 */
export const MULTI_JOINER = ' | '

export const joinMulti = (values: string[]) => values.join(MULTI_JOINER)
