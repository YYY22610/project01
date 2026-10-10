"""MOA 多轮群辩 —— 真实 LLM 模式联调。

不强制 mock：直接读取 backend/.env 的 LLM_API_KEY（非空 → use_mock_llm=False → RealLLMClient）。
用假的 user_input 驱动完整流程，同时埋点采集：
  - 每次 LLM chat 调用的耗时 / 成败 / 是否空回复
  - 编排器“fallback to scripted”降级次数
  - 最终方案是否来自写死的 _PLAN_TEMPLATE（识别真实产出 vs 兜底）
  - 各角色发言长度（判断是否为 LLM 真实生成）

运行：backend/venv/Scripts/python.exe test_moa_group_real.py
（务必在 backend/ 目录下执行，以便加载 .env）
"""
import asyncio
import logging
import time

import app.services.agents.llm_client as lc
from app.config import settings
from app.services.autogen_group_discussion import (
    run_autogen_discussion,
    _PLAN_TEMPLATE,
)

# ---- 埋点：记录每次真实 LLM 调用 ----
orig_chat = lc.RealLLMClient.chat
CALL_LOG: list[dict] = []


async def measured_chat(self, messages, tools=None):
    t0 = time.time()
    try:
        resp = await orig_chat(self, messages, tools)
    except Exception as e:  # 异常上抛，由 _llm_text 捕获并降级
        CALL_LOG.append({"ok": False, "err": str(e)[:200], "ms": round((time.time() - t0) * 1000)})
        raise
    content = (resp.get("content") or "").strip()
    CALL_LOG.append({
        "ok": True,
        "ms": round((time.time() - t0) * 1000),
        "len": len(content),
        "empty": not content,
    })
    return resp


lc.RealLLMClient.chat = measured_chat

# ---- 埋点：捕获编排器降级日志 ----
FALLBACKS: list[str] = []
ERR_LOGS: list[str] = []


class _H(logging.Handler):
    def emit(self, r):
        msg = r.getMessage()
        if "fallback to scripted" in msg:
            FALLBACKS.append(msg)
        if "LLM API error" in msg:
            ERR_LOGS.append(msg)


logging.getLogger("app.services.agents.autogen_group_discussion").addHandler(_H())
logging.getLogger("app.services.agents.llm_client").addHandler(_H())


async def main():
    print(f"=== MOA 真实 LLM 联调 ===")
    print(f"use_mock_llm = {settings.use_mock_llm}  (False=真实模式)")
    print(f"BASE_URL      = {settings.LLM_API_BASE_URL}")
    print(f"MODEL         = {settings.LLM_MODEL}")
    print(f"KEY 已配置    = {'是' if settings.LLM_API_KEY else '否'}")
    print("-" * 60)

    async def fake_user_input(prompt: str) -> str:
        return "确认"

    events = []
    role_contents: dict[str, str] = {}
    t0 = time.time()
    async for ev in run_autogen_discussion(
        requirement="杭州3日游，一个人，想舒服点，不要太赶",
        dest="杭州", days=3, budget=2000, travelers="1 人",
        user_input=fake_user_input,
    ):
        events.append(ev)
        if ev["type"] == "content":
            role_contents.setdefault(ev["data"]["role_id"], "")
            role_contents[ev["data"]["role_id"]] += ev["data"]["delta"]
    elapsed = round((time.time() - t0) * 1000)

    # ---- 结果分析 ----
    order = [e["type"] for e in events]
    done_plan = next((e["data"]["plan"]["markdown"] for e in events if e["type"] == "done"), "")
    # 模板内容级独有短语（写死在 _PLAN_TEMPLATE 里、真实 LLM 不会原样写出）。
    # 注意：不能用品块标题（💰费用明细等）判定，因为合规的真实方案也会写这些标题 → 会误报。
    TEMPLATE_UNIQUE = ("茅家埠湿地秘境", "德寿宫、龙井观景台", "京杭大运河·小河直街", "菊英面馆片儿川", "知味观更稳")
    used_template = any(p in done_plan for p in TEMPLATE_UNIQUE)
    # FORMAT_SPEC 必填板块命中数（衡量 LLM 是否遵循输出格式规范）
    FORMAT_MARKERS = ("行程概览", "费用明细", "预算总结", "交通方案", "实用小贴士")
    fmt_hits = sum(1 for m in FORMAT_MARKERS if m in done_plan)
    # 落盘完整方案，便于人工审阅（用绝对路径，避免 git-bash /tmp 差异）
    _plan_path = "D:/27475/WorkBuddy-搭建网站/travel-experiment-platform/backend/moa_done_plan.txt"
    with open(_plan_path, "w", encoding="utf-8") as f:
        f.write(done_plan)

    print(f"总耗时        = {elapsed} ms")
    print(f"事件流顺序    = {order}")
    print(f"降级回退次数  = {len(FALLBACKS)}")
    if ERR_LOGS:
        print("LLM API 错误：")
        for e in ERR_LOGS:
            print("   -", e)
    print(f"整合方案兜底模板 = {'是（真实产出失败，_is_plan_like 判否）' if used_template else '否（真实 LLM 产出）'}  "
          f"[判定依据: 模板独有短语 {'命中' if used_template else '均未命中'}]")
    print(f"FORMAT_SPEC 板块命中 = {fmt_hits}/5 （行程概览/费用明细/预算总结/交通方案/实用小贴士）")

    ok_calls = [c for c in CALL_LOG if c.get("ok")]
    fail_calls = [c for c in CALL_LOG if not c.get("ok")]
    empty_calls = [c for c in ok_calls if c.get("empty")]
    print(f"\n真实 LLM 调用 = {len(CALL_LOG)} 次 | 成功 {len(ok_calls)} | 异常 {len(fail_calls)} | 成功但空回复 {len(empty_calls)}")
    if ok_calls:
        ms = [c["ms"] for c in ok_calls]
        print(f"单次耗时 ms：min={min(ms)} max={max(ms)} avg={round(sum(ms)/len(ms))}")
    if fail_calls:
        print("失败调用详情：")
        for c in fail_calls[:5]:
            print(f"   - {c['err']}")

    print("\n各角色发言长度（判断是否为 LLM 真实生成，非脚本）：")
    for rid, txt in role_contents.items():
        print(f"   {rid:12s} {len(txt):4d} 字 | 首句：{txt[:40].replace(chr(10),' ')}")

    print("\n最终方案前 600 字预览：")
    print(done_plan[:600])
    print(f"\n（完整方案已落盘 /tmp/moa_done_plan.txt，共 {len(done_plan)} 字）")

    print("\n=== 结论 ===")
    if fail_calls or len(FALLBACKS) == len(CALL_LOG):
        print("⚠️ 真实 LLM 调用未成功（全部/多数降级），需排查网络或 Key/模型配置")
    elif used_template:
        print("🟡 流程跑通但整合方案走了兜底模板（LLM 未产出合规方案，_is_plan_like 判否）")
    else:
        print("✅ 真实 LLM 端到端跑通，角色发言与方案均为模型实时生成")


if __name__ == "__main__":
    asyncio.run(main())
