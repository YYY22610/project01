"""MOA 群辩后端直连 SSE 探针（无浏览器）：验证服务端的 await_user / await_confirm / done
跨请求暂停-恢复是否正确。mock 模式下不依赖网络。"""
import json
import sys
import httpx

BASE = "http://127.0.0.1:8000"
EMAIL = "moaval@test.com"
PW = "Test1234!"


def log(*a):
    print("[PROBE]", *a, flush=True)


def main():
    with httpx.Client(timeout=httpx.Timeout(connect=10, read=200, write=30, pool=10)) as c:
        # 1) 登录取 token
        r = c.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PW})
        if r.status_code != 200:
            log("login failed", r.status_code, r.text[:200])
            sys.exit(1)
        token = r.json()["access_token"]
        log("login ok, token len =", len(token))

        # 2) 启动群辩 SSE
        headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
        body = {
            "message": "一个人，3天，预算1000元，喜欢人文和美食，不要太赶",
            "dest": "杭州", "days": 3, "budget": 1000, "travelers": "1 人",
        }
        seen = []
        resumed_user = False
        resumed_confirm = False
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
                    log("event:", ev)
                    if ev == "await_user" and not resumed_user:
                        # 立即回填回答，恢复群聊
                        rr = c.post(f"{BASE}/api/moa/group-resume",
                                    json={"message": "我喜欢安静一点的景点，预算控制在800元以内"},
                                    headers=headers)
                        log("  -> resume(user) ->", rr.status_code)
                        resumed_user = True
                    elif ev == "await_confirm" and not resumed_confirm:
                        rr = c.post(f"{BASE}/api/moa/group-resume",
                                    json={"message": "确认"},
                                    headers=headers)
                        log("  -> resume(confirm) ->", rr.status_code)
                        resumed_confirm = True
                    elif ev == "done":
                        log("DONE reached. plan chars =", len((data or {}).get("plan", {}).get("markdown", "")))
                        break
                    elif ev == "error":
                        log("ERROR event:", data)
                        break

        log("SEEN EVENTS:", seen)
        log("RESULT:", {
            "saw_await_user": "await_user" in seen,
            "resumed_user": resumed_user,
            "saw_await_confirm": "await_confirm" in seen,
            "resumed_confirm": resumed_confirm,
            "saw_done": "done" in seen,
        })


if __name__ == "__main__":
    main()
