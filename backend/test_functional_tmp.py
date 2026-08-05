"""Temporary functional test for module 5/6 enhancements."""
import asyncio
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select, delete
from app.database import async_session_factory
from app.deps import get_current_admin, get_db
from app.models.user import User, ExperimentGroup, UserStatus
from app.models.task_submission import TaskSubmission
from app.models.reminder import Reminder
from app.models.questionnaire import QuestionnaireItem, QuestionnaireResponse, QuestionType
from app.models.admin_score import AdminScore
from app.main import app
import httpx

TEST_EMAIL = f"test_func_{uuid.uuid4().hex[:8]}@example.com"
CREATED_IDS = {}


async def get_db_override():
    async with async_session_factory() as s:
        yield s


async def admin_override():
    return {"sub": "admin", "role": "admin"}


app.dependency_overrides[get_current_admin] = admin_override
app.dependency_overrides[get_db] = get_db_override


async def seed():
    async with async_session_factory() as s:
        u = User(email=TEST_EMAIL, group=ExperimentGroup.H, status=UserStatus.REGISTERED, password_hash="x")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        CREATED_IDS["user"] = str(u.id)
        sub = TaskSubmission(user_id=u.id, task1_search=True, task2_document=True,
                             task3_reminder=True, task4_email=True,
                             email_status="sent", email_recipient="dest@example.com")
        s.add(sub)
        r = Reminder(user_id=u.id, reminder_datetime=datetime(2026, 8, 1, 9, 0), content="西湖门票预约")
        s.add(r)
        item = QuestionnaireItem(construct="trust", question_text="信任度", question_type=QuestionType.likert,
                                 scale_level=5, sort_order=1, is_active=True)
        s.add(item)
        await s.commit()
        await s.refresh(item)
        CREATED_IDS["item"] = str(item.id)
        resp = QuestionnaireResponse(user_id=u.id, item_id=item.id, response_value="4")
        s.add(resp)
        # 操纵检验（choice 题，非数值）— 验证聚合后该列不为空（尾空 bug 修复）
        mc_item = QuestionnaireItem(construct="manipulation_check",
                                    question_text="是否使用AI助理", question_type=QuestionType.choice,
                                    scale_level=0, sort_order=99, is_active=True)
        s.add(mc_item)
        await s.commit()
        await s.refresh(mc_item)
        CREATED_IDS["mc_item"] = str(mc_item.id)
        mc_resp = QuestionnaireResponse(user_id=u.id, item_id=mc_item.id, response_value="是")
        s.add(mc_resp)
        await s.commit()


async def main():
    await seed()
    uid = CREATED_IDS["user"]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1) set_score with quality_score + reminder_correct
        payload = {f: 8 for f in ["scenic_score", "historic_score", "rarity_score", "scale_score",
                                    "integrity_score", "fame_score", "season_score"]}
        payload["eco_score"] = 0
        payload["quality_score"] = 7
        payload["reminder_correct"] = True
        payload["notes"] = "测试"
        r = await client.post(f"/api/admin/scores/{uid}", json=payload)
        print("set_score status:", r.status_code, r.json())

        # 2) participant detail -> reminders + quality + reminder_correct
        r = await client.get(f"/api/admin/participants/{uid}")
        d = r.json()
        print("detail reminders:", len(d.get("reminders", [])), "first:", d["reminders"][0] if d.get("reminders") else None)
        print("detail scores[0]:", d["scores"][0] if d.get("scores") else None)
        print("detail submission email:", d.get("submission", {}).get("email_recipient"),
              d.get("submission", {}).get("email_status"))

        # 3) export/all?group=H -> check new columns present
        r = await client.get("/api/admin/export/all", params={"group": "H"})
        text = r.text
        print("export/all status:", r.status_code)
        header = text.splitlines()[0]
        print("has Questionnaire_Overall:", "Questionnaire_Overall" in header)
        print("has Quality_Score:", "Quality_Score" in header)
        print("has Reminder_Correct:", "Reminder_Correct" in header)
        # find our row
        row = [l for l in text.splitlines()[1:] if TEST_EMAIL in l]
        if row:
            fields = row[0].split(",")
            print("our row tail (quality/reminder/q):", fields[-7:])
            # 操纵检验 是最后一列，必须非空（修复前的尾空 bug）
            manip_val = fields[-1]
            print("manipulation_check (last col) =", repr(manip_val))
            assert manip_val.strip() != "", "操纵检验列不应为空（尾空 bug 未修复）"
            print("ASSERT manipulation_check non-empty: PASS")
            # 信任列应等于 4.0（单个 likert 响应）
            trust_idx = header.split(",").index("信任")
            print("trust col =", repr(fields[trust_idx]))
            assert fields[trust_idx].strip() == "4.0", "信任均分应为 4.0"
            print("ASSERT trust == 4.0: PASS")

        # 直接调用聚合函数调试
        from app.routers.admin import _compute_questionnaire_scores
        async with async_session_factory() as s2:
            qs = await _compute_questionnaire_scores(s2)
            print("DEBUG q_scores for user:", qs.get(uid))
            # 直接查原始响应
            from sqlalchemy import select as _select
            raw = (await s2.execute(_select(QuestionnaireResponse.user_id, QuestionnaireItem.construct, QuestionnaireResponse.response_value)
                                    .join(QuestionnaireItem, QuestionnaireResponse.item_id == QuestionnaireItem.id)
                                    .where(QuestionnaireResponse.user_id == uid))).all()
            print("DEBUG raw responses:", raw)

    # cleanup
    async with async_session_factory() as s:
        await s.execute(delete(AdminScore).where(AdminScore.user_id == uid))
        await s.execute(delete(Reminder).where(Reminder.user_id == uid))
        await s.execute(delete(QuestionnaireResponse).where(QuestionnaireResponse.user_id == uid))
        if CREATED_IDS.get("item"):
            await s.execute(delete(QuestionnaireItem).where(QuestionnaireItem.id == CREATED_IDS["item"]))
        if CREATED_IDS.get("mc_item"):
            await s.execute(delete(QuestionnaireItem).where(QuestionnaireItem.id == CREATED_IDS["mc_item"]))
        await s.execute(delete(TaskSubmission).where(TaskSubmission.user_id == uid))
        await s.execute(delete(User).where(User.id == uid))
        await s.commit()
    print("CLEANUP done")


asyncio.run(main())
