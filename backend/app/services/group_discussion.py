"""MOA 组多角色群辩调度器（模式 B）。

产出 SSE 事件流，由 routers/agent.py 的 /group-discuss 转成 text/event-stream 推给前端：
  stage       {stage, label}            当前阶段提示（开场/首轮/辩论/整合）
  role_start  {role_id,name,emoji,color,specialty}  某角色开始发言
  content     {role_id, delta}          该角色文本增量（流式）
  role_end    {role_id}                 该角色发言结束
  done        {plan:{markdown,quotes}}  主持人整合完成，附各角色金句
  error       {error}                   异常兜底
"""
import asyncio
import logging
import re

from app.services.agents.llm_client import get_llm_client
from app.services.agents.moa_personas import (
    FACILITATOR, LINXIAOSUAN, SUGEGE, LAOXU, AHAO, EXPERT_ORDER,
)

logger = logging.getLogger(__name__)

# 离线/无 Key 时的脚本兜底（保证答辩 demo 不依赖外网），内容与真实 LLM 产出同构
_SCRIPTED = {
    "opening": "收到，你一个人来杭州 3 天、当地预算 2000 元。下面请四位专家先各抒己见，再交叉过招，最后我来整合一份不超预算的方案。",
    "round1": {
        "linxiaosuan": "我先把账算明白：2000 块单人 3 天，住宿压到地铁沿线 250/晚、餐饮日均 230、门票挑免费的西湖加寺庙早场，市内全靠地铁。浪漫提议先报个价再谈。",
        "sugege": "钱要花在嘴上！菊英面馆片儿川、河坊街定胜糕、楼外楼东坡肉至少留一顿正餐，早餐去桐山沐馒头，吃的记忆比景点更值。",
        "laoxu": "别光赶路。永福寺禅意、孤山文澜阁、南宋御街的老字号，留半天安安静静看一座城怎么长出来的，比打卡十个网红点强。",
        "ahao": "出片要算好光。断桥清晨、雷峰塔日落、宝石山层林——都是免费机位，走官方步道安全又出片，拒绝野山夜爬。",
    },
    "round2": {
        "linxiaosuan": "@美食达人 美食我认，但楼外楼偏贵，换成知味观更稳；@风光猎人 宝石山黄昏好，但别超时赶末班地铁，我帮你们排进预算。",
        "sugege": "@财务总监 知味观可以，但菊英那顿片儿川不能砍，那是杭州的魂；@人文使者 你说的禅茶我陪你去，顺手拍张晨光茶席。",
        "laoxu": "@风光猎人 你那黄金时刻我支持，但雷峰塔日落人挤人，不如去茅家埠看水上日落，安静又有味。",
        "ahao": "@人文使者 茅家埠听你的；@财务总监 末班地铁我记下了，机位都排在 17:30 前收工，安全又出片。",
    },
}

_PLAN_TEMPLATE = """## 行程概览
- 出行人：{travelers}
- 总预算：约 ¥{total}（当地消费，不含往返大交通）
- 整体风格：人文 + 美食 + 轻松出片
- 节奏：松弛不赶，日均 2~3 个主场景

## 每日行程
**Day 1 · 西湖人文线（步行为主）**
- 上午：断桥—白堤—孤山（文澜阁、平湖秋月），趁人少拍照
- 下午：雷峰塔—苏堤散步，傍晚湖滨看日落
- 晚上：河坊街觅食（定胜糕、葱包桧），住地铁沿线非西湖边溢价房

**Day 2 · 灵隐与茶香（半日龙井）**
- 清晨：永福寺禅茶，安静避人流
- 上午：灵隐寺早场（7 点前人少）
- 中午：龙井村农家饭
- 下午：龙井半日，傍晚回西湖

**Day 3 · 老城美食（慢游）**
- 清晨：菊英面馆片儿川（6 点免排队）
- 上午：南宋御街—胡庆余堂，看老字号
- 下午：茅家埠水上日落机位（官方步道）
- 晚上：返程

## 预算明细
| 项目 | 预估 |
| --- | --- |
| 市内交通（地铁/公交） | ¥150 |
| 住宿（2 晚沿线） | ¥500 |
| 餐饮 | ¥700 |
| 门票/体验 | ¥300 |
| **合计** | **¥{total}** |

## 团队讨论摘要
- 财务总监守住省钱底线：住宿沿线、门票挑免费、通勤靠地铁。
- 美食达人保住美食灵魂：菊英片儿川与一顿正餐不可砍。
- 人文使者留住文史静心：永福寺禅茶与老字号半日。
- 风光猎人保住安全出片：黄金时刻机位走官方步道，17:30 前收工。
"""


def _chunk_text(text: str):
    """按句子/标点切分，便于逐段流式推送。"""
    parts = re.split(r'(?<=[。！？!?\n])', text)
    return [p for p in parts if p.strip()]


async def _llm_text(system_prompt: str, user_prompt: str) -> str:
    """调用 LLM 取一段纯文本；失败或空返回空串（交由上层兜底）。"""
    try:
        client = get_llm_client()
        resp = await client.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        text = (resp.get("content") or "").strip()
        return text
    except Exception as e:  # 网络/Key 异常都不应中断整场讨论
        logger.warning("MOA LLM call failed, fallback to scripted: %s", e)
        return ""


async def _speak(persona, user_prompt: str, fallback: str):
    """产出某角色一段发言文本（LLM 优先，空则脚本兜底）。"""
    text = await _llm_text(persona["system_prompt"], user_prompt)
    if not text:
        text = fallback
    return text


async def run_group_discussion(
    requirement: str,
    dest: str = "杭州",
    days: int = 3,
    budget: int = 2000,
    travelers: str = "1 人",
):
    task_ctx = (
        f"任务：为「{travelers}」规划「{dest}{days}日游」，当地预算 ¥{budget}（不含往返大交通，"
        f"仅用于住宿/餐饮/门票/市内交通）。用户需求：{requirement}"
    )

    # ---- 阶段：开场 ----
    yield {"type": "stage", "data": {"stage": "opening", "label": "主持人开场"}}
    opening = await _speak(
        FACILITATOR,
        f"{task_ctx}\n请用 2~3 句开场：点明你作为主持人的角色，并说明接下来会先让四位专家各自表态、再交叉辩论、最后由你整合。不要给具体景点。",
        _SCRIPTED["opening"],
    )
    async for ev in _emit_role(FACILITATOR, opening):
        yield ev

    transcript = [f"主持人：{opening}"]

    # ---- 阶段：首轮发言 ----
    yield {"type": "stage", "data": {"stage": "round1", "label": "专家首轮表态"}}
    for p in EXPERT_ORDER:
        prompt = (
            f"{task_ctx}\n你是「{p['name']}」（{p['specialty']}）。\n"
            f"目前讨论记录：\n{chr(10).join(transcript)}\n\n"
            f"请作为第一个/后续表态者，从你的专业角度给出【初始立场与建议】，60~140 字，带具体杭州地名/价位/时段。"
        )
        text = await _speak(p, prompt, _SCRIPTED["round1"][p["id"]])
        transcript.append(f"{p['name']}：{text}")
        async for ev in _emit_role(p, text):
            yield ev

    # ---- 阶段：交叉辩论 ----
    yield {"type": "stage", "data": {"stage": "round2", "label": "交叉辩论·互相妥协"}}
    for p in EXPERT_ORDER:
        prompt = (
            f"{task_ctx}\n你是「{p['name']}」（{p['specialty']}）。\n"
            f"目前讨论记录：\n{chr(10).join(transcript)}\n\n"
            f"请针对其他人的方案做【简短反驳或妥协】，必须 @点名至少一位其他专家，并给出你的调整，60~120 字。"
        )
        text = await _speak(p, prompt, _SCRIPTED["round2"][p["id"]])
        transcript.append(f"{p['name']}：{text}")
        async for ev in _emit_role(p, text):
            yield ev

    # ---- 阶段：主持人整合 ----
    yield {"type": "stage", "data": {"stage": "integrate", "label": "主持人整合方案"}}
    integrate_prompt = (
        f"{task_ctx}\n讨论记录：\n{chr(10).join(transcript)}\n\n"
        f"请整合成最终方案，必须包含以下 Markdown 板块：\n"
        "## 行程概览（出行人/总预算/风格/节奏）\n"
        "## 每日行程（按 Day 分块，含上午/下午/晚上）\n"
        "## 预算明细（表格：市内交通/住宿/餐饮/门票/合计，合计不超过预算）\n"
        "## 团队讨论摘要（一句话点出每位专家守住的底线）\n"
        "预算仅含当地消费，不含往返大交通。"
    )
    plan_md = await _llm_text(FACILITATOR["system_prompt"], integrate_prompt)
    if not plan_md:
        plan_md = _PLAN_TEMPLATE.format(travelers=travelers, total=budget)

    quotes = [
        {"role_id": p["id"], "name": p["name"], "emoji": p["emoji"], "color": p["color"],
         "text": _SCRIPTED["round2"][p["id"]]}
        for p in EXPERT_ORDER
    ]
    # 若走了 LLM，金句改为各角色最后一段发言摘要
    if transcript:
        for p in EXPERT_ORDER:
            for line in reversed(transcript):
                if line.startswith(f"{p['name']}：") and len(line) > len(p["name"]) + 1:
                    quotes = [q for q in quotes if q["role_id"] != p["id"]]
                    quotes.append({"role_id": p["id"], "name": p["name"], "emoji": p["emoji"],
                                   "color": p["color"], "text": line[len(p["name"]) + 1:]})
                    break

    yield {"type": "done", "data": {"plan": {"markdown": plan_md, "quotes": quotes}}}


async def _emit_role(persona, text: str):
    """把一个角色的整段发言拆成 SSE 事件流（role_start → content* → role_end）。"""
    yield {"type": "role_start", "data": {
        "role_id": persona["id"], "name": persona["name"], "emoji": persona["emoji"],
        "color": persona["color"], "specialty": persona["specialty"],
    }}
    for chunk in _chunk_text(text):
        yield {"type": "content", "data": {"role_id": persona["id"], "delta": chunk}}
        await asyncio.sleep(0.06)
    yield {"type": "role_end", "data": {"role_id": persona["id"]}}
