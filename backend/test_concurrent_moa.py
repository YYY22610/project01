"""
MOA 组群辩并发压测脚本
======================
模拟 N 个参与者「注册 → 签知情同意 → 强制 MOA 组 → 登录 → 并发发起群辩(SSE)」，
验证多用户同时使用 MOA 智囊团（另一条代码路径，区别于 /agent/chat）时后端是否正常。

与 test_concurrent_users_chat.py 的区别：
  - 用户组强制 MOA（否则 /moa/group-discuss 返回 403）
  - 群辩中途会暂停等用户输入：await_user（问偏好）与 await_confirm（确认门），
    本脚本在流式读取时自动调用 /moa/group-resume 回填，使讨论走到 done。

用法（在 backend 目录下用 venv 运行）：
    ../venv/Scripts/python.exe test_concurrent_moa.py [并发数]

依赖：httpx（venv 已装）。会真实调用 LLM，token 成本高于单 agent（每人约 7 次 LLM 调用）。
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
    "q1": "yes", "q2": "both", "q3": "often",
    "q4": ["agent_helpful"], "q5": "m_3_6", "q6": "female",
    "q7": "25-34", "q8": "bachelor", "q9": "unmarried", "q10": "student",
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
    # 强制分到 MOA（保证可以调智囊团）
    r = await client.patch(f"{BASE}/admin/participants/{uid}",
                           json={"group": "MOA"},
                           headers={"Authorization": f"Bearer {admin_tok}"})
    r.raise_for_status()
    r = await client.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return uid, r.json()["access_token"]


async def moa_one(client: httpx.AsyncClient, idx: int, token: str, message: str):
    """对一个用户发起一次 /moa/group-discuss SSE 群辩，自动处理 await_user/await_confirm 回填。"""
    headers = {"Authorization": f"Bearer {token}"}
    started = time.monotonic()
    result = {
        "user": idx, "http_status": None, "ok": False,
        "error_event": None, "chars": 0, "latency_ms": 0,
        "await_user": 0, "await_confirm": 0, "stages": 0, "note": "",
    }
    # 独立的 resume 客户端（与流式读取共用 host 连接池上限分开，避免互相阻塞）
    resume_client = httpx.AsyncClient(
        headers=headers, timeout=30,
        limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
    )
    try:
        async with client.stream(
            "POST", f"{BASE}/moa/group-discuss",
            json={"message": message, "dest": "杭州", "days": 3, "budget": 3000, "travelers": "2 人"},
            headers=headers, timeout=600,
        ) as resp:
            result["http_status"] = resp.status_code
            if resp.status_code != 200:
                body = await resp.aread()
                result["note"] = body.decode("utf-8", "ignore")[:400]
                result["latency_ms"] = int((time.monotonic() - started) * 1000)
                await resume_client.aclose()
                return result

            event_type = None
            data_buf = []
            content_chars = 0
            got_done = False

            async def send_resume(text: str):
                try:
                    rr = await resume_client.post(
                        f"{BASE}/moa/group-resume", json={"message": text})
                    return rr.status_code == 200
                except Exception as e:
                    result["note"] = f"resume 失败 {type(e).__name__}: {e}"
                    return False

            async for raw in resp.aiter_lines():
                if raw == "":
                    if event_type == "content":
                        try:
                            d = json.loads("".join(data_buf))
                            content_chars += len(d.get("delta", ""))
                        except Exception:
                            pass
                    elif event_type == "stage":
                        result["stages"] += 1
                    elif event_type == "await_user":
                        result["await_user"] += 1
                        await send_resume("我更看重吃好喝好，同行两人，其中一人不吃辣。")
                    elif event_type == "await_confirm":
                        result["await_confirm"] += 1
                        # 确认门：用 is_confirm 命中词（确认/可以/同意…）让其跳出修订循环
                        await send_resume("确认")
                    elif event_type == "done":
                        got_done = True
                    elif event_type == "error":
                        try:
                            result["error_event"] = json.loads("".join(data_buf)).get("error")
                        except Exception:
                            result["error_event"] = "".join(data_buf)
                    event_type = None
                    data_buf = []
                    continue
                if raw.startswith("event:"):
                    event_type = raw[len("event:"):].strip()
                    data_buf = []
                elif raw.startswith("data:"):
                    data_buf.append(raw[len("data:"):].strip())

            result["chars"] = content_chars
            result["ok"] = got_done and not result["error_event"]
            result["latency_ms"] = int((time.monotonic() - started) * 1000)
            if not got_done and not result["error_event"]:
                result["note"] = (
                    f"stream ended without done (await_user={result['await_user']},"
                    f" await_confirm={result['await_confirm']})"
                )
    except Exception as e:
        result["note"] = f"{type(e).__name__}: {e}"
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
    finally:
        try:
            await resume_client.aclose()
        except Exception:
            pass
    return result


async def cleanup():
    try:
        from app.database import async_session_factory
        from sqlalchemy import text
        # 先删所有引用 users 的从表（按 user_id 子查询），再删 users，避免外键约束冲突
        dep_tables = [
            "chat_messages", "questionnaire_responses", "moa_group_sessions",
            "behavior_logs", "admin_scores", "reminders", "task_submissions",
        ]
        async with async_session_factory() as db:
            for t in dep_tables:
                await db.execute(
                    text(f"DELETE FROM {t} WHERE user_id IN "
                         f"(SELECT id FROM users WHERE email LIKE :p)"),
                    {"p": f"{EMAIL_PREFIX}%"})
            await db.execute(text("DELETE FROM users WHERE email LIKE :p"),
                            {"p": f"{EMAIL_PREFIX}%"})
            await db.commit()
        return "ok"
    except Exception as e:
        return f"清理失败: {e}"


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    print(f"[*] MOA 并发数 = {n}，问题 = {DEFAULT_MSG[:30]}...")

    if not await health():
        print("[!] 后端未就绪（/api/health 不通），请先启动后端。")
        sys.exit(1)

    limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)
    async with httpx.AsyncClient(limits=limits) as client:
        admin_tok = await admin_token(client)
        print("[*] 初始化测试账号（注册+签同意+分 MOA+登录，串行以避免启动期竞态）...")
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

        print(f"[*] 开始并发发起 MOA 群辩（{len(tokens)} 人，每人约 7 次 LLM 调用）...")
        t0 = time.monotonic()
        tasks = [moa_one(client, idx, tok, DEFAULT_MSG) for idx, tok in tokens]
        results = await asyncio.gather(*tasks)
        wall = time.monotonic() - t0

        ok = [r for r in results if r["ok"]]
        fail = [r for r in results if not r["ok"]]
        lats = [r["latency_ms"] for r in results if r["latency_ms"]]
        print("\n==== MOA 结果汇总 ====")
        print(f"总账号: {len(results)}  成功(走到done): {len(ok)}  失败: {len(fail)}")
        print(f"墙钟耗时: {wall:.1f}s   平均单用户延迟: "
              f"{(sum(lats)/len(lats)/1000):.1f}s" if lats else "n/a")
        if lats:
            print(f"延迟 min/max: {min(lats)/1000:.1f}s / {max(lats)/1000:.1f}s")
        for r in results:
            flag = "OK " if r["ok"] else "FAIL"
            print(f"  [{flag}] user{r['user']} http={r['http_status']} "
                  f"chars={r['chars']} await_u={r['await_user']} await_c={r['await_confirm']} "
                  f"stages={r['stages']} latency={r['latency_ms']/1000:.1f}s"
                  + (f"  note={r['note']}" if r['note'] else "")
                  + (f"  err={r['error_event']}" if r['error_event'] else ""))
        from collections import Counter
        http_fail = Counter(r["http_status"] for r in fail if r["http_status"])
        if http_fail:
            print(f"失败 HTTP 状态分布: {dict(http_fail)}")

    print("\n[*] 清理测试账号...")
    print(f"[*] 清理结果: {await cleanup()}")


if __name__ == "__main__":
    asyncio.run(main())
