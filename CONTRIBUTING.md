# CONTRIBUTING.md — 旅行规划实验平台 开发规范

> 本文档定义团队的代码标准、评审流程与架构铁律。所有 PR 必须遵循。
> 维护者：资深开发工程师（代码质量把控）

---

## 1. 技术栈

- **后端**：Python 3.13 + FastAPI + SQLAlchemy 2.0（async）+ asyncpg + PostgreSQL 17
- **前端**：React 18 + TypeScript + Vite + Tailwind CSS + Zustand
- 依赖见 `backend/requirements.txt` 与 `frontend/package.json`

## 2. 本地环境

- PostgreSQL 17 安装在 `D:\Develop\PostgreSQL`，端口 `5432`，账号 `postgres/postgres`，库名 `travel_experiment`
- 后端虚拟环境：`backend/venv/`（已装 bcrypt==4.0.1，注意与 passlib 1.7.4 的兼容）
- 启动后端：`backend> venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- 启动前端：`frontend> node node_modules/vite/bin/vite.js --host`
- ⚠️ **Vite 代理 target 必须用 `http://127.0.0.1:8000`**（Node 22 把 `localhost` 解析为 IPv6 `::1`，会导致 `ECONNREFUSED`）

## 3. 分支与提交

- 主分支 `main`；功能分支 `feature/xxx`；修复分支 `fix/xxx`
- 提交信息遵循 Conventional Commits：`feat/fix/docs/refactor/test/chore(scope): 简述`

## 4. PR 流程

1. 提交前 **self-review** 并逐项勾选《代码评审清单》（见 `docs/代码评审清单.md`）
2. 至少 1 名成员评审通过；**安全类 / 实验效度类改动须资深开发者终审**
3. CI（lint + test）全绿方可合并

## 5. 架构铁律（团队共识，源自真实事故）

> 这些不是建议，是红线。每条都对应一次已发生的线上/实验事故。

1. **单盲不可破坏**：参与者 JWT 与前端**不得**携带或解码实验分组（`group`）值。需要"是否显示 AI 面板"时，由后端下发布尔字段 `has_ai_assistant`。
   *事故：JWT 写入 group，前端 `atob` 解码即可知分组 → 单盲失效（auth_service.py / Task.tsx）*
2. **密钥零硬编码**：`SECRET_KEY`、密码、API Key 一律走环境变量；**不允许**带可被直接用于生产的默认值。
   *事故：SECRET_KEY 默认 `"dev-secret-key-change-in-production"`，漏配即人人可伪造 JWT（config.py）*
3. **异常不静默**：影响业务判定的异常必须上抛或明确标记失败，**禁止** `except: return {"status":"ok"}` 式伪装成功。
   *事故：邮件发送失败被吞，记为 `mock_sent`，子任务完成度失真（email.py）*
4. **唯一真相源**：任务完成状态以 `taskStatus.submission`（后端）为准；前端本地 state 仅作交互缓存，初始化须从后端同步，禁止以本地 state 作为提交判定。
   *事故：刷新页面后本地状态归零，已完成的任务显示"未完成"无法提交（Task.tsx）*
5. **Agent 工具必落库**：AI 完成的子任务必须回写 `TaskSubmission` 对应字段，与人工组口径完全一致。
   *事故：Agent 的 set_reminder / generate_docx 不持久化，AI 组完成度无法统计（agent_tools.py）*
6. **文件下载须校验**：用户可控的文件名必须用 `os.path.basename` 截断，并确认最终路径落在允许目录内。
   *事故：下载接口直接 `os.path.join(UPLOAD_DIR, file_name)`，存在路径穿越（document.py）*
7. **Mock 与真实依赖契约一致**：切换 Mock/Real 实现时，返回结构（如 LLM 的 `tool_calls`）必须归一化为同一形态再处理。
   *事故：Mock 返回 dict，真实 API 返回对象，接入真模型即崩（llm_client.py / base_agent.py）*

## 6. 代码风格

- **Python**：`ruff`（启用 E/F/I 规则）+ 完整类型注解；`async` 函数务必 `await`
- **TypeScript**：`eslint` + `prettier`；**禁用 `any`**（API 响应必须声明 `interface`）；列表 `key` 用稳定 id 而非数组下标
- 重复逻辑（如"查找或创建 submission"）必须抽公共函数，禁止复制粘贴 4 份

## 7. 测试要求

- **必含用例**：分组分配并发安全、状态机非法流转拒绝、LLM `tool_calls` 解析（Mock 与 Real 两种结构）
- 提交功能改动须带相应测试，`pytest` 全绿

## 8. 安全红线

- 不在代码、日志、提交中打印密钥
- 所有用户输入、文件下载路径做校验
- 管理类接口必须经由 `get_current_admin` 校验 `role`
