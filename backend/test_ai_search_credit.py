# -*- coding: utf-8 -*-
"""验证「有 AI 助手的组：只要开始对话，即算完成搜索景点」这条规则。

覆盖四个场景：
  A. MOA 组仅与单个 Agent 对话（写 chat_messages）→ 搜索景点应达标
  B. MOA 组仅发起智囊团群辩（只写 behavior_logs）→ 搜索景点应达标
  C. H 组没有任何对话，也未手动检索 → 搜索景点应**不**达标
  D. MOA 组无任何对话，也未手动检索 → 提交后不应被误判为已搜索

同时验证：前端谎报 task1_search=False 时，只要服务端有对话记录，
提交仍被计为达标（说明判定不依赖前端上报）。

用法：backend/venv/Scripts/python.exe test_ai_search_credit.py
测试账号以 e2e_ai_search_ 为前缀，执行完自动删除。
"""
import asyncio
import os
import sys
import uuid

os.environ.setdefault("LLM_API_KEY", "")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, delete, text

from app.database import async_session_factory, engine
from app.main import app
from app.models.user import User, UserStatus, ExperimentGroup
from app.models.chat_message import ChatMessage
from app.models.behavior_log import BehaviorLog, ActionType
from app.models.task_submission import TaskSubmission
from app.models.questionnaire import QuestionnaireResponse
from app.models.moa_group_session import MoaGroupSession
from app.models.reminder import Reminder
from app.models.admin_score import AdminScore
from app.services.auth_service import create_user_token

PREFIX = "e2e_ai_search_"
RESULTS = []


def check(name: str, ok: bool, detail: str = ""):
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail else ""))


async def cleanup(db):
    """按前缀清理测试账号及其关联数据。"""
    rows = await db.execute(select(User.id).where(User.email.like(f"{PREFIX}%")))
    uids = [r[0] for r in rows.all()]
    if not uids:
        return
    await db.execute(delete(ChatMessage).where(ChatMessage.user_id.in_(uids)))
    await db.execute(delete(BehaviorLog).where(BehaviorLog.user_id.in_(uids)))
    await db.execute(delete(TaskSubmission).where(TaskSubmission.user_id.in_(uids)))
    await db.execute(delete(QuestionnaireResponse).where(QuestionnaireResponse.user_id.in_(uids)))
    await db.execute(delete(MoaGroupSession).where(MoaGroupSession.user_id.in_(uids)))
    await db.execute(delete(Reminder).where(Reminder.user_id.in_(uids)))
    await db.execute(delete(AdminScore).where(AdminScore.user_id.in_(uids)))
    await db.execute(delete(User).where(User.id.in_(uids)))
    await db.commit()


async def make_user(db, group: ExperimentGroup, tag: str) -> User:
    u = User(
        email=f"{PREFIX}{tag}_{uuid.uuid4().hex[:6]}@test.local",
        group=group,
        status=UserStatus.TASK_IN_PROGRESS,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def main():
    async with async_session_factory() as db:
        await cleanup(db)

        # ---------- A. MOA：单聊对话 → 达标 ----------
        ua = await make_user(db, ExperimentGroup.MOA, "chat")
        db.add(ChatMessage(user_id=ua.id, agent_id="moa_a", role="user", content="杭州西湖怎么玩"))
        await db.commit()
        ta = create_user_token(str(ua.id), "MOA", UserStatus.TASK_IN_PROGRESS.value)

        # ---------- B. MOA：仅群辩（无 chat_messages）→ 达标 ----------
        ub = await make_user(db, ExperimentGroup.MOA, "group")
        db.add(BehaviorLog(
            user_id=ub.id, group="MOA", action_type=ActionType.AGENT_MESSAGE,
            agent_id="moa_group", input_content="请帮我规划三日游",
        ))
        await db.commit()
        tb = create_user_token(str(ub.id), "MOA", UserStatus.TASK_IN_PROGRESS.value)

        # ---------- C. H：无对话无检索 → 不达标 ----------
        uc = await make_user(db, ExperimentGroup.H, "human")
        tc = create_user_token(str(uc.id), "H", UserStatus.TASK_IN_PROGRESS.value)

        # ---------- D. MOA：完全没对话 → 不达标 ----------
        ud = await make_user(db, ExperimentGroup.MOA, "silent")
        td = create_user_token(str(ud.id), "MOA", UserStatus.TASK_IN_PROGRESS.value)

        ids = [ua.id, ub.id, uc.id, ud.id]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # /task/status 的 ai_chat_started
        for uid, tok, name, expect in [
            (ua.id, ta, "A 单聊对话", True),
            (ub.id, tb, "B 仅群辩", True),
            (uc.id, tc, "C H组无对话", False),
            (ud.id, td, "D MOA无对话", False),
        ]:
            r = await c.get("/api/task/status", headers=auth(tok))
            ok = r.status_code == 200
            started = r.json().get("ai_chat_started") if ok else None
            check(f"{name}：/task/status ai_chat_started", ok and started is expect,
                  f"HTTP {r.status_code}, ai_chat_started={started}, 期望={expect}")

        # 提交时前端谎报 False，服务端仍应据对话记录判定达标
        for uid, tok, name, expect in [
            (ua.id, ta, "A 单聊对话", True),
            (ub.id, tb, "B 仅群辩", True),
            (uc.id, tc, "C H组无对话", False),
            (ud.id, td, "D MOA无对话", False),
        ]:
            r = await c.post("/api/task/submit", headers=auth(tok), json={
                "task1_search": False,   # 故意谎报为未搜索
                "task2_document": False,
                "task3_reminder": False,
                "task4_email": False,
            })
            # 只完成了搜索一项，all_completed 恒为 False；
            # 故直接查库核对 task1_search（见下方「数据库 task1_search」一组断言）
            check(f"{name}：提交接口可正常返回", r.status_code == 200,
                  f"HTTP {r.status_code}")

    # 落库结果核对
    async with async_session_factory() as db:
        for uid, name, expect in [
            (ua.id, "A 单聊对话", True),
            (ub.id, "B 仅群辩", True),
            (uc.id, "C H组无对话", False),
            (ud.id, "D MOA无对话", False),
        ]:
            row = await db.execute(select(TaskSubmission).where(TaskSubmission.user_id == uid))
            sub = row.scalar_one_or_none()
            got = sub.task1_search if sub else None
            check(f"{name}：数据库 task1_search", got is expect, f"落库值={got}, 期望={expect}")

        await cleanup(db)

    await engine.dispose()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n结果：{passed}/{total} 通过")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
