// markdown 工具函数的回归用例。
// 用例数据均取自 probe_tempplan_content.py / probe_daysdraft_content.py
// 抓到的真实 LLM 输出，不是构造的假数据。
import {
  normalizeMarkdown,
  stripTagMarkers,
  plainText,
} from '../src/utils/markdown.ts'

let fail = 0
const check = (ok, label) => {
  console.log(`${ok ? '✓' : '✗'} ${label}`)
  if (!ok) fail++
}

// —— normalizeMarkdown ——
// 真实 spots 条目：--- 分隔行 + emoji 小节头 + **加粗**
const realSpot = [
  '---',
  '',
  '⛰️ 南线经典 | 雷峰夕照-净慈寺安全机位带  ',
  '安全系数 ⭐⭐⭐⭐⭐ | 15:30-18:00 光线柔和  ',
  '**雷峰塔夕照亭（纯平拍机位）**：¥40/人，塔内电梯直达',
].join('\n')

const normSpot = normalizeMarkdown(realSpot)
check(!/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/m.test(normSpot), '真实 spots：--- 分隔行已清除（不成横线）')
check(normSpot.includes('**雷峰塔夕照亭（纯平拍机位）**'), '真实 spots：配对加粗保留')
check(!/^\n|\n$/.test(normSpot), '真实 spots：首尾无空行')

// 真实 quote：--- 分隔 + 【标签】泄漏 + **加粗**
const realQuote =
  '💰 预算砍至800，住宿必须下沉 | 安静人文线配比修正  \n' +
  '单人独行 × 800元总盘  \n\n' +
  '---\n' +
  '【住宿选择】  \n' +
  '@人文使者 你推荐的之江馆溢价仍过高。改选**青芝坞民宿四人间（60元/晚）**，比原方案再降。'

const normQuote = normalizeMarkdown(stripTagMarkers(realQuote))
check(!/【[^】]{0,12}】/.test(normQuote), '真实 quote：【标签】已清除')
check(!/^\s*-{3,}\s*$/m.test(normQuote), '真实 quote：--- 分隔行已清除')
check(normQuote.includes('**青芝坞民宿四人间（60元/晚）**'), '真实 quote：配对加粗保留')

// 落单 **（截图里的真实形态）
const strayBold = '**晕染调**（湖畔金色时刻）**：免费，沿湖石板步道'
const outStray = normalizeMarkdown(strayBold)
check(!outStray.includes('**：'), '落单 ** 已清理')
check(outStray.startsWith('**晕染调**'), '落单场景下的配对加粗保留')

// || 拼接表格（ChatWindow 原有能力，不能因重构丢失）
const table = '| 景点 | 门票 || 西湖 | 免费 || 灵隐寺 | ¥75 |'
const outTable = normalizeMarkdown(table)
check(outTable.split('\n').length === 3, '|| 拼接表格行已拆成 3 行')

// 代码围栏
const fence = '说明\n```json\n{"a":1}\n```'
check(!normalizeMarkdown(fence).includes('```'), '代码围栏符号已去除')

// 流式半截标记：不应误删 ## 或吃掉未闭合 **
const frames = [
  ['行程建议如下\n\n---', false, '分隔行半截'],
  ['行程建议如下\n\n---\n\n##', true, '标题 ## 半截'],
  ['## 景点\n**西湖', true, '加粗未闭合'],
  ['## 景点\n**西湖**免费', true, '加粗已闭合'],
]
for (const [src, keepHash, label] of frames) {
  const out = normalizeMarkdown(src)
  check(out.includes('##') === keepHash, `流式「${label}」：## 处理正确`)
}
check(normalizeMarkdown('## 景点\n**西湖**免费').includes('**西湖**'), '流式：闭合加粗不丢')

// —— stripTagMarkers ——
// 剥完只剩标签的行应整行丢弃，不留空条目
const tagOnly = normalizeMarkdown(stripTagMarkers('【景点游览】\n---\n【住宿选择】'))
check(tagOnly.trim() === '', '纯标签行被整段丢弃')

const keepBody = stripTagMarkers('【住宿选择】\n青旅四人间 60 元/晚')
check(keepBody.includes('青旅四人间 60 元/晚'), '标签后的正文保留')

// —— plainText ——
// 单元格要裸文本：配对加粗也必须去掉（normalizeMarkdown 会保留它，那是给 ReactMarkdown 渲染用的）
const pt = plainText('**西湖**：免费\n\n⛰️ 孤山 | 登顶')
check(!pt.includes('**'), 'plainText：配对加粗已剥离')
check(!pt.includes('\n'), 'plainText：换行已压成空格（适配表格单元格）')
check(pt.includes('孤山'), 'plainText：正文保留')
check(pt.includes('西湖'), 'plainText：加粗内文字保留')

const ptTag = plainText('【景点游览】**西湖**：免费')
check(!ptTag.includes('【'), 'plainText：【标签】已剥离')

const ptHead = plainText('## 景点\n西湖人多')
check(!ptHead.includes('#'), 'plainText：行首 ## 已剥离')

// 真实 spots 名（带 --- 与 emoji）塞进单元格
const ptReal = plainText('**雷峰塔夕照亭（纯平拍机位）**：¥40/人，塔内电梯直达')
check(!ptReal.includes('**') && !ptReal.includes('---'), 'plainText：真实 spots 条目已纯文本化')
check(ptReal.startsWith('雷峰塔夕照亭'), 'plainText：真实 spots 内容保留')

console.log(fail === 0 ? '\n全部用例通过' : `\n${fail} 个用例失败`)
process.exit(fail === 0 ? 0 : 1)
