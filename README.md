# 人机协作决策实验平台
## Human–AI Collaboration Decision Experiment Platform

> 模板说明：本文件为项目说明文档模板，已按实际技术架构填写，方括号 `[ ]` 内的内容请替换为你的真实信息（姓名、学号、导师、学校、仓库地址等）。

---

## 一、项目简介

本平台用于开展**人机协作决策**的对照实验研究。实验采用**单盲、三组间对照设计**，将参与者随机分配至以下三组：

| 组别 | 含义 | AI 介入程度 |
|------|------|------------|
| **H** | 纯人工（Pure Human） | 无 AI 辅助 |
| **H+SOA** | 单智能体辅助（Single AI Assistant） | 1 个 AI 助理 |
| **H+MOA** | 多智能体辅助（Multi AI Assistants） | 3 个分工 AI 助理 |

核心实验任务为**「杭州 N 日游行程规划」**（默认 N=3，预算 M=1000 元），包含四项子任务：

1. **景点搜索** —— 检索目的地景点信息
2. **文档生成** —— 将规划导出为 Word 文档
3. **提醒设置** —— 设定出行提醒
4. **邮件发送** —— 将行程文档发送给指定收件人

实验通过**行为日志系统**采集参与者操作轨迹，并结合**八因子百分制评分**对最终行程方案的合理性进行量化评估。

---

## 二、技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 · TypeScript · Vite · Tailwind CSS · Zustand · React Router v6 |
| 后端 | Python · FastAPI · SQLAlchemy 2.0（异步）· asyncpg |
| 数据库 | PostgreSQL 17 |
| 实时通信 | SSE（Server-Sent Events），用于 Agent 流式回复与执行状态推送 |
| AI Agent | 基于 LLM API + Function Calling，含 `MockLLMClient` / `RealLLMClient` 工厂模式 |
| 文档生成 | `python-docx` 程序化生成 `.docx` |
| 部署 | Docker（PostgreSQL）· 支持云服务器 / Vercel + Railway |

---

## 三、实验设计与评分

- **分组策略**：区块随机化（Block Randomization），分组信息对参与者不可见（单盲）。
- **样本量**：默认每组 1:1:1 分配（默认 100 人，可按需调整）。
- **行程合理性评分**：八因子百分制（1–10 分 × 权重 + 生态/可持续性调节项），评分标准参考 GB/T 18972-2017《旅游资源分类、调查与评价》。
- **数据维度**：客观行为指标（搜索次数、编辑次数、AI 交互轮次、任务时长等）+ 事后问卷（单盲构念对齐）+ 管理员主观评分。

---

## 四、目录结构

```
travel-experiment-platform/
├── frontend/                 # React + TypeScript 前端
│   ├── src/
│   │   ├── pages/            # 页面（注册、任务、问卷、管理后台等）
│   │   ├── components/       # 组件（ChatWindow、ExecutionLog 等）
│   │   ├── stores/           # Zustand 状态管理
│   │   ├── hooks/            # 自定义 Hook（useBehaviorLogger 等）
│   │   ├── services/         # API 封装
│   │   └── types/            # 类型定义
│   └── vite.config.ts
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── routers/          # 路由（auth/task/search/document/email/agent/log/admin…）
│   │   ├── services/         # 业务逻辑（auth/document/email/group/agent…）
│   │   ├── models/           # ORM 模型（10 张表）
│   │   ├── schemas/          # Pydantic Schema
│   │   ├── deps.py           # 依赖注入（鉴权）
│   │   └── main.py           # 应用入口
│   ├── uploads/              # 运行时生成文件（已被 .gitignore 排除）
│   ├── .env.example          # 环境变量模板
│   └── requirements.txt
├── database/
│   ├── schema.sql            # 建表脚本（10 张表）
│   └── seed.sql              # 初始数据（系统配置、问卷题项）
├── docker-compose.yml        # PostgreSQL 容器编排
├── .gitignore
└── README.md
```

> 数据库共 **10 张表**：`users` / `behavior_logs` / `task_submissions` / `chat_messages` / `questionnaire_items` / `questionnaire_responses` / `admin_scores` / `reminders` / `system_config` / `admin_users`。

---

## 五、环境准备

- **数据库**：PostgreSQL 17
- **Python**：3.11 及以上
- **Node.js**：18 及以上
- **包管理器**：pip / npm

---

## 六、本地运行

> ⚠️ **启动顺序**：数据库 → 后端 → 前端，三者缺一不可。若前端报 `POST /api/auth/register 500 (Internal Server Error)`，通常是**后端或数据库没在运行**（前端代理连不上 `http://127.0.0.1:8000`，vite 返回 500 / ECONNREFUSED），先按下面三步确认服务都已起来，这并非代码报错。

### 1. 数据库（PostgreSQL）

PostgreSQL 不会随系统自启，每次需手动启动。

**方式 A（推荐，需管理员权限）**：以管理员身份打开 PowerShell，启动系统服务：

```powershell
net start postgresql-x64-17
```

**方式 B（无管理员权限时）**：用 `pg_ctl` 直接以普通进程拉起：

```powershell
& "C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" -D "C:\Program Files\PostgreSQL\17\data" start
```

首次运行需导入表结构与初始数据：

```powershell
psql -U postgres -d travel_experiment -f database/schema.sql
psql -U postgres -d travel_experiment -f database/seed.sql
```

（或直接使用 `docker-compose.yml` 拉起 PostgreSQL 容器。）

### 2. 后端

项目已预置 `backend/venv` 虚拟环境，依赖已安装，一般无需重建：

```powershell
cd backend
.\venv\Scripts\activate                                   # Windows 激活虚拟环境
.\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
```

> 若依赖缺失或需重建：`python -m venv venv` → `pip install -r requirements.txt` → `cp .env.example .env`（按需填写）。

后端启动后访问 `http://localhost:8000/docs` 可查看 Swagger API 文档。

### 3. 前端

新开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173` 即可访问实验平台。

---

## 七、环境变量（`.env`）

| 变量 | 说明 | 示例 |
|------|------|------|
| `DATABASE_URL` | 数据库连接串 | `postgresql+asyncpg://postgres:postgres@localhost:5432/travel_experiment` |
| `SECRET_KEY` | JWT 签名密钥（生产环境务必更换） | `change-me` |
| `ALGORITHM` | JWT 算法 | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token 有效期（分钟） | `1440` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 管理员账号 | `admin` / `change-me` |
| `LLM_API_KEY` | LLM 密钥（留空则使用 Mock 模式） | — |
| `LLM_API_BASE_URL` | LLM 接口地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 模型名 | `gpt-4o-mini` |
| `RESEND_API_KEY` | 邮件服务密钥（留空则 Mock） | — |
| `SENDER_EMAIL` | 发件邮箱 | `experiment@example.com` |
| `BING_SEARCH_API_KEY` / `GOOGLE_SEARCH_API_KEY` | 搜索 API 密钥 | — |
| `CORS_ORIGINS` | 跨域白名单 | `http://localhost:5173` |

> ⚠️ `.env` 含有敏感信息，**已被 `.gitignore` 排除，切勿提交到版本库**。请仅提交 `.env.example`。

---

## 八、主要 API 概览

| 模块 | 端点 | 说明 |
|------|------|------|
| 认证 | `POST /api/auth/register` · `/login` · `/consent` | 注册、登录、知情同意 |
| 任务 | `GET /api/task/config` · `/status` · `POST /task/start` · `/submit` | 任务配置与提交 |
| 搜索 | `POST /api/search` | 景点信息检索 |
| 文档 | `POST /api/document/generate` · `GET /api/document/download/{file}` | Word 生成与下载 |
| 提醒 | `POST /api/reminder` | 设置提醒 |
| 邮件 | `POST /api/email/send` | 发送行程邮件 |
| Agent | `POST /api/agent/chat`（SSE） | AI 助理流式对话 |
| 行为日志 | `POST /api/log/batch` | 批量上报操作日志 |
| 管理后台 | `GET /api/admin/dashboard` · `/logs` · `/openclaw/status` · `/scores` | 监控、日志、评分 |

---

## 九、部署（可选）

- **数据库**：使用 Docker Compose 或云托管 PostgreSQL。
- **后端**：Gunicorn + Uvicorn Worker 部署于云服务器 / Railway。
- **前端**：`npm run build` 后静态托管于 Vercel / Nginx。
- 需将 `.env` 中的 `CORS_ORIGINS` 改为生产域名。

---

## 十、作者与致谢

- **作者**：[你的姓名]（[学校名称] [学院/专业] [学号]）
- **指导教师**：[导师姓名]
- **项目类型**：[毕业设计 / 课程项目 / 科研课题]
- **代码仓库**：https://github.com/YYY22610/project01

> 本平台代码结构参考了开源项目 `multi-agent-travel-planner` 的 Agent 分工思路，并改造为人机协作（用户手动驱动）模式。

---

## 十一、许可证

[此处填写许可证，如 MIT / 仅用于学术用途]
