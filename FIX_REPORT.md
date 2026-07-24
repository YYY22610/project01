# 缺陷修复报告（P0 + P1）

> 基于 `FEATURE_COMPLETION_AUDIT.md` 的待决项，本次修复优先级为 🔴 P0 两项 + 🟡 P1 两项（问卷构念对齐、演示差异化）。管理员手动微调分组暂搁置。

## 一、修复结果总览

| 项 | 严重度 | 状态 | 验证 |
|----|--------|------|------|
| consent 后 JWT 刷新 group | 🔴 P0 | 已修复 | e2e 22/22 通过（抽到 SOA 组，token.group=SOA） |
| 邮件失败不再静默记为成功 | 🔴 P0 | 已修复 | 离线校验：配置 key 但发送失败 → `status=failed` → 路由抛 502 |
| 问卷构念对齐需求 | 🟡 P1 | 已修复 | DB 构念 = {trust,autonomy,satisfaction,task_load,future_use,manipulation_check} |
| 演示差异化 + 确认 + 时长 | 🟡 P1 | 已修复 | `demo_watch_seconds=42` 落库；三组差异化演示 + “我已理解”勾选 |
| 前端构建 | — | 已修复 | `npm run build` 通过（顺带修复 3 处既有 TS 类型错误） |

## 二、逐项说明

### 🔴 P0-1：consent 后 JWT 未刷新 → AI 面板对首次会话不可见
**根因**：`userStore.consent()` 调 `/auth/consent` 后只 `fetchMe()` 不刷新 token；而 `Task.tsx` 依赖 token 里的 `group` 决定 `showAI`。分组在 consent 后才分配，注册 token 的 `group=None`，导致 SOA/MOA 用户首次进入任务页看不到 AI 助理面板（重新登录可绕过，真实参与者会卡住）。

**修复**：
- `backend/app/routers/auth.py`：`/auth/consent` 改为返回 `TokenResponse`（含新分组的 JWT），不再返回 `UserResponse`。
- `frontend/src/stores/userStore.ts`：`consent()` 在拿到新 token 后写入 `localStorage` 并同步 store；`completeDemo(watchSeconds?)` 透传时长。
- `frontend/src/services/index.ts`：`demoComplete(watchSeconds?)` 发送 `{watch_seconds}`。

### 🔴 P0-2：邮件失败被静默记为成功
**根因**：`email.py` 路由无论 `send_email()` 返回 `mock_sent`/`sent`/`failed` 一律 200 并记录为完成；真实发送失败时实验数据被污染。

**修复**：`backend/app/routers/email.py`
- `send_email()` 抛异常 → 502（服务异常）。
- 返回 `status == "failed"` → 502（明确失败），不再写入 `task4_email=True`。
- 仅 `mock_sent`/`sent` 视为有效完成。
- `frontend/src/pages/Task.tsx`：`handleSendEmail` 增加 `status === 'failed'` 判断，失败时不标记已发送。

### 🟡 P1：问卷构念对齐需求
**根因**：种子问卷为 TAM 体系（PU/PEOU/trust/SAT/CI/workload），缺感知自主性(autonomy)与操纵检验(manipulation_check)，命名与需求不符。

**修复**：
- `backend/app/models/questionnaire.py`：`construct` 由 `SAEnum` 改为 `String(20)`（与 `group` 列同思路，加删构念无需改库类型）；枚举值更新为 6 个需求构念。
- `backend/app/services/seed_service.py` + `database/seed.sql`：重写为 6 构念 15 题，含 2 道 `choice` 类型（操纵检验），选项正确入库（`options` JSONB）。
- `backend/app/routers/questionnaire.py`、`admin.py`：`item.construct.value` → `item.construct`。
- `frontend/src/pages/Questionnaire.tsx`：构念标签映射更新；新增选择题渲染（操纵检验题）。
- 注：题目要求措辞对 H 组（手动工具）与 SOA/MOA 组（AI）均中性有效，配合操纵检验题满足单盲要求。

### 🟡 P1：演示差异化 + 确认机制 + 时长记录
**根因**：`Demo.tsx` 三组显示相同任务指令，无分组差异化、无“我已理解”确认、无观看时长记录（需求 2.2/2.3）。

**修复**：
- `frontend/src/pages/Demo.tsx`：按 token.group 展示 H/SOA/MOA 三套差异化演示文案；新增“我已理解”勾选（未勾选不能开始任务）；记录进入/离开时长。
- `backend/app/models/user.py` + `schema.sql`：`users` 表新增 `demo_watch_seconds INTEGER`。
- `backend/app/schemas/task.py` + `task.py`：`/task/demo-complete` 接收 `watch_seconds` 并落库。

### 附带：前端构建类型错误（既有，本次暴露）
- `userStore` 接口 `completeDemo` 签名同步为 `(watchSeconds?: number)`。
- `adminStore` 接口 `fetchParticipants` 返回类型由 `Promise<void>` 改为 `Promise<any>`（实现返回了 `res.data`，原声明导致调用处推断为 `never`）。
- `AdminSettings.tsx`：`item.options?.map` 加可选链守卫。

## 三、验证方式

端到端脚本 `e2e_verify.py`（项目根目录，可复用为回归测试）覆盖：
注册 → consent（断言新 token 含 group）→ 人口统计 → 演示(时长) → 任务四子任务（搜索/文档/提醒/邮件）→ 提交 → 问卷(断言 6 构念 + 选择题) → 提交问卷 → 管理后台(dashboard/participants) → 数据库层断言 `demo_watch_seconds` 与构念 → 邮件失败守卫离线校验。

**结果：22/22 通过；`npm run build` 通过。**

## 四、仍建议后续处理（本次未做）
- 🟡 管理员手动微调分组端点（纠偏自动随机分配）。
- 🟢 P2：异常报警、OpenClaw 状态监控、状态机终态（QUESTIONNAIRE_COMPLETED 之后缺最终“已完成”态）、Excel 导出。
- 邮件 `mock_sent` 在演示环境下仍记为完成（符合受控实验预期，无真实收件人）；真实环境配置 `RESEND_API_KEY` 后失败会正确返回 502。
