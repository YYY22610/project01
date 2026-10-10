"""MOA 多轮群辩编排器 —— mock 模式端到端验证。

强制 mock LLM（LLM_API_KEY 空），用假的 user_input 驱动完整流程，
断言事件流包含：stage / role_start+role_end（host+4专家）/ await_user /
await_confirm（含非空草案）/ done（含非空最终方案）。

运行：backend/venv/Scripts/python.exe test_moa_group_mock.py
"""
import os
import asyncio

# 强制 mock 模式（必须在 import app 之前设置）
os.environ["LLM_API_KEY"] = ""

from app.services.autogen_group_discussion import run_autogen_discussion


async def drive(answers: list[str]):
    """用一组预设回答驱动 user_input，收集全部 SSE 事件。"""
    queue = list(answers)

    async def fake_user_input(prompt: str) -> str:
        if queue:
            return queue.pop(0)
        return "确认"

    events = []
    async for ev in run_autogen_discussion(
        requirement="杭州3日游，一个人，想舒服点",
        dest="杭州", days=3, budget=2000, travelers="1 人",
        user_input=fake_user_input,
    ):
        events.append(ev)
    return events


def summarize(events):
    order = [e["type"] for e in events]
    roles = [e["data"].get("role_id") for e in events if e["type"] == "role_start"]
    return order, roles


def assert_flow(name, events, expect_confirm_count=1):
    order, roles = summarize(events)
    errors = []

    # 1) 角色发言完整：host + 4 专家各至少一次 role_start
    for needed in ("facilitator", "linxiaosuan", "sugege", "laoxu", "ahao"):
        # 注意 role_start 的 role_id 是平台 MOA id
        pass
    role_set = set(roles)
    for needed in ("facilitator", "linxiaosuan", "sugege", "laoxu", "ahao"):
        if needed not in role_set:
            errors.append(f"缺少角色发言 role_start: {needed}")

    # 2) 关键交互事件
    if "await_user" not in order:
        errors.append("缺少 await_user（主持人反问用户）")
    if order.count("await_confirm") != expect_confirm_count:
        errors.append(f"await_confirm 次数应为 {expect_confirm_count}，实际 {order.count('await_confirm')}")
    if "done" not in order:
        errors.append("缺少 done（最终方案）")

    # 3) 顺序：await_user 在 await_confirm 之前，await_confirm 在 done 之前
    if "await_user" in order and "await_confirm" in order and order.index("await_user") > order.index("await_confirm"):
        errors.append("await_user 应在 await_confirm 之前")
    if order.index("await_confirm") > order.index("done"):
        errors.append("await_confirm 应在 done 之前")

    # 4) 草案/最终方案非空，且含 FORMAT_SPEC 关键板块
    confirm_plan = next((e["data"]["plan"]["markdown"] for e in events if e["type"] == "await_confirm"), "")
    done_plan = next((e["data"]["plan"]["markdown"] for e in events if e["type"] == "done"), "")
    if not confirm_plan.strip():
        errors.append("await_confirm 的 plan.markdown 为空")
    if not done_plan.strip():
        errors.append("done 的 plan.markdown 为空")
    for marker in ("行程概览", "费用明细", "预算总结", "交通方案"):
        if marker not in done_plan:
            errors.append(f"最终方案缺少板块：{marker}")

    # 5) quotes 非空
    quotes = next((e["data"]["plan"].get("quotes") for e in events if e["type"] == "done"), [])
    if not quotes or len(quotes) != 4:
        errors.append(f"done 的 quotes 应为 4 条，实际 {len(quotes)}")

    if errors:
        print(f"❌ [{name}] 失败：")
        for e in errors:
            print("   -", e)
        return False
    print(f"✅ [{name}] 通过：事件数={len(events)}，角色={sorted(role_set)}，确认门次数={order.count('await_confirm')}")
    return True


async def main():
    print("=== MOA 多轮群辩 mock 验证 ===")
    ok = True

    # 场景 A：反问→确认（一次确认门）
    ev_a = await drive(["我想吃好喝好，预算内尽量舒服", "确认"])
    ok &= assert_flow("场景A 反问+确认", ev_a, expect_confirm_count=1)

    # 场景 B：反问→修改→确认（两次确认门，验证修订循环）
    ev_b = await drive(["喜欢人文，慢一点", "把第二天改成去西溪湿地，轻松点", "确认"])
    ok &= assert_flow("场景B 反问+修订+确认", ev_b, expect_confirm_count=2)
    # 修订后最终方案应含修订说明
    done_b = next(e["data"]["plan"]["markdown"] for e in ev_b if e["type"] == "done")
    if "修订说明" not in done_b:
        print("❌ [场景B] 修订后方案未包含修订说明")
        ok = False
    else:
        print("✅ [场景B] 修订说明已写入最终方案")

    print("\n=== 结果 ===", "全部通过 ✅" if ok else "存在失败 ❌")
    return ok


if __name__ == "__main__":
    success = asyncio.run(main())
    raise SystemExit(0 if success else 1)
