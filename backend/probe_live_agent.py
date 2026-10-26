"""对运行中的后端做一次真实 AI 对话探测（走 HTTP + SSE，不是内进程）。

目的：确认 base_agent 的多轮工具循环在真实服务上生效——回复不能是
「操作完成。」这类兜底文案，且模型确实能连续调用工具。

用法：后端需已在 127.0.0.1:8000 运行。脚本自建临时 SOA 账号，跑完即删。
"""
import asyncio
import json
import sys
import uuid

import httpx
from sqlalchemy import text

sys.path.insert(0, ".")
from app.database import engine, async_session_factory  # noqa: E402
from app.models.user import UserStatus  # noqa: E402
from app.services.auth_service import create_user_token  # noqa: E402

BASE = "http://127.0.0.1:8000"
PROMPT = "先帮我搜一下杭州有哪些必去的景点，再根据搜索结果给我排 3 天行程，预算 2000 内"


async def make_user() -> tuple[str, str]:
    """建一个临时 SOA 账号，返回 (user_id, token)。"""
    uid = str(uuid.uuid4())
    async with async_session_factory() as db:
        await db.execute(
            text(
                # status / group 都是 PG 原生枚举，库里存枚举名（大写），不能传 .value
                'insert into users (id, email, status, "group") '
                "values (:i, :e, 'TASK_IN_PROGRESS', 'SOA')"
            ),
            {"i": uid, "e": f"probe_live_{uuid.uuid4().hex[:6]}@test.local"},
        )
        await db.commit()
    token = create_user_token(uid, "SOA", UserStatus.TASK_IN_PROGRESS.value)
    return uid, token


async def cleanup(uid: str) -> None:
    async with async_session_factory() as db:
        for sql in (
            "delete from chat_messages where user_id = :u",
            "delete from behavior_logs where user_id = :u",
            "delete from task_submissions where user_id = :u",
            "delete from users where id = :u",
        ):
            await db.execute(text(sql), {"u": uid})
        await db.commit()


def run_probe(token: str) -> dict:
    """同步流式读 SSE：ASGITransport 会缓冲整个响应，必须走真实端口。"""
    content_parts: list[str] = []
    tool_names: list[str] = []
    events: list[str] = []
    errors: list[str] = []

    with httpx.Client(timeout=180.0) as client:
        with client.stream(
            "POST",
            f"{BASE}/api/agent/chat",
            json={"agent_id": "soa", "message": PROMPT},
            headers={"Authorization": f"Bearer {token}"},
        ) as resp:
            if resp.status_code != 200:
                resp.read()
                return {"http": resp.status_code, "body": resp.text[:300]}
            cur_event = None
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    cur_event = line[6:].strip()
                    events.append(cur_event)
                elif line.startswith("data:"):
                    raw = line[5:].strip()
                    if cur_event == "content":
                        try:
                            content_parts.append(json.loads(raw))
                        except json.JSONDecodeError:
                            content_parts.append(raw)
                    elif cur_event == "tool_call":
                        try:
                            tool_names.append(json.loads(raw).get("tool", "?"))
                        except json.JSONDecodeError:
                            pass
                    elif cur_event == "error":
                        errors.append(raw)

    return {
        "http": 200,
        "content": "".join(p for p in content_parts if isinstance(p, str)),
        "tools": tool_names,
        "events": events,
        "errors": errors,
    }


async def main() -> None:
    uid, token = await make_user()
    print(f"临时账号: {uid[:8]}… (SOA)")
    print(f"提问: {PROMPT}\n")
    try:
        r = await asyncio.to_thread(run_probe, token)

        if r.get("http") != 200:
            print(f"❌ HTTP {r['http']}: {r.get('body')}")
            return

        text_out = r["content"]
        print(f"事件序列: {' → '.join(r['events'])}")
        print(f"工具调用 {len(r['tools'])} 次: {r['tools'] or '（模型本轮未调工具）'}")
        print(f"回复长度: {len(text_out)} 字")
        print(f"回复开头: {text_out[:160]!r}\n")

        fallback = "操作已完成，但我没能整理出文字说明"
        if r["errors"]:
            print(f"❌ 流内报错: {r['errors']}")
        elif not text_out.strip():
            print("❌ 回复为空 —— 兜底链路仍有问题")
        elif fallback in text_out:
            print("⚠️  命中兜底文案：模型返回空内容，多轮循环未覆盖到")
        else:
            print("✅ 回复有实质内容，兜底未被触发")
            if len(r["tools"]) >= 2:
                print("✅ 模型连续调用了多次工具 —— 多轮循环路径已被真实覆盖")
    finally:
        await cleanup(uid)
        await engine.dispose()
        print("\n临时账号与关联数据已清理")


asyncio.run(main())
