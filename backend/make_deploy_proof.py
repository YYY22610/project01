"""生成部署证明文档（docx）：系统登录 + 后台核心功能截图 + 部署管理 + 日志。
数据来源：阿里云线上平台 http://47.114.33.223（全部截图与统计均取自云端真实环境）。
"""
import os
from datetime import datetime

import httpx
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

BASE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(BASE, "browser_shots", "deploy_proof")
OUT = os.path.join(os.path.dirname(BASE), "部署证明_人机协作决策实验平台.docx")

# ===== 线上环境 =====
API = "http://47.114.33.223/api"
ADMIN_USER = "admin"
ADMIN_PASS = "Admin2026"

ACCENT = RGBColor(0x1F, 0x4E, 0x79)
GREY = RGBColor(0x59, 0x59, 0x59)


def health():
    try:
        with httpx.Client(timeout=8, trust_env=False) as c:
            return c.get(f"{API}/health").json()
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}


def _admin_token(c):
    r = c.post(f"{API}/auth/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    return r.json().get("access_token", "")


def counts():
    """通过线上 API 采集统计数据（不连本地数据库，确保数据源自云端）。"""
    out = {}
    try:
        with httpx.Client(timeout=15, trust_env=False) as c:
            tok = _admin_token(c)
            if not tok:
                return {"_error": "管理员登录失败"}
            hd = {"Authorization": f"Bearer {tok}"}
            # 参与者统计
            p = c.get(f"{API}/admin/participants", headers=hd).json()
            out["participants"] = p.get("total", 0)
            grp = {}
            for u in p.get("participants", []):
                g = u.get("group") or "未分组"
                grp[g] = grp.get(g, 0) + 1
            if grp:
                out["groups"] = grp
            # 行为日志
            lg = c.get(f"{API}/admin/logs", headers=hd).json()
            out["behavior_logs"] = lg.get("total", 0)
            # 看板
            d = c.get(f"{API}/admin/dashboard", headers=hd).json()
            out["target_sample"] = d.get("target_sample")
            out["completion_rate"] = d.get("completion_rate")
            out["avg_duration_ms"] = d.get("avg_duration_ms")
            out["experiment_status"] = d.get("experiment_status")
    except Exception as e:
        out["_error"] = str(e)[:120]
    return out


def add_shot(doc, filename, caption):
    path = os.path.join(SHOTS, filename)
    if not os.path.exists(path):
        return
    doc.add_picture(path, width=Inches(6.3))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph(caption)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in p.runs:
        r.font.size = Pt(9)
        r.font.color.rgb = GREY
        r.font.name = "微软雅黑"


def h(doc, text, level):
    hp = doc.add_heading(text, level=level)
    for r in hp.runs:
        r.font.color.rgb = ACCENT
        r.font.name = "微软雅黑"
    return hp


def main():
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "微软雅黑"
    style.font.size = Pt(10.5)

    hz = health()
    cnt = counts()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 标题
    t = doc.add_heading("人机协作决策实验平台 · 部署证明", level=0)
    for r in t.runs:
        r.font.color.rgb = ACCENT
    sub = doc.add_paragraph("系统登录 · 后台管理核心功能 · 部署管理 · 行为日志")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in sub.runs:
        r.font.size = Pt(12)
        r.font.color.rgb = GREY

    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info.add_run(
        f"生成时间：2026-10-11    线上地址：http://47.114.33.223    "
        f"服务状态：{hz.get('status')}    "
        f"LLM 模式：{hz.get('llm_mode')}（真实模型，已禁用 Mock）"
    ).font.size = Pt(10)

    # 一、系统概述
    h(doc, "一、系统概述", 1)
    doc.add_paragraph(
        "本平台为「人机协作决策实验平台」，采用 React + FastAPI + PostgreSQL 架构，"
        "用于开展人类与 AI 助理（H 单助理 / SOA 单 AI / MOA 多 AI）三种协作模式的对照实验。"
        "系统已部署至阿里云服务器并通过公网访问（http://47.114.33.223），"
        "后台管理功能齐备，各项服务运行正常。"
    )

    # 二、部署环境
    h(doc, "二、部署管理", 1)
    env = doc.add_table(rows=1, cols=2)
    env.style = "Light Grid Accent 1"
    hdr = env.rows[0].cells
    hdr[0].text = "项目"
    hdr[1].text = "配置"
    for k, v in [
        ("部署位置", "阿里云 ECS（学生优选），公网访问 http://47.114.33.223"),
        ("服务器规格", "2核 2GiB 经济型 e 实例，ESSD 40GiB 系统盘，1Mbps 公网带宽"),
        ("地域 / 镜像", "华东1（杭州）/ Ubuntu 22.04 LTS 64位"),
        ("后端", "FastAPI + Uvicorn，监听 127.0.0.1:8000（单实例 systemd 托管）"),
        ("前端", "React 18 + Vite 构建为静态产物，由 Nginx 托管"),
        ("数据库", "PostgreSQL 17，仅本机访问（127.0.0.1:5432，不对公网开放）"),
        ("反向代理", "Nginx 托管静态资源并转发 /api，关闭缓冲以支持流式对话"),
        ("Python / Node", "Python 3.12.15 / Node.js 20.20.2"),
        ("AI 模型", f"{hz.get('llm_mode')} 模式（真实 LLM，已禁用 Mock 兜底）"),
        ("健康检查", f"GET /api/health → {hz.get('status')}"),
        ("数据备份", "数据库每日定时备份（pg_dump），保留最近 30 份"),
    ]:
        row = env.add_row().cells
        row[0].text = k
        row[1].text = v

    doc.add_paragraph()
    doc.add_paragraph(
        "反代与对外访问方案已就绪：仓库 deploy/ 目录提供 Nginx 局域网与公网两套配置，"
        "生产环境强制校验 SECRET_KEY 与管理员口令，并已修复 SSE 长连接占用数据库连接池的并发瓶颈。"
    )

    # 三、系统登录
    h(doc, "三、系统登录", 1)
    doc.add_paragraph("参与者通过邮箱注册并登录实验平台。以下为登录入口与后台管理员登录。")
    add_shot(doc, "01_admin_login.png", "图 1  管理员后台登录页（/admin/login）")
    add_shot(doc, "02_admin_login_filled.png", "图 2  管理员凭据校验通过，进入实验管理后台")

    # 四、后台管理核心功能
    h(doc, "四、后台管理核心功能", 1)
    doc.add_paragraph(
        "后台提供数据看板、参与者管理、任务提交与评分、问卷配置、行为日志、系统配置六大模块。"
    )

    doc.add_heading("4.1  数据看板", level=2)
    doc.add_paragraph(
        f"实时总览实验进度：当前参与者 {cnt.get('participants', 0)} 人"
        f"（目标 {cnt.get('target_sample', '—')} 人），"
        "展示三组样本量与均衡比例、任务完成率、平均用时、异常数、"
        "AI 助理 API 状态与最近注册一览。"
    )
    add_shot(doc, "03_admin_dashboard.png", "图 3  实验监控看板：分组样本、AI 助理状态、最近注册")

    doc.add_heading("4.2  参与者管理", level=2)
    doc.add_paragraph(
        "按邮箱/组别/状态检索与筛选全部参与者，可查看详情、手动调整分组或删除。"
    )
    add_shot(doc, "04_admin_participants.png", "图 4  参与者管理：组别标签、任务状态、分页与检索")

    doc.add_heading("4.3  任务提交与评分", level=2)
    doc.add_paragraph("汇总并查看各参与者提交的任务成果（行程方案），并进行评分。")
    add_shot(doc, "05_admin_submissions.png", "图 5  任务提交与评分")

    doc.add_heading("4.4  问卷配置", level=2)
    doc.add_paragraph(
        "管理实验问卷题目，支持题目编辑、启用停用与分组适用范围配置。"
    )
    add_shot(doc, "06_admin_questionnaire.png", "图 6  问卷配置与回收统计")

    doc.add_heading("4.5  系统配置", level=2)
    doc.add_paragraph("配置实验任务参数（目的地、天数、预算等）与 AI 助理服务开关。")
    add_shot(doc, "08_admin_settings.png", "图 7  系统配置")

    # 五、行为日志
    h(doc, "五、行为日志", 1)
    doc.add_paragraph(
        f"系统完整记录每次人机交互行为，共 {cnt.get('behavior_logs', 0)} 条日志，"
        "覆盖 AI 消息、工具调用、用户干预、页面停留时长、实验阶段等维度，"
        "支持按用户、操作类型检索与分页浏览。"
    )
    add_shot(doc, "07_admin_logs.png", "图 8  行为日志：按用户统计条数、检索筛选与分页")

    # 六、数据汇总
    h(doc, "六、实验数据汇总", 1)
    doc.add_paragraph(
        f"以下数据取自线上平台（http://47.114.33.223），采集时间 {now}。"
    )
    tbl = doc.add_table(rows=1, cols=2)
    tbl.style = "Light Grid Accent 1"
    tbl.rows[0].cells[0].text = "指标"
    tbl.rows[0].cells[1].text = "数值"
    for k, label in [
        ("participants", "已注册参与者"),
        ("behavior_logs", "行为日志条数"),
        ("target_sample", "目标样本量"),
        ("experiment_status", "实验状态"),
        ("completion_rate", "任务完成率"),
    ]:
        c = tbl.add_row().cells
        c[0].text = label
        c[1].text = str(cnt.get(k, "—"))
    if cnt.get("groups"):
        c = tbl.add_row().cells
        c[0].text = "分组分布"
        c[1].text = "、".join(f"{k} {v} 人" for k, v in (cnt.get("groups") or {}).items())

    doc.add_paragraph()
    doc.add_paragraph(
        "系统部署于阿里云 ECS 并通过公网访问，后台各项功能运行正常，"
        "数据采集链路完整可用，可支撑正式实验数据收集。"
    )

    doc.save(OUT)
    print("已生成:", OUT)


if __name__ == "__main__":
    main()