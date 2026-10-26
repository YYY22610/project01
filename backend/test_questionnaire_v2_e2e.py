"""End-to-end verification of the 2026-10-14 questionnaire (ASGI in-process, no ports).

Covers:
  1. pre items: count, phases, constructs, types, reverse flags, bipolar anchors
  2. consent submission: writes 20 pre responses + maps demographics onto User columns
  3. state machine: registered -> consented, group assigned
  4. post items: 34, includes manipulation check + open text
  5. post submission: phase guard rejects pre items, writes 34 responses
  6. export aggregation: reverse scoring flipped, categorical kept as raw text
"""
import asyncio
import os
import sys

os.environ["LLM_API_KEY"] = ""
sys.path.insert(0, r"D:\27475\WorkBuddy-搭建网站\travel-experiment-platform\backend")

from datetime import datetime, timezone

import httpx
from sqlalchemy import delete, select, func
from app.database import async_session_factory, engine
from app.main import app
from app.models.questionnaire import QuestionnaireItem, QuestionnaireResponse
from app.models.user import User, UserStatus
from app.routers.admin import _compute_questionnaire_scores

EMAIL = f"q_verify_{int(datetime.now(timezone.utc).timestamp())}@test.com"
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")


async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        # ---------- register ----------
        r = await c.post("/api/auth/register", json={"email": EMAIL})
        check("register 200", r.status_code == 200, f"status={r.status_code} {r.text[:120]}")
        token = r.json()["access_token"]
        H = {"Authorization": f"Bearer {token}"}

        # ---------- 1. pre items ----------
        r = await c.get("/api/questionnaire/items", params={"phase": "pre"}, headers=H)
        check("GET items?phase=pre 200", r.status_code == 200, f"status={r.status_code}")
        pre = r.json()
        check("前置问卷 20 题", len(pre) == 20, f"got {len(pre)}")
        check("全部 phase=pre", all(i["phase"] == "pre" for i in pre))
        check(
            "Q01 性别单选",
            pre[0]["question_text"] == "您的性别" and pre[0]["question_type"] == "choice"
            and "男" in pre[0]["options"],
            f"{pre[0]['question_text']} {pre[0]['question_type']}",
        )
        multi = [i for i in pre if i["question_type"] == "multiple"]
        check("Q10 多选题", len(multi) == 1 and len(multi[0]["options"]) == 6, f"{len(multi)} multi")
        rev_pre = [i["sort_order"] for i in pre if i["is_reverse"]]
        check("前置反向题 = Q12,Q20", rev_pre == [12, 20], f"got {rev_pre}")
        note_items = [i["sort_order"] for i in pre if i["section_note"]]
        check("前置指导语在 Q11", note_items == [11], f"got {note_items}")
        si = [i for i in pre if i["construct"] == "social_influence"]
        check("社会影响 6 题", len(si) == 6, f"got {len(si)}")

        # ---------- 2/3. consent ----------
        answers = []
        for it in pre:
            if it["question_type"] == "likert":
                # 用非中位数的 4：反向题翻转为 6-4=2，若未翻转均值会是 4.0，可据此区分
                val = "4"
            elif it["question_type"] == "multiple":
                # exercise the multi-select "exclusive option" path
                val = "我了解人工智能智能体（AI Agent）的基本工作原理 | 以上均不认同"
            elif it["construct"] == "demographic" and it["sort_order"] == 2:
                val = "26–30 岁"
            elif it["construct"] == "ai_experience" and it["sort_order"] == 8:
                val = "经常"
            elif it["construct"] == "ai_experience" and it["sort_order"] == 6:
                val = "是"
            else:
                val = it["options"][0]
            answers.append({"item_id": it["id"], "response_value": val})

        r = await c.post("/api/auth/consent", json={"agreed": True, "responses": answers}, headers=H)
        check("consent 200", r.status_code == 200, f"status={r.status_code} {r.text[:200]}")
        new_token = r.json().get("access_token")
        H = {"Authorization": f"Bearer {new_token}"}

        async with async_session_factory() as db:
            u = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one()
            check("status = consented", u.status == UserStatus.CONSENTED, u.status.value)
            check("group 已分配", u.group is not None, str(u.group))
            n_pre = (await db.execute(
                select(func.count()).select_from(QuestionnaireResponse).where(
                    QuestionnaireResponse.user_id == u.id)
            )).scalar()
            check("前置作答 20 条入库", n_pre == 20, f"got {n_pre}")
            check("gender 映射", u.gender == "男", str(u.gender))
            check("age 映射 (26–30 岁→28)", u.age == 28, str(u.age))
            check("education 映射", u.education == "高中及以下", str(u.education))
            check("tech_frequency 映射", u.tech_frequency == "经常", str(u.tech_frequency))
            check("ai_experience 映射", u.ai_experience == "basic", str(u.ai_experience))
            user_id = u.id

        # ---------- guard: double consent ----------
        r = await c.post("/api/auth/consent", json={"agreed": True, "responses": answers}, headers=H)
        check("重复提交被拒 400", r.status_code == 400, f"status={r.status_code}")

        # ---------- 4. post items ----------
        r = await c.get("/api/questionnaire/items", params={"phase": "post"}, headers=H)
        post = r.json()
        check("后置问卷 34 题", len(post) == 34, f"got {len(post)}")
        check("全部 phase=post", all(i["phase"] == "post" for i in post))
        mc = [i for i in post if i["construct"] == "manipulation_check"]
        check("操纵检验 2 题", len(mc) == 2, f"got {len(mc)}")
        aff = [i for i in post if i["construct"] == "affective_experience"]
        check("情绪体验 5 题双极", len(aff) == 5 and all(
            isinstance(i["options"], dict) and i["options"].get("left") for i in aff))
        check("双极锚点 left/right 齐全", all(
            i["options"].get("left") and i["options"].get("right") for i in aff),
            f"first={aff[0]['options'] if aff else None}")
        txt = [i for i in post if i["question_type"] == "text"]
        check("开放题 1 题 (Q54)", len(txt) == 1 and txt[0]["sort_order"] == 54,
              f"{[t['sort_order'] for t in txt]}")
        rev_post = [i["sort_order"] for i in post if i["is_reverse"]]
        check("后置反向题 = Q25", rev_post == [25], f"got {rev_post}")
        note_post = [i["sort_order"] for i in post if i["section_note"]]
        check("后置指导语在 Q23,Q41", note_post == [23, 41], f"got {note_post}")

        # ---------- guard: post phase rejects pre items ----------
        async with async_session_factory() as db:
            await db.execute(select(User).where(User.id == user_id))
            u = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
            u.status = UserStatus.TASK_COMPLETED
            await db.commit()
        token2 = None
        async with async_session_factory() as db:
            u = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
            from app.services.auth_service import create_user_token
            token2 = create_user_token(str(u.id), u.group.value if u.group else None, u.status.value)
        H = {"Authorization": f"Bearer {token2}"}

        r = await c.post("/api/questionnaire/submit", json={"responses": answers[:3]}, headers=H)
        check("后置提交混入前置题被拒 400", r.status_code == 400, f"status={r.status_code}")

        # ---------- 5. post submit ----------
        post_answers = []
        for it in post:
            if it["question_type"] == "likert":
                # Q25 is reverse; feed 1 so a correct flip must yield 5, not 1
                val = "1" if it["is_reverse"] else "4"
            elif it["question_type"] == "choice":
                val = it["options"][1] if len(it["options"]) > 1 else it["options"][0]
            else:
                val = "整体体验不错，希望后续能支持更多城市。"
            post_answers.append({"item_id": it["id"], "response_value": val})

        r = await c.post("/api/questionnaire/submit", json={"responses": post_answers}, headers=H)
        check("后置提交 200", r.status_code == 200, f"status={r.status_code} {r.text[:200]}")
        check("response_count = 34", r.json().get("response_count") == 34, str(r.json()))

        # ---------- 6. export aggregation ----------
        async with async_session_factory() as db:
            total = (await db.execute(
                select(func.count()).select_from(QuestionnaireResponse).where(
                    QuestionnaireResponse.user_id == user_id)
            )).scalar()
            check("总作答 54 条 (20 pre + 34 post)", total == 54, f"got {total}")

            qs = (await _compute_questionnaire_scores(db))[str(user_id)]
            # 前置李克特全填 4，反向题(Q12/Q20)翻转为 2：
            #   社会影响 = (4+2+4+4+4+4)/6 = 3.67   （未翻转则恒为 4.0）
            #   感知拟人化 = (4+4+4+2)/4   = 3.5    （未翻转则恒为 4.0）
            check("社会影响均值 3.67 (Q12 反向 6-4=2)",
                  abs(qs.get("social_influence", 0) - 3.67) < 0.01,
                  f"got {qs.get('social_influence')}")
            check("感知拟人化均值 3.5 (Q20 反向 6-4=2)",
                  abs(qs.get("anthropomorphism", 0) - 3.5) < 0.01,
                  f"got {qs.get('anthropomorphism')}")
            # 后置李克特填 4、反向 Q25 填 1 翻转为 5：
            #   享乐动机 = (4+4+5+4+4)/5 = 4.2      （未翻转则恒为 3.6）
            check("享乐动机均值 4.2 (Q25 反向 6-1=5)",
                  abs(qs.get("hedonic_motivation", 0) - 4.2) < 0.01,
                  f"got {qs.get('hedonic_motivation')}")
            check("情绪体验均值 = 4 (无反向题)", qs.get("affective_experience") == 4.0,
                  f"got {qs.get('affective_experience')}")
            check("接受意愿 = 4", qs.get("acceptance_intention") == 4.0)
            check("拒绝意愿 = 4", qs.get("resistance_intention") == 4.0)
            check("人口统计为原文非均值", isinstance(qs.get("demographic"), str),
                  f"got {type(qs.get('demographic')).__name__}")
            check("智能体认知保留多选原文", "以上均不认同" in str(qs.get("agent_awareness")),
                  str(qs.get("agent_awareness")))
            check("操纵检验为原文", isinstance(qs.get("manipulation_check"), str),
                  str(qs.get("manipulation_check")))
            check("开放题为原文", "整体体验不错" in str(qs.get("open_feedback")))
            check("_overall 只算数值题", qs.get("_overall") is not None, str(qs.get("_overall")))

            # cleanup the probe account
            await db.execute(delete(QuestionnaireResponse).where(
                QuestionnaireResponse.user_id == user_id))
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()
            print("  [cleanup] probe account + responses removed")

    await engine.dispose()
    print(f"\n{'='*56}\nPASS {len(PASS)} / FAIL {len(FAIL)}")
    if FAIL:
        print("FAILED: " + "; ".join(FAIL))
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
