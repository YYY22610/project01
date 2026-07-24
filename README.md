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

1. **景点搜索** —— 检索目的地景点信息（DuckDuckGo + Bing 爬虫式实时搜索，详见第九节）
2. **文档生成** —— 将规划导出为 Word 文档（内置富文本编辑器，保留排版，详见第九节）
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
| 文档生成 | `python-docx` 程序化生成 `.docx`（支持 HTML 富文本 → 带格式 docx） |
| 景点搜索 | `httpx` + 标准库 `html.parser` 爬取 DuckDuckGo / Bing HTML 结果（爬虫式，无需 API key） |
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
│   │   ├── services/         # 业务逻辑（auth/document/email/group/agent/search…）
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
& "D:\Develop\PostgreSQL\bin\pg_ctl.exe" -D "C:\Program Files\PostgreSQL\17\data" start
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
| 搜索 | `POST /api/search` | 景点信息检索（DuckDuckGo + Bing 爬虫兜底，返回 `source` 标记实时/示例） |
| 文档 | `POST /api/document/generate` · `GET /api/document/download/{file}` | Word 生成与下载 |
| 提醒 | `POST /api/reminder` | 设置提醒 |
| 邮件 | `POST /api/email/send` | 发送行程邮件 |
| Agent | `POST /api/agent/chat`（SSE） | AI 助理流式对话 |
| 行为日志 | `POST /api/log/batch` | 批量上报操作日志 |
| 管理后台 | `GET /api/admin/dashboard` · `/logs` · `/openclaw/status` · `/scores` | 监控、日志、评分 |

---

## 九、功能实现说明（近期更新）

### 9.1 景点搜索（爬虫式实时搜索）

- 后端 `app/services/search_service.py` 使用 `httpx.AsyncClient` 抓取 **DuckDuckGo HTML 搜索结果页**，并用标准库 `html.parser` 自写的 `_ResultExtractor` 状态机解析出 `title / url / snippet`（DuckDuckGo 的 `uddg=` 跳转链接会解码回真实 URL）。
- 若 DuckDuckGo 无结果或请求异常，自动改用 **Bing HTML 结果页**（`li.b_algo > h2 > a` 抓标题、`div.b_caption > p` 抓摘要）兜底。
- **无需任何搜索 API key**，免费零配置；缺点是依赖搜索引擎页面结构，若对方改版可能失效，且存在被限流 / 封 IP 风险。如需更稳定的官方接口，可启用 `.env` 中的 `BING_SEARCH_API_KEY` / `GOOGLE_SEARCH_API_KEY` 作为更高优先级兜底。
- 当外网完全不可达或抓取失败时，路由层回退到本地 10 条杭州示例数据（结果带 `source: "mock"` 标记，前端显示「示例数据」标签）。
- 前端「搜索景点」子任务提供 **搜索引擎 / AI 推荐** 两个子 tab：前者展示可点击跳转的真实搜索结果卡；后者内联调用 Agent（`agentApi.chat('soa', …)` 流式），不污染左侧聊天面板。

### 9.2 文档生成（富文本编辑器 → Word）

- 前端「生成文档」子任务改用内置 **`contenteditable` 富文本编辑器**（仿 `aitravel-main` 项目），支持加粗 / 斜体 / 下划线、H1 / H2 / 正文、有序 / 无序列表、插入表格、清除格式，以及「保存到本地」导出 `.doc`。
- 提交时把编辑器 HTML 传给后端 `POST /api/document/generate`（携带 `format: "html"` 参数）。
- 后端 `app/services/document_service.py` 的 `generate_docx` 用标准库 `html.parser` 将 HTML 转换为**带格式**的 `.docx`（标题层级 / 加粗 / 列表 / 表格均保留），不再丢失排版。

---

## 十、部署（可选）

- **数据库**：使用 Docker Compose 或云托管 PostgreSQL。
- **后端**：Gunicorn + Uvicorn Worker 部署于云服务器 / Railway。
- **前端**：`npm run build` 后静态托管于 Vercel / Nginx。
- 需将 `.env` 中的 `CORS_ORIGINS` 改为生产域名。

---

## 十一、作者与致谢

- **作者**：[你的姓名]（[学校名称] [学院/专业] [学号]）
- **指导教师**：[导师姓名]
- **项目类型**：[毕业设计 / 课程项目 / 科研课题]
- **代码仓库**：https://github.com/YYY22610/project01

> 本平台代码结构参考了开源项目 `multi-agent-travel-planner` 的 Agent 分工思路，并改造为人机协作（用户手动驱动）模式。

---

## 十二、许可证

[此处填写许可证，如 MIT / 仅用于学术用途]
