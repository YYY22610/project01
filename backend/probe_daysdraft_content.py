"""抓取 MOA 讨论过程中 temp_plan 与最终 plan 的真实内容。

用途：核对前端 PlanDisplay / DayCard 的渲染假设。
与 probe_tempplan_content.py 的区别：这次连 days_draft 与最终 plan（quotes）一起打印，
因为 DayCard 与「团队讨论摘要」此前从未用真实数据验证过。

注意：账号必须预先具备 group=MOA，否则 403（新注册 JWT 里 group 为 null）。
"""
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000"
EMAIL = "probe_md2@test.com"
PW = "Test1234!"


def log(*a):
    print("[PROBE]", *a, flush=True)


def dump_days_draft(raw):
    """days_draft 是 JSON 字符串（主持人草案），前端 DayCard 直接消费。"""
    try:
        days = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        log("days_draft 解析失败:", e)
        log("原始值:", repr(str(raw)[:400]))
        return
    log(f"days_draft: {len(days)} 天")
    for i, d in enumerate(days[:2], 1):
        log(f"  Day{i} keys={list(d.keys())}")
        log(f"    title={d.get('title')!r} tag={d.get('tag')!r}")
        for it in (d.get("items") or [])[:3]:
            log("    item:", repr(it)[:220])
    # 关键：统计 Markdown 标记是否出现在 days_draft 里
    blob = json.dumps(days, ensure_ascii=False)
    for mark, label in (("**", "加粗"), ("##", "标题"), ("---", "分隔线"), ("`", "代码符")):
        log(f"  含 {label} {mark!r}: {blob.count(mark)}")


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
        final_plan = {}
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
                    raw_ev, buf = buf.split("\n\n", 1)
                    ev = data = None
                    for line in raw_ev.split("\n"):
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
                    elif ev == "await_user" and not resumed_user:
                        c.post(f"{BASE}/api/moa/group-resume",
                               json={"message": "我喜欢安静一点的景点，预算控制在800元以内"},
                               headers=headers)
                        resumed_user = True
                    elif ev == "await_confirm":
                        c.post(f"{BASE}/api/moa/group-resume", json={"message": "确认"}, headers=headers)
                    elif ev == "done":
                        final_plan = (data or {}).get("plan", {}) or {}
                        log("done 到达")
                        buf = ""
                        break
                    elif ev == "error":
                        log("error data:", data)
                        buf = ""
                        break

        log("=== days_draft（DayCard 的数据源）===")
        if latest.get("days_draft"):
            dump_days_draft(latest["days_draft"])
        else:
            log("未捕获到 days_draft")

        log("=== 最终 plan ===")
        log("顶层键:", list(final_plan.keys()) if final_plan else "(空)")
        data = final_plan.get("data") or {}
        if data:
            log("data 键:", list(data.keys()))
            days = data.get("days") or []
            log(f"days: {len(days)} 天")
            for i, d in enumerate(days[:2], 1):
                log(f"  Day{i} title={d.get('title')!r}")
                for it in (d.get("items") or [])[:2]:
                    log("    item:", repr(it)[:200])
            spots = data.get("spots") or []
            log(f"spots: {len(spots)} 项，样例={repr(spots[0])[:200] if spots else '(空)'}")
        quotes = final_plan.get("quotes") or []
        log(f"quotes: {len(quotes)} 条")
        for q in quotes[:3]:
            log("  -", repr(q)[:240])


if __name__ == "__main__":
    main()
