# -*- coding: utf-8 -*-
"""生成一页组会汇报 PPT：近期工作进展（部署 / 完善 / 证明 / 测试）。"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---- 画布：19:10 宽屏直角 ----
W, H = 13.333, 13.333 / 1.9          # 19:10
prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
slide = prs.slides.add_slide(prs.slide_layouts[6])   # 空白版式

# ---- 配色 ----
NAVY   = RGBColor(0x17, 0x37, 0x5E)   # 深蓝标题栏
INK    = RGBColor(0x1E, 0x29, 0x3B)   # 主文字
GREY   = RGBColor(0x53, 0x60, 0x72)   # 次要文字
CARD   = RGBColor(0xFF, 0xFF, 0xFF)   # 卡片白
BORDER = RGBColor(0xDD, 0xE5, 0xEF)   # 卡片描边
BG     = RGBColor(0xF3, 0xF7, 0xFC)   # 页面底
BARS   = [RGBColor(0x25, 0x63, 0xEB),  # 蓝
          RGBColor(0x0D, 0x94, 0x88),  # 青
          RGBColor(0xEA, 0x58, 0x0C),  # 橙
          RGBColor(0x7C, 0x3A, 0xED)]  # 紫
YAHEI = "微软雅黑"

def setfont(run, size, bold=False, color=INK, name=YAHEI):
    run.font.size = Pt(size); run.font.bold = bold
    run.font.color.rgb = color; run.font.name = name
    r = run._r.rPr
    from pptx.oxml.ns import qn
    ea = r.find(qn('a:ea'))
    if ea is None:
        from lxml import etree
        ea = etree.SubElement(r, qn('a:ea'))
    ea.set('typeface', name)

# ---- 背景 ----
bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid(); bg.fill.fore_color.rgb = BG; bg.line.fill.background()
bg.shadow.inherit = False

# ---- 顶部深蓝标题栏 ----
bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(1.02))
bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
bar.shadow.inherit = False

tb = slide.shapes.add_textbox(Inches(0.5), Inches(0.12), Inches(9.6), Inches(0.8))
tf = tb.text_frame; tf.margin_left = tf.margin_right = 0
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
setfont(p.add_run(), 24, True, RGBColor(0xFF,0xFF,0xFF))
p.runs[0].text = "近期工作进展 · 人机协作决策实验平台"

tb2 = slide.shapes.add_textbox(Inches(10.1), Inches(0.12), Inches(2.75), Inches(0.8))
tf2 = tb2.text_frame; tf2.vertical_anchor = MSO_ANCHOR.MIDDLE
p2 = tf2.paragraphs[0]; p2.alignment = PP_ALIGN.RIGHT
setfont(p2.add_run(), 12, False, RGBColor(0xBF,0xD2,0xEA))
p2.runs[0].text = "部署 · 完善 · 测试"

# ---- 四张卡片（2×2）----
LM, GAP, TOP = 0.5, 0.32, 1.30
CW = (W - LM*2 - GAP) / 2
CH = 2.30
POS = [(LM, TOP), (LM+CW+GAP, TOP), (LM, TOP+CH+0.28), (LM+CW+GAP, TOP+CH+0.28)]

CARDS = [
    ("一、平台部署上线",
     ["阿里云 ECS 全链路部署：环境 · 数据库 · 前后端 · Nginx 反代 ·",
      "守护进程 · 定时备份，共 8 个环节",
      "公网可远程访问，健康检查正常，数据每日备份留 30 份"]),
    ("二、实验流程完善",
     ["问卷体系由代码硬编码重构为数据库驱动",
      "前置 20 题 + 后置 34 题 = 54 题，覆盖 14 个研究构念",
      "补充反向计分题、情绪双极量表与分节指导语"]),
    ("三、部署证明整理",
     ["6 大章节、11 张真实运行截图",
      "覆盖 系统登录 · 后台核心功能 · 部署管理 · 行为日志",
      "参与者端与管理员端登录截图完整，四项要求全部落图"]),
    ("四、全流程测试与核查",
     ["17 个环节通过 16 项，覆盖 H / SOA / MOA 三组",
      "后台 6 个页面可用；6 路并发全通过，SSE 首字节 0.01s",
      "定位问题 7 项，其中 2 项影响实验数据质量"]),
]

for (x, y), (title, lines), col in zip(POS, CARDS, BARS):
    # 卡片
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(CW), Inches(CH))
    card.adjustments[0] = 0.045
    card.fill.solid(); card.fill.fore_color.rgb = CARD
    card.line.color.rgb = BORDER; card.line.width = Pt(1)
    card.shadow.inherit = False
    # 彩色左边条
    lb = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(0.085), Inches(CH))
    lb.adjustments[0] = 0.5
    lb.fill.solid(); lb.fill.fore_color.rgb = col; lb.line.fill.background()
    lb.shadow.inherit = False
    # 标题
    t = slide.shapes.add_textbox(Inches(x+0.28), Inches(y+0.16), Inches(CW-0.5), Inches(0.42))
    tf = t.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    pp = tf.paragraphs[0]; setfont(pp.add_run(), 15.5, True, col)
    pp.runs[0].text = title
    # 正文
    b = slide.shapes.add_textbox(Inches(x+0.28), Inches(y+0.72), Inches(CW-0.5), Inches(CH-0.85))
    bf = b.text_frame; bf.margin_left = bf.margin_right = 0
    bf.word_wrap = True
    for i, ln in enumerate(lines):
        para = bf.paragraphs[0] if i == 0 else bf.add_paragraph()
        para.space_after = Pt(5); para.line_spacing = 1.06
        setfont(para.add_run(), 11.5, False, GREY)
        para.runs[0].text = "· " + ln

# ---- 底部：装饰线 + 下一步 + 页码 ----
ln = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(LM), Inches(H-0.72), Inches(W-LM*2), Pt(1.1))
ln.fill.solid(); ln.fill.fore_color.rgb = RGBColor(0xCB,0xD9,0xEA); ln.line.fill.background(); ln.shadow.inherit = False

acc = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(LM), Inches(H-0.72), Inches(1.15), Pt(1.6))
acc.fill.solid(); acc.fill.fore_color.rgb = BARS[0]; acc.line.fill.background(); acc.shadow.inherit = False

ft = slide.shapes.add_textbox(Inches(LM), Inches(H-0.63), Inches(W-LM*2-0.7), Inches(0.42))
ftf = ft.text_frame; ftf.margin_left = ftf.margin_right = ftf.margin_top = 0
fp = ftf.paragraphs[0]
setfont(fp.add_run(), 11.5, True, NAVY)
fp.runs[0].text = "下一步｜"
setfont(fp.add_run(), 11.5, False, GREY)
fp.runs[1].text = "优先修复邮件真实投递、单盲分组暴露两项高优先级问题，然后进入正式被试招募。"

pn = slide.shapes.add_textbox(Inches(W-LM-0.6), Inches(H-0.62), Inches(0.6), Inches(0.36))
pf = pn.text_frame; pf.margin_left = pf.margin_right = pf.margin_top = 0
pp = pf.paragraphs[0]; pp.alignment = PP_ALIGN.RIGHT
setfont(pp.add_run(), 11, False, RGBColor(0x94,0xA3,0xB8)); pp.runs[0].text = "1"

out = r"D:/27475/WorkBuddy-搭建网站/travel-experiment-platform/组会汇报_工作进展_一页.pptx"
prs.save(out)
print("SAVED:", out)
print("尺寸(in):", round(W,3), "x", round(H,3), " 比例 19:10")
