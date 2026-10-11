"""LLM 并发限流回归测试（不调真实 LLM，用假客户端验证信号量语义）。

不变量：
1. 同时在飞的 _chat_uncapped 调用数≤ LLM_MAX_CONCURRENCY；
2. 超过限流的请求进入排队，最终全部完成（只是串行化，不丢请求）；
3. 等待超过 LLM_CONCURRENCY_WAIT_TIMEOUT 时抛 RuntimeError（友好提示），而非无限挂起。

运行：venv/Scripts/python.exe test_llm_rate_limit.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.agents import llm_client as mod
from app.services.agents.llm_client import RealLLMClient


async def main():
    ok = True

    # ---- 场景 1：并发上限被遵守 ----
    mod._llm_semaphore = None
    mod._LLM_ACQUIRE_TIMEOUT = 5.0
    limit = 5
    mod.settings.LLM_MAX_CONCURRENCY = limit

    client = RealLLMClient()
    inflight = 0
    peak = 0
    completed = 0

    async def fake_uncapped(messages, tools=None):
        nonlocal inflight, peak, completed
        inflight += 1
        peak = max(peak, inflight)
        await asyncio.sleep(0.05)  # 模拟 LLM 延迟
        inflight -= 1
        completed += 1
        return {"content": "ok", "tool_calls": None}

    # 替换内部实现，让 chat 的限流包装生效但不打真实网络
    client._chat_uncapped = fake_uncapped

    async def one_call(i):
        return await client.chat([{"role": "user", "content": f"q{i}"}])

    await asyncio.gather(*[one_call(i) for i in range(20)])
    print(f"场景1 并发{20}请求/上限{limit}: peak_inflight={peak} completed={completed}")
    if peak > limit:
        print(f"  [FAIL] 峰值并发 {peak} 超过上限 {limit}")
        ok = False
    elif completed != 20:
        print(f"  [FAIL] 完成数 {completed} != 20")
        ok = False
    else:
        print("  [OK] 峰值并发未超上限，且 20 个请求全部完成")

    # ---- 场景 2：等待超时抛 RuntimeError（而非挂起） ----
    mod._llm_semaphore = None
    mod._LLM_ACQUIRE_TIMEOUT = 0.2
    mod.settings.LLM_MAX_CONCURRENCY = 1
    client2 = RealLLMClient()

    async def slow_uncapped(messages, tools=None):
        await asyncio.sleep(1.0)  # 长时间占用唯一许可
        return {"content": "ok", "tool_calls": None}

    client2._chat_uncapped = slow_uncapped

    # 第一个请求占住许可
    t1 = asyncio.create_task(client2.chat([{"role": "user", "content": "a"}]))
    await asyncio.sleep(0.05)  # 确保它已获取许可
    # 第二个请求等待 0.2s 后应超时
    try:
        await client2.chat([{"role": "user", "content": "b"}])
        print("场景2 [FAIL] 第二个请求本应超时抛错，却正常返回了")
        ok = False
    except RuntimeError as e:
        print(f"场景2 等待超时 [OK]: {e}")
    await t1  # 等第一个完成

    # ---- 场景 3：许可在异常时也会释放（不泄漏槽位）----
    mod._llm_semaphore = None
    mod._LLM_ACQUIRE_TIMEOUT = 5.0
    mod.settings.LLM_MAX_CONCURRENCY = 1
    client3 = RealLLMClient()
    boom = {"n": 0}

    async def flaky_uncapped(messages, tools=None):
        boom["n"] += 1
        raise ValueError("模拟上游异常")

    client3._chat_uncapped = flaky_uncapped
    for _ in range(3):
        try:
            await client3.chat([{"role": "user", "content": "x"}])
        except ValueError:
            pass
    # 若槽位泄漏，第三次就会因拿不到许可而超时报 RuntimeError；
    # 能连续 3 次抛上游 ValueError 而非排队超时，说明许可正常归还。
    if boom["n"] == 3:
        print("场景3 异常释放许可 [OK]: 连续3次都打到上游，未被限流卡住")
    else:
        print(f"场景3 [FAIL] 只打到上游 {boom['n']} 次，许可可能泄漏")
        ok = False

    print("\n结论:", "全部通过" if ok else "存在失败")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))