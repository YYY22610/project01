"""SSE 全流程 + server_stage 落库验证（同步连真实端口，mock 后端需已启动）。
跑通 await_user→resume→await_confirm→resume→done，然后查库确认 server_stage 自动写入。"""
import json
import sys
import httpx
from sqlalchemy import select

from app.database import async_session_factory
from app.models.moa_group_session import MoaGroupSession

BASE = "http://127.0.0.1:8000"
EMAIL = "moaval@test.com"
PW = "Test1234!"


def main():
    with httpx.Client(timeout=httpx.Timeout(connect=10, read=180, write=30, pool=10)) as c:
        r = c.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PW})
        assert r.status_code == 200, f"login failed: {r.text[:200]}"
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}

        # 清掉残留
        c.delete(f"{BASE}/api/moa/group-state", headers=headers)

        body = {"message": "一个人，3天，预算1000元，喜欢人文和美食", "dest": "杭州", "days": 3, "budget": 1000, "travelers": "1 人"}
        seen = []
        resumed_user = False
        resumed_confirm = False
        with c.stream("POST", f"{BASE}/api/moa/group-discuss", json=body, headers=headers) as resp:
            print("[SSE] status =", resp.status_code)
            buf = ""
            for chunk in resp.iter_text():
                buf += chunk
                while "\n\n" in buf:
                    raw, buf = buf.split("\n\n", 1)
                    ev = None
                    data = None
                    for line in raw.split("\n"):
                        if line.startswith("event: "):
                            ev = line[7:].strip()
                        elif line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                            except Exception:
                                data = line[6:]
                    if not ev:
                        continue
                    seen.append(ev)
                    if ev == "await_user" and not resumed_user:
                        rr = c.post(f"{BASE}/api/moa/group-resume", json={"message": "吃好喝好，兼顾文化"}, headers=headers)
                        print("  resume(user) ->", rr.status_code)
                        resumed_user = True
                    elif ev == "await_confirm" and not resumed_confirm:
                        rr = c.post(f"{BASE}/api/moa/group-resume", json={"message": "确认"}, headers=headers)
                        print("  resume(confirm) ->", rr.status_code)
                        resumed_confirm = True
                    elif ev == "done":
                        print("  DONE, plan chars =", len((data or {}).get("plan", {}).get("markdown", "")))
                        break
                    elif ev == "error":
                        print("  ERROR:", data)
                        break

        print("[SSE] 事件序列:", " -> ".join(seen))
        assert "await_user" in seen and "await_confirm" in seen and "done" in seen, "❌ SSE 流程不完整"

        # 查库验证 server_stage
        import asyncio

        async def check():
            async with async_session_factory() as db:
                row = (await db.execute(select(MoaGroupSession).where(MoaGroupSession.user_id.isnot(None)))).scalars().all()
                rows = [(str(r2.user_id), r2.server_stage) for r2 in row if r2.server_stage]
                print("[DB] server_stage 记录数:", len(rows))
                for uid, ss in rows:
                    print("  user:", uid[:8], "| stage:", ss)
                return any(ss and ss.get("stage") == "done" for _, ss in rows)

        ok = asyncio.run(check())
        assert ok, "❌ server_stage 未写入 done"
        print("\n🎉 SSE 全流程 + server_stage 落库通过")


if __name__ == "__main__":
    main()
    sys.exit(0)
