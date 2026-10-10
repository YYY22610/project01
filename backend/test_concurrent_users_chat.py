"""
并发用户使用 AI 助手压测脚本
================================
模拟 N 个参与者「注册 → 签知情同意 → 强制 SOA 组 → 登录 → 并发调用 /chat(SSE)」，
验证多用户同时使用 AI 助手时后端是否正常（无 429/500/403、SSE 能完整收尾、延迟可接受）。

用法（在 backend 目录下用 venv 运行）：
    ../venv/Scripts/python.exe test_concurrent_users_chat.py [并发数] [每条问题]

依赖：httpx（venv 已装）
注意：会真实调用 LLM（.env 配了真实 Key），会产生少量 token 成本并可能触发限流——
      这正是本测试要观察的点。
"""
import asyncio
import json
import os
import sys
import time

import httpx

BASE = os.environ.get("TEST_BASE", "http://127.0.0.1:8000/api")
EMAIL_PREFIX = "conc_test_"   # 测试账号邮箱前缀，便于清理
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
    """注册 + 签同意 + 强制 SOA + 重新登录，返回 (user_id, chat_token) 或异常。"""
    email = f"{EMAIL_PREFIX}{idx}_{int(time.time())}@example.com"
    pw = "Test@123456"
    # 1) 注册
    r = await client.post(f"{BASE}/auth/register", json={"email": email, "password": pw})
    r.raise_for_status()
    uid = r.json()["user_id"]
    tok = r.json()["access_token"]
    # 2) 签知情同意（10 题问卷）
    r = await client.post(f"{BASE}/auth/consent",
                          json={"agreed": True, "survey": SURVEY},
                          headers={"Authorization": f"Bearer {tok}"})
    r.raise_for_status()
    # 3) 强制分到 SOA（保证可以调 AI 助手）；生效需重新登录
    r = await client.patch(f"{BASE}/admin/participants/{uid}",
                           json={"group": "SOA"},
                           headers={"Authorization": f"Bearer {admin_tok}"})
    r.raise_for_status()
    # 4) 重新登录拿带 SOA 的 token
    r = await client.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return uid, r.json()["access_token"]


async def chat_one(client: httpx.AsyncClient, idx: int, token: str, message: str):
    """对一个用户发起一次 /chat SSE 调用，返回统计字典。"""
    headers = {"Authorization": f"Bearer {token}"}
    started = time.monotonic()
    result = {
        "user": idx,
        "http_status": None,
        "ok": False,
        "error_event": None,
        "chars": 0,
        "latency_ms": 0,
        "note": "",
    }
    try:
        async with client.stream("POST", f"{BASE}/agent/chat",
                                 json={"agent_id": "soa", "message": message},
                                 headers=headers, timeout=180) as resp:
            result["http_status"] = resp.status_code
            if resp.status_code != 200:
                body = await resp.aread()
                result["note"] = body.decode("utf-8", "ignore")[:400]
                result["latency_ms"] = int((time.monotonic() - started) * 1000)
                return result

            event_type = None
            data_buf = []
            content_parts = []
            got_done = False
            async for raw in resp.aiter_lines():
                if raw == "":
                    if event_type == "content":
                        try:
                            content_parts.append(json.loads("".join(data_buf)))
                        except Exception:
                            content_parts.append("".join(data_buf))
                    elif event_type == "done":
                        got_done = True
                    elif event_type == "error":
                        try:
                            result["error_event"] = json.loads("".join(data_buf)).get("error")
                        except Exception:
                            result["error_event"] = "".join(data_buf)
                    elif event_type == "cancelled":
                        result["note"] = "cancelled"
                    event_type = None
                    data_buf = []
                    continue
                if raw.startswith("event:"):
                    event_type = raw[len("event:"):].strip()
                    data_buf = []
                elif raw.startswith("data:"):
                    data_buf.append(raw[len("data:"):].strip())

            full = "".join(content_parts)
            result["chars"] = len(full)
            result["ok"] = got_done and not result["error_event"]
            result["latency_ms"] = int((time.monotonic() - started) * 1000)
            if not got_done and not result["error_event"]:
                result["note"] = "stream ended without done"
    except Exception as e:
        result["note"] = f"{type(e).__name__}: {e}"
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
    return result


async def cleanup():
    """删除本次产生的测试账号，避免污染实验库。"""
    try:
        from app.database import async_session_factory
        from app.models.user import User
        from sqlalchemy import delete, select
        async with async_session_factory() as db:
            res = await db.execute(
                select(User.id).where(User.email.like(f"{EMAIL_PREFIX}%"))
            )
            ids = [row[0] for row in res.all()]
            if ids:
                await db.execute(delete(User).where(User.email.like(f"{EMAIL_PREFIX}%")))
                await db.commit()
        return len(ids)
    except Exception as e:
        return f"清理失败: {e}"


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    message = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MSG
    print(f"[*] 并发数 = {n}，每条问题 = {message[:30]}...")

    if not await health():
        print("[!] 后端未就绪（/api/health 不通），请先启动后端。")
        sys.exit(1)

    limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)
    async with httpx.AsyncClient(limits=limits) as client:
        admin_tok = await admin_token(client)
        print("[*] 初始化测试账号（注册+签同意+分 SOA+登录，串行以避免启动期竞态）...")
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

        print(f"[*] 开始并发调用 AI 助手（{len(tokens)} 人）...")
        t0 = time.monotonic()
        chat_tasks = [chat_one(client, idx, tok, message) for idx, tok in tokens]
        results = await asyncio.gather(*chat_tasks)
        wall = time.monotonic() - t0

        # 汇总
        ok = [r for r in results if r["ok"]]
        fail = [r for r in results if not r["ok"]]
        lats = [r["latency_ms"] for r in results if r["latency_ms"]]
        print("\n==== 结果汇总 ====")
        print(f"总账号: {len(results)}  成功: {len(ok)}  失败: {len(fail)}")
        print(f"墙钟耗时: {wall:.1f}s   平均单用户延迟: "
              f"{(sum(lats)/len(lats)/1000):.1f}s" if lats else "n/a")
        if lats:
            print(f"延迟 min/max: {min(lats)/1000:.1f}s / {max(lats)/1000:.1f}s")
        for r in results:
            flag = "OK " if r["ok"] else "FAIL"
            print(f"  [{flag}] user{r['user']} http={r['http_status']} "
                  f"chars={r['chars']} latency={r['latency_ms']/1000:.1f}s"
                  + (f"  note={r['note']}" if r['note'] else "")
                  + (f"  err={r['error_event']}" if r['error_event'] else ""))
        # 按 HTTP 状态归类失败原因
        from collections import Counter
        http_fail = Counter(r["http_status"] for r in fail if r["http_status"])
        if http_fail:
            print(f"失败 HTTP 状态分布: {dict(http_fail)}")

    print("\n[*] 清理测试账号...")
    cnt = await cleanup()
    print(f"[*] 已删除测试账号: {cnt}")


if __name__ == "__main__":
    asyncio.run(main())
