"""
MOA 组群辩并发测试
====================
模拟 N 个参与者「注册 → 签知情同意 → 强制 MOA 组 → 登录 → 并发 /moa/group-discuss(SSE)」，
并自动处理群辩里的两个交互暂停点：
  - await_user   → 调用 /moa/group-resume 回填一个偏好回答（让讨论继续）
  - await_confirm→ 调用 /moa/group-resume 回填「确认」跳出确认门（拿到最终方案）

验证多个用户同时跑 MOA 群辩时后端是否正常：
  - 无 500 / 连接池耗尽 / 致命竞态
  - 每人都能跑完整场（收到 done 事件，拿到最终 plan markdown）
  - 交互暂停点能被正确回填恢复

用法（backend 目录下，venv 运行）：
    ../venv/Scripts/python.exe test_concurrent_moa_chat.py [并发数]

注意：MOA 每场约 11 次 LLM 调用（主持人开场/草案/整合 + 4 专家×2 轮），
比 SOA 重很多；真实模型下若触发限流会优雅降级为脚本兜底内容，讨论仍会跑完。
因此并发数默认 5（避免把 API 额度打满），可自行加参数提高。
"""
import asyncio
import json
import os
import sys
import time

import httpx

BASE = os.environ.get("TEST_BASE", "http://127.0.0.1:8000/api")
EMAIL_PREFIX = "moa_test_"   # 测试账号邮箱前缀，便于清理
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
DEFAULT_MSG = "帮我规划一个杭州三天游，预算3000元，两个人，希望多去些自然风光和本地美食。"

SURVEY = {
    "q1": "yes",
    "q2": "both",
    "q3": "often",
    "q4": ["agent_helpful"],
    "q5": "m_3_6",
    "q6": "female",
    "q7": "25-34",
    "q8": "bachelor",
    "q9": "unmarried",
    "q10": "student",
}

# 每个用户被问到「偏好」时回填的回答（差异化，模拟真实）
FAKE_ANSWERS = [
    "我更看重吃好喝好，两个人，其中一人不吃辣。",
    "想省钱为主，预算尽量控制在 2500 以内。",
    "希望文化沉浸多一点，喜欢博物馆和历史街区。",
    "出片好看最重要，想拍很多风景照。",
    "想兼顾，别太赶，每天留点自由时间。",
    "带老人同行，体力一般，不要太多爬山。",
    "美食优先，想尝地道小吃，住宿干净就行。",
    "自然风光为主，最好有湖有山。",
    "预算宽松，想住得舒服一点，靠近地铁。",
    "想体验禅意慢游，少网红打卡点。",
]


async def health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{BASE}/health")
            return r.status_code == 200
    except Exception:
        return False


async def admin_token(client: httpx.AsyncClient) -> str:
    r = await client.post(f"{BASE}/auth/admin/login",
                          json={"username": ADMIN_USER, "password": ADMIN_PASS})
    r.raise_for_status()
    return r.json()["access_token"]


async def onboard_user(client: httpx.AsyncClient, admin_tok: str, idx: int):
    """注册 + 签同意 + 强制 MOA + 重新登录，返回 (user_id, token) 或异常。"""
    email = f"{EMAIL_PREFIX}{idx}_{int(time.time())}@example.com"
    pw = "Test@123456"
    r = await client.post(f"{BASE}/auth/register", json={"email": email, "password": pw})
    r.raise_for_status()
    uid = r.json()["user_id"]
    tok = r.json()["access_token"]
    r = await client.post(f"{BASE}/auth/consent",
                          json={"agreed": True, "survey": SURVEY},
                          headers={"Authorization": f"Bearer {tok}"})
    r.raise_for_status()
    # 强制分到 MOA（保证可以跑群辩）
    r = await client.patch(f"{BASE}/admin/participants/{uid}",
                           json={"group": "MOA"},
                           headers={"Authorization": f"Bearer {admin_tok}"})
    r.raise_for_status()
    r = await client.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return uid, r.json()["access_token"]


async def _resume(token: str, message: str):
    """调用 /moa/group-resume 回填用户回答，恢复群聊。"""
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{BASE}/moa/group-resume",
                         json={"message": message},
                         headers={"Authorization": f"Bearer {token}"})
        return r.status_code, r.text, int((time.monotonic() - t0) * 1000)


async def discuss_one(client: httpx.AsyncClient, idx: int, token: str, message: str):
    """对一个 MOA 用户跑完整场群辩（含自动回填 await_user / await_confirm）。"""
    headers = {"Authorization": f"Bearer {token}"}
    started = time.monotonic()
    result = {
        "user": idx, "http_status": None, "ok": False,
        "error_event": None, "plan_chars": 0, "latency_ms": 0,
        "stages": 0, "got_done": False, "resumes": 0, "resume_ms": 0, "note": "",
    }
    try:
        async with client.stream("POST", f"{BASE}/moa/group-discuss",
                                 json={"message": message, "dest": "杭州", "days": 3,
                                       "budget": 2000, "travelers": "2 人"},
                                 headers=headers, timeout=600) as resp:
            result["http_status"] = resp.status_code
            if resp.status_code != 200:
                body = await resp.aread()
                result["note"] = body.decode("utf-8", "ignore")[:400]
                result["latency_ms"] = int((time.monotonic() - started) * 1000)
                return result

            event_type = None
            data_buf = []
            plan_md = ""
            async for raw in resp.aiter_lines():
                if raw == "":
                    if event_type == "error":
                        try:
                            result["error_event"] = json.loads("".join(data_buf)).get("error")
                        except Exception:
                            result["error_event"] = "".join(data_buf)
                    elif event_type == "stage":
                        result["stages"] += 1
                    elif event_type == "done":
                        result["got_done"] = True
                        try:
                            d = json.loads("".join(data_buf))
                            plan_md = (d.get("plan", {}) or {}).get("markdown", "") or ""
                        except Exception:
                            pass
                    elif event_type == "await_user":
                        # 暂停等待用户偏好 → 回填
                        result["resumes"] += 1
                        sc, _, ms = await _resume(token,
                                                  FAKE_ANSWERS[idx % len(FAKE_ANSWERS)])
                        if sc != 200:
                            result["note"] = f"resume(await_user) http={sc}"
                        else:
                            result["resume_ms"] = ms
                    elif event_type == "await_confirm":
                        # 确认门 → 回填「确认」跳出
                        result["resumes"] += 1
                        sc, _, ms = await _resume(token, "确认")
                        if sc != 200:
                            result["note"] = f"resume(await_confirm) http={sc}"
                        else:
                            result["resume_ms"] = ms
                    event_type = None
                    data_buf = []
                    continue
                if raw.startswith("event:"):
                    event_type = raw[len("event:"):].strip()
                    data_buf = []
                elif raw.startswith("data:"):
                    data_buf.append(raw[len("data:"):].strip())

            result["plan_chars"] = len(plan_md)
            result["ok"] = result["got_done"] and not result["error_event"]
            result["latency_ms"] = int((time.monotonic() - started) * 1000)
            if not result["got_done"] and not result["error_event"]:
                result["note"] = (result["note"] or "") + " stream ended without done"
    except Exception as e:
        result["note"] = f"{type(e).__name__}: {e}"
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
    return result


async def cleanup():
    try:
        from app.database import async_session_factory
        from app.models.user import User
        from app.models.moa_group_session import MoaGroupSession
        from sqlalchemy import delete, select
        async with async_session_factory() as db:
            # 先删子表（MOA 会话态），再删用户，避免外键约束报错
            await db.execute(
                delete(MoaGroupSession).where(
                    MoaGroupSession.user_id.in_(
                        select(User.id).where(User.email.like(f"{EMAIL_PREFIX}%"))
                    )
                )
            )
            await db.execute(delete(User).where(User.email.like(f"{EMAIL_PREFIX}%")))
            await db.commit()
        return "ok"
    except Exception as e:
        return f"清理失败: {e}"


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(f"[*] MOA 并发数 = {n}，需求 = {DEFAULT_MSG[:24]}...")

    if not await health():
        print("[!] 后端未就绪（/api/health 不通），请先启动后端。")
        sys.exit(1)

    limits = httpx.Limits(max_connections=100, max_keepalive_connections=40)
    # 关键：SSE 流在 LLM 调用间隙会有数秒空闲（专家并发轮），
    # 必须把读超时设大，否则默认 5s 读超时会在空闲间隙误杀连接。
    timeout = httpx.Timeout(connect=10, read=600, write=60, pool=30)
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        admin_tok = await admin_token(client)
        print("[*] 初始化测试账号（注册+签同意+分 MOA+登录，串行）...")
        tokens = []
        for i in range(n):
            try:
                _, tok = await onboard_user(client, admin_tok, i)
                tokens.append((i, tok))
            except Exception as e:
                print(f"  - 用户{i} 初始化失败: {type(e).__name__}: {e}")

        if not tokens:
            print("[!] 没有可用账号，终止。")
            return

        print(f"[*] 开始并发 MOA 群辩（{len(tokens)} 人）...")
        t0 = time.monotonic()
        tasks = [discuss_one(client, idx, tok, DEFAULT_MSG) for idx, tok in tokens]
        results = await asyncio.gather(*tasks)
        wall = time.monotonic() - t0

        ok = [r for r in results if r["ok"]]
        fail = [r for r in results if not r["ok"]]
        lats = [r["latency_ms"] for r in results if r["latency_ms"]]
        print("\n==== MOA 群辩结果汇总 ====")
        print(f"总账号: {len(results)}  成功(done且无error): {len(ok)}  失败: {len(fail)}")
        print(f"墙钟耗时: {wall:.1f}s   平均单用户延迟: "
              f"{(sum(lats)/len(lats)/1000):.1f}s" if lats else "n/a")
        if lats:
            print(f"延迟 min/max: {min(lats)/1000:.1f}s / {max(lats)/1000:.1f}s")
        for r in results:
            flag = "OK " if r["ok"] else "FAIL"
            print(f"  [{flag}] user{r['user']} http={r['http_status']} "
                  f"stages={r['stages']} resumes={r['resumes']} "
                  f"resume_ms={r['resume_ms']} "
                  f"plan_chars={r['plan_chars']} latency={r['latency_ms']/1000:.1f}s"
                  + (f"  note={r['note']}" if r['note'] else "")
                  + (f"  err={r['error_event']}" if r['error_event'] else ""))

    print("\n[*] 清理测试账号...")
    print(f"[*] {await cleanup()}")


if __name__ == "__main__":
    asyncio.run(main())
