/** 极简 Markdown → HTML 转换，仅覆盖本方案用到的结构（标题/粗体/列表/表格/段落）。
 *  用于把主持人的最终方案导出为 Word 文档内容。 */
export function markdownToHtml(md: string): string {
  const lines = md.replace(/\r\n/g, '\n').split('\n')
  const out: string[] = []
  let inList = false
  let inTable = false
  const closeList = () => { if (inList) { out.push('</ul>'); inList = false } }
  const closeTable = () => { if (inTable) { out.push('</tbody></table>'); inTable = false } }

  const inline = (s: string) =>
    s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

  for (const raw of lines) {
    const line = raw.trim()
    if (!line) { closeList(); closeTable(); continue }

    // 表格
    if (line.startsWith('|') && line.endsWith('|')) {
      const cells = line.split('|').slice(1, -1).map((c) => c.trim())
      if (!inTable) {
        out.push('<table style="border-collapse:collapse;width:100%;margin:8px 0">')
        out.push('<tbody>')
        inTable = true
        out.push('<tr>' + cells.map((c) => `<th style="border:1px solid #ccc;padding:6px 10px;background:#f4f8fd">${inline(c)}</th>`).join('') + '</tr>')
      } else {
        // 分隔行（|---|）跳过
        if (cells.every((c) => /^-+$/.test(c.replace(/ /g, '')))) continue
        out.push('<tr>' + cells.map((c) => `<td style="border:1px solid #ccc;padding:6px 10px">${inline(c)}</td>`).join('') + '</tr>')
      }
      continue
    }
    closeTable()

    // 标题
    const h = /^(#{1,4})\s+(.*)$/.exec(line)
    if (h) {
      closeList()
      const level = h[1].length
      const sizes = { 1: '26px', 2: '20px', 3: '17px', 4: '15px' }
      out.push(`<h${level} style="font-size:${sizes[level as 1|2|3|4]};margin:14px 0 6px;color:#16263d">${inline(h[2])}</h${level}>`)
      continue
    }

    // 列表
    if (/^[-*]\s+/.test(line)) {
      if (!inList) { out.push('<ul style="margin:6px 0 6px 22px">'); inList = true }
      out.push(`<li style="margin:2px 0">${inline(line.replace(/^[-*]\s+/, ''))}</li>`)
      continue
    }
    closeList()

    // 段落
    out.push(`<p style="margin:6px 0;line-height:1.8">${inline(line)}</p>`)
  }
  closeList(); closeTable()
  return out.join('\n')
}
