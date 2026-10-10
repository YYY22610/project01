"""抓取 MOA 讨论过程中 temp_plan 事件的真实内容，用于核对前端渲染假设。

只读探针：注册/登录测试账号 → 发起群辩 → 收集 temp_plan 事件 → 打印各字段形态。
不改业务代码，不写数据库（仅走正常的注册接口）。
"""
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000"
EMAIL = "probe_md@test.com"
PW = "Test1234!"


def log(*a):
    print("[PROBE]", *a, flush=True)


def main():
    with httpx.Client(timeout=httpx.Timeout(connect=10, read=300, write=30, pool=10)) as c:
        r = c.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PW})
        if r.status_code != 200:
            log("login failed", r.status_code, r.text[:200])
            sys.exit(1)
        token = r.json()["access_token"]
        log("login ok")

        headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
        body = {
            "message": "一个人，3天，预算1000元，喜欢人文和美食，不要太赶",
            "dest": "杭州", "days": 3, "budget": 1000, "travelers": "1 人",
        }

        latest = {}
        resumed_user = False
        with c.stream("POST", f"{BASE}/api/moa/group-discuss", json=body, headers=headers) as resp:
            log("SSE status =", resp.status_code)
            if resp.status_code != 200:
                log("SSE failed", resp.read().decode()[:300])
                sys.exit(1)
            buf = ""
            for chunk in resp.iter_text():
                buf += chunk
                while "\n\n" in buf:
                    raw, buf = buf.split("\n\n", 1)
                    ev, data = None, None
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
                    if ev == "temp_plan":
                        latest = (data or {}).get("plan", {}) or {}
                        log("temp_plan 快照 keys =", list(latest.keys()))
                    elif ev == "await_user" and not resumed_user:
                        c.post(f"{BASE}/api/moa/group-resume",
                               json={"message": "我喜欢安静一点的景点，预算控制在800元以内"},
                               headers=headers)
                        resumed_user = True
                    elif ev == "await_confirm":
                        c.post(f"{BASE}/api/moa/group-resume", json={"message": "确认"}, headers=headers)
                    elif ev in ("done", "error"):
                        log(ev, "到达，停止收集")
                        if ev == "error":
                            log("error data:", data)
                        buf = ""
                        break

        log("=== 抓到的 temp_plan 最终快照 ===")
        for k, v in latest.items():
            if k == "days_draft":
                log(f"[{k}] (JSON 草案字符串, len={len(str(v))})")
                continue
            if isinstance(v, list):
                log(f"[{k}] list, {len(v)} 项")
                for it in v[:4]:
                    log("   -", repr(str(it)[:200]))
            else:
                log(f"[{k}] {type(v).__name__}: {repr(str(v)[:200])}")


if __name__ == "__main__":
    main()
