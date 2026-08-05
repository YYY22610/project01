// Shared mapping between backend construct values and Chinese display labels.
// Keep this in sync with the admin questionnaire config dropdown.
export const CONSTRUCT_LABELS: Record<string, string> = {
  usefulness: '感知有用性',
  ease_of_use: '感知易用性',
  trust: '信任度',
  satisfaction: '满意度',
  future_use: '使用意愿',
  sys_quality: '系统质量',
  task_load: '任务负荷',
  manipulation_check: '操纵检验',
  autonomy: '感知自主性',
}

export const CONSTRUCT_OPTIONS = Object.entries(CONSTRUCT_LABELS).map(([value, label]) => ({
  value,
  label,
}))

// Frontend type tokens ↔ DB question_type + scale_level
export const TYPE_OPTIONS = [
  { value: 'likert5', label: '5级量表 (1-5)' },
  { value: 'likert7', label: '7级量表 (1-7)' },
  { value: 'single_choice', label: '单选题' },
  { value: 'multiple_choice', label: '多选题' },
  { value: 'text', label: '文本题' },
]

export const typeLabel = (value: string) =>
  TYPE_OPTIONS.find((t) => t.value === value)?.label || value

export const constructLabel = (value: string) =>
  CONSTRUCT_LABELS[value] || value
