"""探针：直接调 RealLLMClient，验证模型名/Key 是否生效，并打印整合阶段原始返回。"""
import asyncio
from app.config import settings
from app.services.agents.llm_client import get_llm_client
from app.services.agents.autogen_personas import build_host_system


async def main():
    print("MODEL =", settings.LLM_MODEL)
    client = get_llm_client()
    print("client =", type(client).__name__)
    sys_p = build_host_system()
    user_p = (
        "任务：为「1 人」规划「杭州3日游」，当地预算 ¥2000。\n"
        "请整合成最终方案，必须严格按输出格式规范排版，包含以下板块：\n"
        "## 行程概览 / ## 每日行程（按 Day 分块）/ ### 💎 免费必打卡 / "
        "### 💰 费用明细 / ### 📊 预算总结（含 `> 单人总预算：¥XXXX`）/ "
        "### 🚇 交通方案 / ### 💡 实用小贴士。预算仅含当地消费，不超 ¥2000。"
    )
    try:
        resp = await client.chat([
            {"role": "system", "content": sys_p},
            {"role": "user", "content": user_p},
        ])
        content = resp.get("content") or ""
        print("返回长度 =", len(content))
        print("前 1200 字：")
        print(content[:1200])
        # 粗判是否含 FORMAT_SPEC 板块
        for m in ("行程概览", "费用明细", "预算总结", "交通方案", "实用小贴士"):
            print(f"  板块[{m}] = {'有' if m in content else '无'}")
    except Exception as e:
        print("调用异常：", repr(e)[:500])


if __name__ == "__main__":
    asyncio.run(main())
