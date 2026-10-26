import { useEffect, useMemo, useState } from 'react'
import { questionnaireApi } from '../services'
import type { QuestionnaireItem } from '../types'
import { joinMulti } from '../constants/questionnaire'

/**
 * 问卷题目加载 + 作答状态 —— 前置问卷与后置问卷共用。
 *
 * 作答值统一用 string（多选题内部以 " | " 连接后提交），
 * 渲染时由 QuestionRenderer 按题型还原成 string[]。
 *
 * @param phase 'pre' | 'post'
 * @param submit 提交回调，收到已归一化的 [{item_id, response_value}]
 */
export function useQuestionnaire(
  phase: 'pre' | 'post',
  submit: (responses: { item_id: string; response_value: string }[]) => Promise<void>,
) {
  const [items, setItems] = useState<QuestionnaireItem[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    let alive = true
    setLoading(true)
    questionnaireApi
      .items(phase)
      .then((res) => {
        if (!alive) return
        setItems(res.data)
        setLoadError('')
      })
      .catch(() => {
        if (alive) setLoadError('问卷加载失败，请刷新页面重试')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [phase])

  const setAnswer = (itemId: string, value: string | string[]) => {
    const normalized = Array.isArray(value) ? joinMulti(value) : value
    setAnswers((prev) => ({ ...prev, [itemId]: normalized }))
  }

  /** 开放题为选填，不计入「未完成」判定 */
  const isAnswered = (item: QuestionnaireItem) => {
    if (item.question_type === 'text') return true
    return !!answers[item.id]?.trim()
  }

  const answeredCount = useMemo(
    () => items.filter(isAnswered).length,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [items, answers],
  )

  const allAnswered = items.length > 0 && answeredCount === items.length

  const handleSubmit = async () => {
    if (!allAnswered || submitting) return
    setSubmitting(true)
    try {
      await submit(items.map((item) => ({ item_id: item.id, response_value: answers[item.id] ?? '' })))
      setSubmitted(true)
    } finally {
      setSubmitting(false)
    }
  }

  /** 按构念分组渲染用：同构念只显示一次小标题 */
  const withHeaders = useMemo(() => {
    let currentConstruct = ''
    return items.map((item) => {
      const showHeader = item.construct !== currentConstruct
      currentConstruct = item.construct
      return { item, showHeader }
    })
  }, [items])

  return {
    items,
    answers,
    setAnswer,
    loading,
    loadError,
    submitting,
    submitted,
    allAnswered,
    answeredCount,
    handleSubmit,
    withHeaders,
  }
}
