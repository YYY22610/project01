# 部署指南：实验室局域网 vs 公网

本平台是「前端（React/Vite）+ 后端（FastAPI/PostgreSQL）」单体，两种部署目标**用同一套代码**，差异只在「是否加密 / 是否有域名 / 是否真发邮件」。下面先给结论清单，再给步骤。

---

## 一、分别需要哪些东西

### 实验室局域网（最快，约 10 分钟）
| 需要 | 说明 |
|---|---|
| 一台内网可达的机器（开发机/实验室服务器） | 跑后端 + 前端构建产物 |
| 已装 PostgreSQL 并已建库 `travel_experiment` | 沿用现有库即可 |
| Python venv + Node 已就绪 | 见下步骤 |
| **不需要** 域名、证书、公网 IP、真实 SMTP | 提醒邮件走 mock，不真发 |
| 一台内网可达的机器（开发机/实验室服务器） | 跑后端 + 前端构建产物 |

访问方式：参与者在同一 WiFi/网段，浏览器打开 `http://<服务器内网IP>`。

### 公网（约 1–2 小时，含证书申请）
| 需要 | 说明 |
|---|---|
| 一台有**公网 IP** 的服务器（阿里云/腾讯云等） | 1 核 2G 即可承载 100 人实验 |
| 一个**已备案域名**，DNS 的 A 记录指向该服务器 | 国内服务器必须备案 |
| **TLS 证书**（Let's Encrypt，免费） | 浏览器对跨设备/公网强制要求 HTTPS |
| **真实 SMTP**（QQ/163/腾讯企业邮等） | 提醒邮件要真发到参与者邮箱 |
| 防火墙放行 80/443，数据库端口**不**对外 | 5432 只绑 127.0.0.1 |
| LLM API Key（DashScope 等） | Agent 对话需要 |

访问方式：参与者任意网络，浏览器打开 `https://你的域名`。

---

## 二、两者通用步骤

1. **构建前端**
   ```bash
   cd frontend && npm install && npm run build   # 产物在 frontend/dist/
   ```
   前端 API 地址写死为相对路径 `/api`，因此只要 nginx 同域反代，无需改任何前端代码。

2. **配置生产环境**
   复制 `deploy/.env.production.template` 为 `backend/.env`，逐项填写。
   - `APP_ENV=production` 会**强制**要求 `SECRET_KEY`（≥32 位随机串）与 `ADMIN_PASSWORD`（≠admin123），否则启动直接报错。
   - 生成随机密钥：`python -c "import secrets; print(secrets.token_hex(32))"`。

3. **启动后端（单实例，关键）**
   ```bash
   cd backend && ./venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
   ```
   ⚠️ **必须 `--workers 1`，且全平台只允许一个进程/一台机器跑后端。** 提醒调度器（每 30 秒扫到期提醒发邮件）是进程内单协程，多实例会因无行锁而重复发信。可用 `deploy/travel-experiment.service`（systemd）或 `deploy/start.sh` 托管，崩溃自启。

4. **配置并启用 Nginx 反代**
   - 局域网：`sudo cp deploy/nginx-lan.conf /etc/nginx/sites-enabled/`，把 `server_name` 改成服务器内网 IP。
   - 公网：先 `sudo certbot --nginx -d 你的域名` 申请证书，再 `sudo cp deploy/nginx-public.conf /etc/nginx/sites-enabled/`，改好域名与证书路径。
   - 校验并重载：`sudo nginx -t && sudo systemctl reload nginx`。

   Nginx 同时承担：① 托管 `frontend/dist` 静态文件；② 把 `/api` 转发到本机 8000；③ **关闭 `/api` 的缓冲**（`proxy_buffering off`），否则 SSE 流式对话（智囊团/单助理）前端收不到实时推送。

5. **验证**
   - 浏览器打开站点 → 注册 → 进入 Agent 对话 / 智囊团讨论，确认能流式出字、能导出 Word。
   - `curl https://你的域名/api/health` 返回 `{"status":"ok"}`。

---

## 三、两种目标的核心差异（一句话）

| 维度 | 局域网 | 公网 |
|---|---|---|
| 传输加密 | 明文 HTTP | HTTPS（证书） |
| 入口 | 内网 IP | 已备案域名 |
| 邮件 | mock 不发 | 真实 SMTP |
| 风险面 | 仅内网 | 全网，需 HSTS/防火墙 |
| 适合 | 实验室可控环境 | 跨地域招募参与者 |

---

## 四、部署前必须已知的关键约束

1. **连接池已修复**：原 SSE 流会整场对话长占一条数据库连接（数分钟），30+ 人同时对话会耗尽 30 条连接导致全平台阻塞。本次已将流内 DB 读写改为「短会话即用即关」，回归测试 `backend/test_connection_pool.py` 已锁定该不变量（LLM 推理期间连接池 checkedout=0）。
2. **单实例约束**（见上）：提醒调度器进程内运行，禁止多 worker/多实例。
3. **生产密钥强制**：`APP_ENV=production` 下默认 `SECRET_KEY`/`ADMIN_PASSWORD` 会被拒绝启动——上线前务必改。
4. **数据隐私**：参与者邮箱、问卷属于个人信息。局域网在可控环境即可；公网务必 HTTPS + 服务器访问控制，不要图省事走「发布为应用」类云 Demo（那是为展示用的，不适合承载真实实验数据）。

---

## 五、临时快速验证（仅局域网，非生产）

适合实验室当场让同网段同学点开看效果，跳过 nginx。

- **Windows 一键版**：直接双击 `deploy/start-lan-windows.bat`。它会开两个窗口（后端 0.0.0.0:8000 + 前端 0.0.0.0:5173），并提示你先把 `backend/.env` 的 `CORS_ORIGINS` 加上 `http://<本机IP>:5173`。⚠️ 与本机开发调试共用 8000/5173 端口，启动前请先结束正在跑的开发服务器。
- **手动版（任意系统）**：
  ```bash
  # 后端
  cd backend && ./venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
  # 前端（开发服务器，允许局域网访问）
  cd frontend && npm run dev -- --host 0.0.0.0 --port 5173
  ```
  并把 `backend/.env` 的 `CORS_ORIGINS` 加上 `http://<你的IP>:5173`。

**注意**：开发服务器每次改代码热更新、无 TLS、无静态压缩，只适合演示，正式实验请用 nginx 生产方案（见上）。
