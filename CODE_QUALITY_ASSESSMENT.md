# 代码质量评估报告 + 团队技术提升方案

> 评估对象：旅行规划实验平台（FastAPI + React 18 + TypeScript + PostgreSQL）
> 评估角色：资深开发工程师（代码质量把控）
> 日期：2026-07-20

---

## 一、架构与工程亮点（先肯定做对的地方）

团队在以下方面有清晰的设计意识，值得保持：

1. **分层清晰**：`routers / services / models` 职责分离，路由只做编排，业务逻辑在 service 层。
2. **状态机抽象**（`state_machine.py`）：用 `VALID_TRANSITIONS` 集中管理实验流程状态流转，避免散落的 if/else，这是很好的领域建模。
3. **JWT 角色分离**：参与者 token 与管理员 token 用 `role` 字段区分（`auth_service.py`、`deps.py`）。
4. **输入校验**：后端用 Pydantic + `EmailStr` 做请求校验，前端有独立 `services` 层封装 axios。
5. **CORS 白名单**：`config.py` 用 `cors_origins_list` 限定来源，而非 `*`。
6. **SSE 流式** Agent 通信已实现（`agent.py` + `useAgentChat.ts`）。

---

## 二、高严重度问题（必须修，否则影响正确性 / 安全 / 实验效度）

### H1. 参与者 JWT 泄露实验分组（单盲被破坏）
- **位置**：`auth_service.py:27-34` 生成 token 时写入 `group`；`Task.tsx:45-67` 前端 `atob(token.split('.')[1])` 解码出 `payload.group`。
- **问题**：单盲设计要求参与者**不知晓自己属于哪组**。但分组（H/SOA/MOA）放进了对参与者可见的 JWT，任何人打开 DevTools 即可解码。这会**污染实验结论**。
- **修复**：参与者 JWT 不携带 `group`，改为后端下发布尔字段 `has_ai_assistant`；前端据此决定是否显示 AI 面板，分组值永远不落前端。

### H2. 硬编码密钥默认值（生产即裸奔）
- **位置**：`config.py:21` `SECRET_KEY = "dev-secret-key-change-in-production"`；`:27` `ADMIN_PASSWORD = "admin123"`。
- **问题**：若 `.env` 漏配，`SECRET_KEY` 为公开字符串，任何人可伪造任意用户/管理员 JWT。
- **修复**：`SECRET_KEY` 改为**必填**（缺失即启动失败），密钥用环境变量注入；管理员初始密码改为首次运行强制改密或随机生成。

### H3. 邮件失败被静默吞掉（实验数据失真）
- **位置**：`email.py:24-33` `try/except` 任意异常都返回 `{"status": "mock_sent"}`。
- **问题**：即使配置了真实 API Key 且发送失败（网络/鉴权错误），也记为"已发送"。子任务 `task4_email` 被错误标记完成，影响实验完成率统计。
- **修复**：区分 `failed` 与 `mock_sent`；真实发送失败时向上抛错或明确标记 `failed`，不伪装成功。

### H4. 真实 LLM 接入会直接报错（Function Calling 不兼容）
- **位置**：`llm_client.py:111-115` `RealLLMClient` 返回 `choice.get("tool_calls")`（OpenAI 为对象列表）；`base_agent.py:65` 却用 `tc["function"]["name"]`（当作 dict）。
- **问题**：Mock 用 dict，真实 API 返回对象，两种结构不一致。一旦接入真模型，工具调用解析必崩。
- **修复**：统一把 `tool_calls` 归一化为 dict 结构后再处理（或在 real client 里做兼容转换）。

### H5. 文档下载接口路径穿越风险
- **位置**：`document.py:59-72` `file_name` 直接来自 URL 参数，仅 `os.path.join(UPLOAD_DIR, file_name)`，未做 `os.path.basename` / `secure_filename` 校验。
- **问题**：`file_name=../../etc/passwd` 可逃逸出 `uploads/documents`。
- **修复**：用 `os.path.basename(file_name)` 截断路径，并校验文件确实位于 `UPLOAD_DIR` 内。

### H6. 分组分配存在并发竞态（破坏 1:1:1）
- **位置**：`group_service.py:10-64`，先 `count` 各组人数再 `random.choice`，全程无数据库行锁/事务隔离。
- **问题**：多人同时签署同意书时，可能读到相同的计数，导致同组超额，破坏随机化平衡。
- **修复**：用 `SELECT ... FOR UPDATE` 锁住计数/用原子自增，或在应用层用分布式锁；至少用 DB 事务保证分配原子性。

---

## 三、中严重度问题（应修，影响可维护性 / 一致性）

### M1. "查找或创建提交记录"逻辑重复 4 次
- **位置**：`document.py:37-53`、`reminder.py:32-43`、`email.py:36-49`、`task.py:68-72,95-99`。
- **问题**：同一套 `SELECT TaskSubmission WHERE user_id` → 存在则更新/不存在则新建 写了四遍，且 document 用裸 SQL（`__table__.update()`），其余用 ORM，风格不一致，易引入笔误。
- **修复**：抽公共函数 `get_or_create_submission(db, user_id)`。

### M2. Agent 工具不落库，AI 组完成度无法追踪
- **位置**：`agent_tools.py:111-117` `set_reminder_tool` 仅返回 dict 不持久化；`:91-96` `generate_docx_tool` 生成文件但不更新 `TaskSubmission.task2_document`。
- **问题**：SOA/MOA 组用户用 AI 完成的子任务，后端 `submission` 标记仍是 false，与 H 组口径不一，实验数据分析会出现系统性偏差。
- **修复**：Agent 工具执行成功后回写对应 `taskN_*` 字段（或统一走与手动相同的服务函数）。

### M3. 任务完成状态"双源"不一致
- **位置**：`Task.tsx:13,148` 本地 `useState` 是完成判定依据；但后端 `taskStatus.submission` 已有持久化结果。
- **问题**：用户中途刷新页面 → 本地状态归零，即使后端已记录完成，页面也显示"未完成"且无法提交。
- **修复**：以 `taskStatus.submission` 为唯一真相源初始化本地状态。

### M4. 真实搜索 API 是死代码
- **位置**：`search.py:31-33` `if settings.BING_SEARCH_API_KEY or settings.GOOGLE_SEARCH_API_KEY: pass`；`config.py:39-40` 配了 Key 却不用。
- **问题**：配了 Key 仍走 Mock，给人"已接入"的错觉。
- **修复**：实现真实调用分支，或删掉无效配置避免误导。

### M5. 流式渲染逐词 setState（性能）
- **位置**：`useAgentChat.ts:34` 每个 `content` chunk 都 `addMessage` 触发全局 store 更新。
- **问题**：长回复会触发几十至上百次重渲染（re-render storm）。
- **修复**：用 ref 累积、节流（如每 50ms / 每 N 词）批量提交一次 UI 更新。

### M6. 问卷提交未校验题项有效性
- **位置**：`questionnaire.py:53-58` 直接 `resp["item_id"]` 写入，未校验该 item 是否存在/启用，也未限制结构。
- **修复**：Pydantic 定义响应项结构；校验 `item_id` 属于当前启用题项。

---

## 四、低严重度 / 规范问题

- **L1** `Task.tsx:32` `hasAI` 变量声明后从未使用（死代码）。
- **L2** `Task.tsx:177,204` 等多处 `.map((_, i) => key={i})` 用数组下标作 key，列表变动时会触发错误复用。
- **L3** `Task.tsx:75,108` 同名的 `search_result_click` 事件含义不一致（一次记数量、一次记标题）。
- **L4** `admin.py` 多个接口 `admin: dict = Depends(get_current_admin)` 返回的是 JWT payload dict 而非模型，与 `get_current_user` 返回模型风格不一。
- **L5** 前端大量 `catch { alert('...') }` 原生弹窗，无统一错误 UI（Register 已改善，其余未跟进）。
- **L6** 多数 API 响应未声明类型（`res.data` 为 `any`），失去 TS 类型保护。
- **L7** 全仓**无自动化测试**，研究平台尤其需要回归测试保障数据正确性。

---

## 五、团队技术提升方案（不止改代码，更要提升人）

### A. 建立"代码评审清单"（PR 必过项）
把上面 H/M 级问题固化为清单，每次 PR 自查：
- [ ] 密钥/配置有无硬编码默认值
- [ ] 用户输入/文件下载有无路径穿越
- [ ] 异常是否被静默吞掉（尤其影响业务判定的）
- [ ] 状态是否单一真相源
- [ ] 重复逻辑是否抽公共函数
- [ ] 实验口径（分组、完成度）前后端是否一致

### B. 用本次问题做"反向教学"
每个 bug 都是教材：
- H1 讲**实验伦理与最小暴露面**；
- H4 讲**Mock 与真实依赖的契约一致性**；
- H6 讲**并发与事务隔离**；
- M5 讲**前端渲染性能与节流**。

### C. 补齐工程底座
1. 引入 `ruff`(Python) + `eslint`/`prettier`(TS) 在提交前自动跑；
2. 编写**至少 3 类测试**：分组分配并发、状态机流转、工具调用解析；
3. 关键接口补 `response_model` + 前端 `interface`，消灭 `any`。

### D. 我可提供的持续支持
- 定期 Code Review（你发 PR 我审）；
- 对高严重度问题**带注释地动手修**，过程中讲解取舍；
- 帮你把清单落成一个可复用的 `CONTRIBUTING.md` / 评审模板。

---

## 六、建议的起步顺序
1. 先修 **H1+H2+H5**（安全/实验效度，半天）；
2. 再修 **H3+H4+M2**（数据真实性，半天）；
3. 最后补 **M1/M3/M5 + 测试底座**（可维护性，1 天）。
