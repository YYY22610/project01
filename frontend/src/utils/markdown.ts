/**
 * LLM 输出的 Markdown 归一化。
 *
 * 平台的 LLM 文本（助理回复、MOA 发言、最终方案）都直接来自模型，常见三类噪声：
 *  1. 落单的 **            —— 行内 ** 数为奇数，收尾那个没配对，渲染后裸露成符号
 *  2. 独立的 --- / *** 行 —— 交给 Markdown 会渲染成 <hr> 横线，在密集卡片里抢视觉，
 *                             也容易被误读成删除线
 *  3. ``` 代码围栏        —— 模型极少真的输出代码，去掉围栏符号更干净
 *  4. || 拼接的表格行      —— 模型把整张表压成一行，需拆成换行 remark-gfm 才能渲染
 *  5. 【xxx】内部标签      —— 后端 _parse_tagged 的划分标记，不该暴露给用户
 *
 * 所有处理都是纯字符串变换，可安全用于 SSE 流式渲染：每一帧都是对**完整累积文本**
 * 重新处理（store 里 m.content + delta 累加后整段传入），不是在上帧结果上叠加，
 * 因此不存在"标记被吃掉后无法恢复"的问题；代价只是流式中途那一瞬加粗尚未成对闭合。
 */

/** 清掉一行里落单的 **（该行 ** 出现偶数次，说明最后那个没有配对） */
function stripStrayBold(line: string): string {
  const parts = line.split('**')
  if (parts.length % 2 === 0) {
    // 落单的是最后一个 **，把最后一段接回前一段
    return parts.slice(0, -1).join('**') + parts[parts.length - 1]
  }
  return line
}

/** 把 || 拼接的表格行拆成多行：|a||b||c| => |a|\n|b|\n|c| */
function splitConcatenatedTableRow(line: string): string {
  const trimmed = line.trim()
  if (trimmed.startsWith('|') && trimmed.includes('||')) {
    return trimmed.replace(/\|\|/g, '|\n|')
  }
  return line
}

/**
 * Markdown 归一化（结构性清理）。
 * 适用于交给 ReactMarkdown 渲染的正文。
 */
export function normalizeMarkdown(text: string): string {
  return text
    // 代码围栏：只去符号，保留内容
    .replace(/^\s*```[a-zA-Z]*\s*$/gm, '')
    // 独立的分隔行：清空后由下方 \n{3,} 折叠 + 首尾收口处理
    .replace(/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/gm, '')
    .split('\n')
    .map(splitConcatenatedTableRow)
    .map(stripStrayBold)
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    // 删掉分隔行后首尾会留空行，会让卡片顶部出现空隙
    .replace(/^\n+|\n+$/g, '')
}

/**
 * 剥掉后端内部的 【xxx】 标签。
 * 这些标记是 _parse_tagged 用来划分六项要素的，不该出现在界面上；
 * 剥完只剩标签的行整行丢弃，避免留下空条目。
 */
export function stripTagMarkers(text: string): string {
  const kept = text
    .split('\n')
    .filter((line) => line.replace(/【[^】]{0,12}】/g, '').trim().length > 0)
    .join('\n')
  return kept.replace(/【[^】]{0,12}】/g, '')
}

/**
 * 纯文本化：用于表格单元格等不能放 Markdown 组件的位置。
 *
 * 注意不能直接用 normalizeMarkdown —— 它**保留配对的 **（那是留给 ReactMarkdown
 * 去渲染成 <strong> 的）。单元格要的是裸文本，故这里额外把配对加粗也去掉。
 */
export function plainText(text: string): string {
  return normalizeMarkdown(stripTagMarkers(text))
    // 配对加粗 -> 只留文字
    .replace(/\*\*(.+?)\*\*/g, '$1')
    // 残留的行内标记（标题/列表/引用符号）
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s{0,3}>\s?/gm, '')
    .replace(/\s+/g, ' ')
    .trim()
}
