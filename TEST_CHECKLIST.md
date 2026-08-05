# 人机协作决策实验平台 — 已完成任务检测清单

> 用途：逐条检测上一轮完成的功能。每条含「改了什么」+「怎么测」+「预期结果」。
> 环境前提：
> - 后端需先启动（真实 PostgreSQL 已在 5432 运行）。
>   - 启动：`cd backend && .\venv\Scripts\Activate.ps1 && uvicorn app.main:app --reload --port 8000`
> - 前端需先 `npm run dev`（默认 5173，代理到 127.0.0.1:8000）。
> - 若要用真实 LLM/邮件，需**重启后端**使 .env 中新填的 Qwen Key、QQ 邮箱授权码生效（mock 测试不需要）。

---

## ✅ 任务 A：端到端冒烟测试（6 功能 / 16 断言全 PASS）

**改了什么**
- 新增 `backend/test_e2e_smoke.py`：强制 mock LLM，真实 JWT 登录，覆盖 ①注册分组 ②H 组界面 ③SOA 对话 ④Word 生成 ⑤提醒设置 ⑥邮件发送 六功能。

**怎么测**
```powershell
cd D:\27475\WorkBuddy-搭建网站\travel-experiment-platform\backend
.\venv\Scripts\python.exe test_e2e_smoke.py
```

**预期结果**
- 输出 `16 passed` / `All 16 assertions passed`，无报错。
- 踩坑已规避：枚举用 Python 比较而非进 SQL WHERE；cleanup 与 run 同一事件循环内 `engine.dispose()`。

---

## ✅ 任务 B：SSE 实时状态日志渲染（提问时实时显示助理在做什么）

**改了什么**
- 后端 `agent_tools.py`：新增 `TOOL_STATUS_LABELS`（5 个工具 calling/done 中文文案）+ `get_tool_status_label()`。
- 后端 `base_agent.py`：tool_call / tool_result 事件加 `status` 字段。
- 前端 `chatStore.ts`：`ToolActivity` 增加 `id/status/state('calling'|'done')`，新增 `addToolCall/completeToolCall/resetToolActivity/setStatusText`。
- 前端 `useAgentChat.ts`：消费 tool_call/tool_result 事件更新状态。
- 前端 `ChatWindow.tsx`：新增 `AgentStatusPanel` / `ActivityStep`（调用中转圈、完成绿勾）。

**怎么测**
1. 启动前后端，用 SOA 或 MOA 组账号登录进入对话页。
2. 发送会触发工具的消息（如「帮我搜索杭州西湖景点并生成行程 Word」）。
3. 观察对话区底部状态面板。

**预期结果**
- 流式回复过程中，状态面板**逐条实时出现**：
  - 🔄 正在调用搜索引擎… → ✅ 搜索完成
  - 🔄 正在生成 Word 文档… → ✅ 文档生成完成
  - （以此类推，每个工具一步）
- 不再是「干等最后出结果」，而是边做边显示。

---

## ✅ 任务 C：干预能力（随时中断助理当前操作，重下指令）

**改了什么**
- 后端 `agent_cancel.py`：新增 `AgentCancelManager` 单例（按 user_id+agent_id 维度，asyncio.Lock）。
- 后端 `base_agent.py`：`chat()` 新增 `cancel_check` 检查点；3 处检查点（首轮 LLM 后 / 每个工具前 / 二次 LLM 前）`if await _is_cancelled(): yield cancelled; return`。
- 后端 `agent.py`：流式起始 `reset_cancel`；新增 `POST /cancel`（校验 agent_id 归属：SOA→soa，MOA→moa_a/moa_b）；行为日志记 `cancelled` 与 `is_success`。
- 后端 `schemas/agent.py`：新增 `CancelRequest(agent_id)`。
- 前端 `chatStore.ts`：新增 `cancelled` 状态 + `setCancelled`。
- 前端 `useAgentChat.ts`：`AbortController` + `cancel()`（先置位 `/cancel` → `abort()` → 更新 UI）。
- 前端 `ChatWindow.tsx`：流式时底部出现红色 ■ 停止按钮，点击调用 `cancel()`。
- 前端 `services/index.ts`：新增 `agentApi.cancel(agentId)`，捕获 `AbortError` 静默。

**怎么测**
1. 启动前后端，SOA/MOA 账号进入对话页。
2. 发送会触发**多工具串联**的消息（如「搜索杭州景点 → 生成 Word → 设置提醒 → 发邮件」）。
3. 在助理执行到中途（如刚搜完、正在生成 Word 时）点击红色 ■ 停止按钮。
4. 观察状态面板与对话。
5. 中断后，重新输入一条新指令并发送。

**预期结果**
- 点击停止后：下一个待执行工具被**真正拦住**，状态面板显示「⛔ 已中断 / 操作被用户取消」。
- 已完成的那一步（如搜索）结果保留，未执行的后续步骤不再运行。
- 中断后可立即发新指令，助理正常响应（新会话不受上次取消影响）。
- 越权测试：`POST /api/agent/cancel` 带他人 agent_id 返回 400；未登录返回 401（已在 `test_cancel_flow.py` 断言）。

---

## 🐞 任务 D & E：干预实现过程中修复的两个真实 Bug

**Bug①：取消检查点被「假触发」**
- 现象：`_cancelled()` 直接 `bool(cancel_check())` 而传入的是 async 协程 → 协程对象恒为 truthy → 取消**永远触发**（一进来就中断）。
- 修复：`async def _is_cancelled(): return bool(await cancel_check())`，3 处检查点改为 `await _is_cancelled()`。
- 验证：修复后未取消时流程正常跑完；取消时只在检查点停。

**Bug②：SSE 响应体缩进错位**
- 现象：编辑 `agent.py` 时误把 `return StreamingResponse(...)` 移进 `/cancel` 端点内部，导致 `agent_chat` 返回 `None` → SSE 实际返回 `application/json null`。
- 修复：将 `return StreamingResponse(...)` 复位到 `agent_chat` 函数层级（修正缩进）。
- 验证：`test_e2e_smoke.py` 16/16 仍 PASS，且前端能收到真实 event-stream。

---

## 📌 复测辅助脚本
- `backend/test_e2e_smoke.py` — 6 功能回归（16 断言）。
- `backend/test_cancel_flow.py` — 干预专项（6 断言：取消后下一工具不执行 / 鉴权 / 越权）。

**建议检测顺序**：先跑 A（脚本回归）→ 再手动测 B（看状态面板）→ 最后测 C（点停止按钮中断 + 重发）。
