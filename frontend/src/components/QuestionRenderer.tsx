import type { QuestionnaireItem } from '../types'
import { isExclusiveOption, joinMulti } from '../constants/questionnaire'

/**
 * 问卷题目渲染器 —— 前置问卷（Consent.tsx）与后置问卷（Questionnaire.tsx）共用。
 *
 * 设计要点：
 *  - 题目全部来自后端 questionnaire_items（按 phase 区分），前端不再硬编码题干与选项
 *  - 支持 4 种题型：likert（普通/双极）、multiple、choice、text
 *  - 同构念的题连续排列时只显示一次构念小标题；section_note 渲染为题干上方的指导语
 *  - 反向计分题在题干后加「（反向计分）」提示，避免被试误读（题目原文仍原样呈现）
 */

type Props = {
  item: QuestionnaireItem
  /** 当前作答：单选/量表/文本为字符串，多选为 string[] */
  value: string | string[] | undefined
  onChange: (value: string | string[]) => void
  /** 左侧题号（Q01…），与原文档编号一致 */
  label: string
}

const isBipolar = (item: QuestionnaireItem): boolean =>
  item.question_type === 'likert' &&
  !!item.options &&
  typeof item.options === 'object' &&
  !Array.isArray(item.options) &&
  typeof item.options.left === 'string'

const toArray = (v: string | string[] | undefined): string[] =>
  Array.isArray(v) ? v : v ? String(v).split(' | ') : []

export default function QuestionRenderer({ item, value, onChange, label }: Props) {
  const selectedMulti = toArray(value)

  const toggleMulti = (opt: string) => {
    if (isExclusiveOption(opt)) {
      // 互斥项：已选则取消，否则独占
      onChange(selectedMulti.includes(opt) ? [] : [opt])
      return
    }
    const withoutExclusive = selectedMulti.filter((x) => !isExclusiveOption(x))
    onChange(
      withoutExclusive.includes(opt)
        ? withoutExclusive.filter((x) => x !== opt)
        : [...withoutExclusive, opt],
    )
  }

  return (
    <div>
      {/* 题组指导语：仅题组首题带 section_note */}
      {item.section_note && (
        <p className="text-xs text-gray-500 bg-gray-50 border-l-2 border-blue-200 rounded-r px-3 py-2 mb-3 leading-relaxed">
          {item.section_note}
        </p>
      )}

      {isBipolar(item) ? (
        // 双极量表：题干只留题号，左右端词与刻度并排一行。
        // 题目原文形如「忧郁 —— 1 —— … —— 5 —— 满足」，是把量表画在题干里的纸笔写法，
        // 界面上已有真实刻度按钮，再照搬会重复且与按钮错位，故此处不重复题干文字。
        <div>
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-sm font-medium text-gray-500 shrink-0">{label}</span>
            {item.is_reverse && (
              <span className="text-xs text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded shrink-0">
                反向计分
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 sm:gap-4">
            <span className="text-sm text-gray-600 shrink-0 w-16 sm:w-24 text-right">
              {item.options.left}
            </span>
            <div className="flex gap-2">
              {Array.from({ length: item.scale_level }, (_, i) => i + 1).map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => onChange(String(val))}
                  className={`w-10 h-10 rounded-lg font-medium transition ${
                    value === String(val)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {val}
                </button>
              ))}
            </div>
            <span className="text-sm text-gray-600 shrink-0">{item.options.right}</span>
          </div>
        </div>
      ) : (
        <>
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-sm font-medium text-gray-500 shrink-0">{label}</span>
            <span className="text-sm text-gray-700">{item.question_text}</span>
            {item.is_reverse && (
              <span className="text-xs text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded shrink-0">
                反向计分
              </span>
            )}
          </div>

          {/* —— 李克特量表 —— */}
          {item.question_type === 'likert' && (
            <div className="flex flex-wrap gap-2 sm:ml-11">
              {Array.from({ length: item.scale_level }, (_, i) => i + 1).map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => onChange(String(val))}
                  className={`w-10 h-10 rounded-lg font-medium transition ${
                    value === String(val)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {val}
                </button>
              ))}
              {item.scale_level === 5 && (
                <div className="flex justify-between w-full text-xs text-gray-400 mt-1">
                  <span>非常不同意</span>
                  <span>非常同意</span>
                </div>
              )}
            </div>
          )}

          {/* —— 单选 —— */}
          {item.question_type === 'choice' && Array.isArray(item.options) && (
            <div className="flex flex-col gap-2 sm:ml-11">
              {item.options.map((opt: string) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => onChange(opt)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium text-left transition ${
                    value === opt
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          )}

          {/* —— 多选 —— */}
          {item.question_type === 'multiple' && Array.isArray(item.options) && (
            <div className="flex flex-col gap-2 sm:ml-11">
              {item.options.map((opt: string) => {
                const checked = selectedMulti.includes(opt)
                return (
                  <label
                    key={opt}
                    className={`flex items-start gap-2 px-3 py-2.5 rounded-lg border cursor-pointer transition text-sm leading-relaxed ${
                      checked
                        ? 'border-blue-500 bg-blue-50 text-blue-900'
                        : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/40'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleMulti(opt)}
                      className="mt-0.5 w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 flex-shrink-0"
                    />
                    <span>{opt}</span>
                  </label>
                )
              })}
            </div>
          )}

          {/* —— 开放题 —— */}
          {item.question_type === 'text' && (
            <textarea
              value={typeof value === 'string' ? value : ''}
              onChange={(e) => onChange(e.target.value)}
              rows={4}
              maxLength={1000}
              placeholder="请输入您的想法（选填）"
              className="w-full sm:ml-11 px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-700 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-300 resize-y"
            />
          )}
        </>
      )}
    </div>
  )
}

export { joinMulti }
