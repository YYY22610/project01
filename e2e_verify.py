"""
端到端验证脚本：覆盖本次修复的 P0/P1 项
- P0 #1: consent 后 JWT 含 group（AI 面板对首次会话用户可见）
- P0 #2: 邮件真实失败不再静默记为成功（离线 mock 验证守卫可达）
- P1 问卷: 构念对齐需求 (trust/autonomy/satisfaction/task_load/future_use/manipulation_check)，含 choice 题
- P1 演示: demo_watch_seconds 落库
全链路: 注册→同意→演示→任务四子任务→提交→问卷→管理后台
"""
import json
import time
import os
import urllib.request
import urllib.error
import base64
import asyncio
import asyncpg
import sys

# 确保 backend 包可导入（脚本位于项目根目录，app 包在 backend/ 下）
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_HERE, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

BASE = "http://127.0.0.1:8000"
DB_DSN = "postgresql://postgres:postgres@localhost:5432/travel_experiment"

results = []


def rec(name, ok, detail=""):
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def jwt_payload(token):
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part))


def req(method, path, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"detail": raw}


def main():
    # ---------- 1. 注册 ----------
    stamp = int(time.time() * 1000)
    email = f"e2e_{stamp}@test.com"
    pw = "Test1234!"
    st, reg = req("POST", "/api/auth/register", body={"email": email, "password": pw})
    rec("注册返回 token", st == 200 and "access_token" in reg, f"status={st}")
    reg_token = reg.get("access_token")
    pld = jwt_payload(reg_token)
    rec("注册 token group 为 None（分组在 consent 后分配）", pld.get("group") is None, f"group={pld.get('group')}")

    # ---------- 2. consent 后 JWT 含 group（P0 #1） ----------
    st, cons = req("POST", "/api/auth/consent", token=reg_token)
    rec("consent 返回新 token", st == 200 and "access_token" in cons, f"status={st}")
    new_token = cons.get("access_token")
    pld2 = jwt_payload(new_token)
    grp = pld2.get("group")
    rec("P0#1: consent 后 token 含 group（非 None）", grp in ("H", "SOA", "MOA"), f"group={grp}")

    # ---------- 3. demographics ----------
    st, _ = req("POST", "/api/auth/demographics", token=new_token,
                body={"age": 22, "gender": "F", "education": "本科", "tech_frequency": "每天", "ai_experience": "偶尔"})
    rec("人口统计提交", st == 200, f"status={st}")

    # ---------- 4. demo-complete 含时长 ----------
    st, demo = req("POST", "/api/task/demo-complete", token=new_token, body={"watch_seconds": 42})
    rec("演示完成(含 watch_seconds) 200", st == 200, f"status={st} msg={demo.get('message')}")

    # ---------- 5. task start ----------
    st, start = req("POST", "/api/task/start", token=new_token)
    rec("任务开始 200", st == 200 and "task_id" in start, f"status={st}")

    # ---------- 6. 任务四子任务 ----------
    st, _ = req("POST", "/api/search", token=new_token, body={"query": "杭州 西湖 景点", "page": 1})
    rec("子任务1 景点搜索", st == 200, f"status={st}")
    st, doc = req("POST", "/api/document/generate", token=new_token,
                  body={"title": "杭州三日游行程规划", "content": "第一天：西湖。第二天：灵隐寺。第三天：西溪。"})
    rec("子任务2 生成 Word 文档", st == 200 and "file_path" in doc, f"status={st}")
    fp = doc.get("file_path")
    st, _ = req("POST", "/api/reminder", token=new_token,
                body={"reminder_datetime": "2026-08-01T09:00:00", "content": "出发提醒"})
    rec("子任务3 设置提醒", st == 200, f"status={st}")
    st, em = req("POST", "/api/email/send", token=new_token,
                 body={"to_email": "friend@example.com", "subject": "杭州三日游", "content": "行程见附件",
                       "attachment_path": fp})
    rec("子任务4 发送邮件(mock_sent 视为完成)", st == 200 and em.get("status") in ("mock_sent", "sent"),
        f"status={st} email_status={em.get('status')}")

    # ---------- 7. task submit ----------
    st, sub = req("POST", "/api/task/submit", token=new_token,
                  body={"task1_search": True, "task2_document": True, "task3_reminder": True, "task4_email": True,
                        "docx_file_path": fp, "email_status": em.get("status"), "email_recipient": "friend@example.com"})
    rec("任务提交 all_completed=true", st == 200 and sub.get("all_completed") is True, f"status={st}")

    # ---------- 8. 问卷（P1 构念对齐） ----------
    st, items = req("GET", "/api/questionnaire/items", token=new_token)
    rec("获取问卷题项 200", st == 200 and len(items) >= 14, f"status={st} count={len(items)}")
    constructs = set(i["construct"] for i in items)
    expected = {"trust", "autonomy", "satisfaction", "task_load", "future_use", "manipulation_check"}
    rec("P1问卷: 6 个构念齐全", expected.issubset(constructs), f"got={sorted(constructs)}")
    choice_items = [i for i in items if i.get("question_type") == "choice" and i.get("options")]
    rec("P1问卷: 含选择题(操纵检验)且带选项", len(choice_items) >= 1, f"choice_count={len(choice_items)}")
    # 提交问卷
    responses = [{"item_id": i["id"], "response_value": ("3" if i["question_type"] == "likert" else i["options"][0])} for i in items]
    st, qsub = req("POST", "/api/questionnaire/submit", token=new_token, body={"responses": responses})
    rec("问卷提交 200", st == 200 and qsub.get("submitted") is True, f"status={st}")

    # ---------- 9. 管理后台 ----------
    st, adm = req("POST", "/api/auth/admin/login", body={"username": "admin", "password": "admin123"})
    rec("管理员登录 200", st == 200 and "access_token" in adm, f"status={st}")
    atoken = adm.get("access_token")
    st, dash = req("GET", "/api/admin/dashboard", token=atoken)
    rec("管理后台 dashboard 200", st == 200, f"status={st}")
    st, parts = req("GET", "/api/admin/participants", token=atoken)
    rec("管理后台 participants 200", st == 200, f"status={st}")

    # ---------- 10. 数据库层校验 ----------
    async def db_checks():
        conn = await asyncpg.connect(DB_DSN)
        # demo_watch_seconds 落库
        uid = pld2.get("sub")
        row = await conn.fetchrow("SELECT demo_watch_seconds FROM users WHERE id=$1", uid)
        wat = row["demo_watch_seconds"] if row else None
        rec("P1演示: demo_watch_seconds=42 已落库", wat == 42, f"demo_watch_seconds={wat}")
        # 问卷构念（DB）
        db_const = await conn.fetch("SELECT DISTINCT construct FROM questionnaire_items")
        db_set = set(r["construct"] for r in db_const)
        rec("P1问卷: DB 构念与需求一致", expected.issubset(db_set), f"db={sorted(db_set)}")
        await conn.close()

    asyncio.run(db_checks())

    # ---------- P0 #2 离线校验：邮件失败守卫可达 ----------
    try:
        import unittest.mock as mock
        from app.services import email_service
        with mock.patch.object(email_service.settings, "RESEND_API_KEY", "fake-key"), \
             mock.patch("httpx.Client.post", side_effect=Exception("network down")):
            res = email_service.send_email("x@y.com", "s", "c")
        rec("P0#2: 配置 key 但发送失败 → status=failed", res.get("status") == "failed", f"res={res}")
    except Exception as e:
        rec("P0#2: 离线守卫校验异常", False, str(e))

    # ---------- 汇总 ----------
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("\n================ 汇总 ================")
    print(f"通过 {passed}/{total}")
    for name, ok, detail in results:
        if not ok:
            print(f"  ✗ {name} — {detail}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
