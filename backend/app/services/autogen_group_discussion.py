"""MOA 组多角色群辩编排器（移植自 AutoGen travel-planner，模式 B）。

与 app/services/group_discussion.py 的区别：本编排器支持**完整多轮用户互动**——
群聊进行中主持人可向用户提问并暂停等待回答（await_user），
群聊结束后进入**确认门**（await_confirm）：用户可提出修改意见让主持人修订，直到确认。

产出 SSE 事件流，由 routers/moa_group.py 转成 text/event-stream 推给前端：
  stage         {stage, label}            阶段提示
  role_start    {role_id,name,emoji,color,specialty}  某角色开始发言
  content       {role_id, delta}          该角色文本增量（流式）
  role_end      {role_id}                 该角色发言结束
  await_user    {prompt}                  主持人/角色向用户提问，等待用户输入（恢复接口回填）
  await_confirm {plan:{markdown,quotes}  确认门：展示草案，等待用户「确认 / 修改意见」
  done          {plan:{markdown,quotes}  最终方案已确认
  error         {error}                   异常兜底

LLM 调用复用平台 get_llm_client()（真实 LLM + 无 Key 的 mock 兜底），不依赖 autogen-agentchat 运行时。
"""
import asyncio
import json
import logging
import re

from app.config import settings
from app.services.agents.autogen_personas import (
    PERSONAS,
    EXPERT_ORDER,
    HOST,
    DISPLAY_NAME,
    moa_member,
    build_persona_system,
    build_host_system,
)
from app.services.agents.llm_client import get_llm_client
from app.services.search_service import web_search

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 脚本兜底（无 LLM Key / 网络异常时，保证答辩 demo 仍可跑通，内容与真实产出同构）
# ---------------------------------------------------------------------------
_SCRIPTED_OPENING = (
    "收到，你一个人来{dest}{days}天、当地预算 ¥{budget}。下面先请四位专家各抒己见，"
    "再交叉过招，最后我来整合一份兼顾省钱、好吃、有文化、出片安全的方案。先问你一句——"
)

_SCRIPTED_ROUND1 = {
    "p_finance": "【交通方式】地铁1/2号线为主【住宿选择】青旅或地铁沿线经济房，约120/晚【预算明细】总预算1000，住宿360+餐饮300+门票100+交通50，余190机动。【交通方式】公交补足，3天合计60元【住宿选择】避开西湖边溢价房，首选南宋御街/武林广场附近【预算明细】机动190可补贴餐饮升级。",
    "p_food": "【餐饮安排】片儿川25、定胜糕10、葱包桧10【餐饮安排】菊英面馆早场免排队【餐饮安排】河坊街人均60/天足够地道【餐饮安排】知味观片儿川优于楼外楼，性价比高【餐饮安排】永福寺禅茶也是杭州味觉一景。",
    "p_culture": "【景点游览】孤山文澜阁免费【景点游览】永福寺禅茶免费【景点游览】南宋御街老字号半日【景点游览】胡雪岩故居旧门票¥20【景点游览】浙江省博物馆孤山馆免费。",
    "p_scenery": "【景点游览】断桥清晨免费【景点游览】雷峰塔日落机位【景点游览】茅家埠水上日落【安全提示】走官方步道17:30前收工【景点游览】宝石山黄昏俯瞰但注意脚下滑石。",
}

_SCRIPTED_ROUND2 = {
    "p_finance": "@美食达人 知味观比楼外楼性价比高；【住宿选择】青旅可压到110/晚【预算明细】省下40元补贴餐饮【交通方式】宋城/公交价格低【住宿选择】南宋御街汉庭/如家约160/晚更稳妥。",
    "p_food": "@财务总监 片儿川不能砍；【餐饮安排】菊英面馆早场【餐饮安排】大马弄菜市场早餐【餐饮安排】河坊街知味观/咬不得猫耳朵【餐饮安排】九溪烟树沿途农家饭。",
    "p_culture": "@风光猎人 茅家埠日落可以；【景点游览】南宋御街顺路看胡庆余堂【景点游览】灵隐寺早7点前人少【景点游览】飞来峰造像免费【景点游览】京杭大运河小河直街。",
    "p_scenery": "@人文使者 茶席机位不错；【景点游览】机位排17:00前【景点游览】九溪烟树徒步【安全提示】不野山夜爬【景点游览】杨梅岭徒步路线【景点游览】龙井村免费。",
}

_SCRIPTED_QUOTES = {
    "p_finance": "住宿沿线、门票挑免费、通勤靠地铁，省钱底线我守住了。",
    "p_food": "菊英片儿川与一顿正餐不可砍，杭州的魂在胃里。",
    "p_culture": "永福寺禅茶与老字号半日，文史静心不能少。",
    "p_scenery": "黄金时刻机位走官方步道，17:30 前收工，安全又出片。",
}

# 主持人每日行程草案 mock 兜底（真实模式 LLM 失败时用，结构与真实输出同构）
_SCRIPTED_DAILY = """\
```json
{"days": [
  {"tag": "步行为主", "title": "西湖人文线", "items": [
    {"time": "上午", "text": "断桥—白堤—孤山（2.5h，免费）"},
    {"time": "下午", "text": "雷峰塔—苏堤散步（2h，门票参考40）"},
    {"time": "晚上", "text": "河坊街觅食（定胜糕/葱包桧），住地铁沿线经济房"}
  ]},
  {"tag": "半日龙井", "title": "灵隐与茶香", "items": [
    {"time": "清晨", "text": "永福寺禅茶（避开人流）"},
    {"time": "上午", "text": "灵隐寺早场（7点前人少，门票参考75）"},
    {"time": "中午", "text": "龙井村农家饭（人均50）"},
    {"time": "下午", "text": "龙井半日，傍晚回西湖"}
  ]},
  {"tag": "慢游", "title": "老城美食", "items": [
    {"time": "清晨", "text": "菊英面馆片儿川（6点免排队，25/碗）"},
    {"time": "上午", "text": "南宋御街—胡庆余堂老字号"},
    {"time": "下午", "text": "茅家埠水上日落机位（免费）"},
    {"time": "晚上", "text": "返程"}
  ]}
]}
```
"""

_PLAN_TEMPLATE = """🏛️ **方案**

**方案 A：经典全景深度游**

Day 1：断桥残雪-白堤-**孤山**（浙江省博物馆孤山馆，免费）-苏堤春晓-**雷峰塔**（登塔观日落，¥40/人，需购票）-长桥公园看日落。 Day 2：灵隐寺与飞来峰（¥75，需预约）-中午天外天就餐-下午龙井村品茶-晚上河坊街与南宋御街。 Day 3：**西溪国家湿地公园**（需预约，体验摇橹船，免费）-下午河渚街-根据时间返程。

**方案 B：人文禅意慢游**

Day 1：茅家埠漫步-杨公堤-下午中国丝绸博物馆-傍晚北山街香樟树与民国建筑。 Day 2：法喜寺（¥10，需预约）-中午天竺-下午梅家坞茶园发呆-晚上武林夜市。 Day 3：小河直街-拱宸桥-京杭大运河博物馆-下午返程。

**方案 C：自然野趣休闲游**

Day 1：西湖游船（上三潭印月，需购票）-下午花港观鱼-晚上观看印象西湖演出（需购票）。 Day 2：**西溪国家湿地公园深度游**（需预约，电瓶船加步行）-下午西溪天堂商业街-晚上周边就餐。 Day 3：良渚古城遗址公园（需预约，体验早期文明）-下午良渚博物院-返程。

---

💡 **实用小贴士**

- **交通**：西湖景区周末及节假日实行单双号限行且极度拥堵，强烈建议地铁加共享单车出行，切勿自驾进入核心区。
- **预约**：灵隐寺、飞来峰、浙江省博物馆、良渚古城遗址等热门场馆必须提前 3-7 天在官方微信公众号预约，现场不售票。
- **美食**：避开景区周边的"网红"杭帮菜连锁店，推荐前往中山中路、凤起路或武林路周边寻找本地人排队的社区老店。

这三套方案中，哪一套的底层逻辑最契合您本次出行的核心诉求呢？

```json
{
  "days": [
    {"tag": "步行为主", "title": "西湖人文线", "items": [
      {"time": "上午", "text": "断桥—白堤—孤山（2.5h，免费）"},
      {"time": "下午", "text": "雷峰塔—苏堤散步（2h，¥40）"},
      {"time": "晚上", "text": "河坊街觅食，住地铁沿线"}
    ]},
    {"tag": "半日龙井", "title": "灵隐与茶香", "items": [
      {"time": "清晨", "text": "永福寺禅茶（避开人流）"},
      {"time": "上午", "text": "灵隐寺早场（7点前人少，¥75）"},
      {"time": "中午", "text": "龙井村农家饭（人均¥50）"},
      {"time": "下午", "text": "龙井半日，傍晚回西湖"}
    ]},
    {"tag": "慢游", "title": "老城美食", "items": [
      {"time": "清晨", "text": "菊英面馆片儿川（6点免排队，¥25）"},
      {"time": "上午", "text": "南宋御街—胡庆余堂老字号"},
      {"time": "下午", "text": "茅家埠水上日落机位（免费）"},
      {"time": "晚上", "text": "返程"}
    ]}
  ]
}
```
"""


def is_confirm(text: str) -> bool:
    return text.strip().lower() in ("确认", "可以", "ok", "yes", "是的", "没问题", "通过", "confirm", "同意")


def _chunk_text(text: str):
    """按句子/标点切分，便于逐段流式推送。"""
    parts = re.split(r"(?<=[。！？!?\n])", text)
    return [p for p in parts if p.strip()]


def _is_plan_like(text: str) -> bool:
    """判断 LLM 产出是否符合六项要素骨架（精确标题至少命中 3 项，防止 LLM 自创格式）。"""
    if not text or len(text) < 50:
        return False
    markers = ["（一）每日行程安排", "（二）景点游览方案", "（三）交通方案", "（四）住宿选择", "（五）餐饮安排", "（六）预算明细"]
    return sum(1 for m in markers if m in text) >= 3


async def _llm_text(system_prompt: str, user_prompt: str) -> str:
    """调用平台 LLM 取一段纯文本；失败或空返回空串（交由上层兜底）。"""
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


async def _gather_search_refs(dest: str, days: int, budget: int, requirement: str) -> str:
    """搜索增强（RAG）：主持人整合前抓取真实网页摘要，返回 markdown 引用块。

    免 Key（DuckDuckGo 网页版抓取 + Bing 兜底，见 search_service.web_search）。
    任何失败都降级为「无参考」返回空串，绝不阻断群辩。
    mock 模式（无 LLM Key）走写死模板，不联网搜索。
    """
    if settings.use_mock_llm or not settings.SEARCH_ENHANCE:
        return ""
    # 查询词精准化：价格导向 + 从用户需求提取偏好词，让 Bing 返回具体价格页/攻略页
    pref_keywords = ""
    for kw in ("美食", "人文", "文化", "省钱", "穷游", "出片", "摄影", "亲子", "徒步", "购物", "夜景", "历史"):
        if kw in requirement:
            pref_keywords += f" {kw}"
    queries = [
        f"{dest}{days}日游 攻略 2026{pref_keywords}",
        f"{dest} 景点 门票 价格 多少钱",
        f"{dest} 必去景点 门票价格{pref_keywords}",
        f"{dest} 美食 小吃 人均 价格 推荐",
        f"{dest} 经济型酒店 青旅 一晚 价格",
        f"{dest} 地铁 公交 票价",
    ]

    async def _one(q: str) -> list:
        try:
            # Bing 主路 ~0.7s；DDG 兜底可能 ~10s，超时留 15s 余量
            return await asyncio.wait_for(web_search(q, num=5), timeout=15)
        except Exception:
            return []

    try:
        batches = await asyncio.gather(*[_one(q) for q in queries])
        seen: set[str] = set()
        lines: list[str] = []
        for q, rs in zip(queries, batches):
            if not rs:
                continue
            added = 0
            for r in rs:
                url = (r.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                if not added:  # 该查询首次新增引用时才打印查询标题（避免重复结果产生空标题）
                    lines.append(f"【搜索：{q}】")
                    added = 1
                title = (r.get("title") or "").strip().replace("\n", " ")
                snippet = (r.get("snippet") or "").strip().replace("\n", " ")
                lines.append(f"- {title}（{url}）")
                if snippet:
                    lines.append(f"  {snippet}")
                if len(seen) >= 20:  # 控制注入量，避免 prompt 过长
                    break
        logger.info("MOA 搜索增强: %d 个查询 → %d 条唯一引用", len(queries), len(seen))
        return "\n".join(lines)
    except Exception as e:
        logger.warning("MOA 搜索增强失败（降级为无参考）: %s", e)
        return ""


def _refs_block(search_refs: str) -> str:
    """把联网参考资料包装成统一的 prompt 注入块。

    所有发言阶段共用；空引用（mock 模式/搜索失败）返回空串，不污染 prompt。
    含「严禁编造来源标注」硬约束：LLM 常自行编造「来源：景区官网」等虚假出处，
    与用户重视学术真实性的要求冲突，必须显式禁止。
    """
    if not search_refs:
        return ""
    return (
        "【联网参考资料】（以下是搜索到的真实信息，发言中提到的具体景点、价格、营业时间、"
        "店铺推荐必须优先以此为准；参考资料没有的信息严禁编造具体数字，也严禁编造"
        "「来源：xxx」之类参考资料中不存在的出处标注）：\n"
        f"{search_refs}\n\n"
    )


# 常见平台名 → 域名关键词映射：来源校验时若引用块 URL 含对应域名，视为「有据可依」
_SOURCE_DOMAIN_MAP = {
    "知乎": "zhihu", "携程": "ctrip", "美团": "meituan", "大众点评": "dianping",
    "去哪儿": "qunar", "马蜂窝": "mafengwo", "飞猪": "fliggy", "小红书": "xiaohongshu",
    "百度百科": "baike.baidu", "百度地图": "map.baidu", "高德": "amap",
    "穷游": "qyer", "驴妈妈": "lvmama", "同程": "ly.com", "途牛": "tuniu",
}


def _ref_contains(refs_text: str, src: str) -> bool:
    """判断来源标注是否能在联网参考资料中找到对应。

    匹配优先级：① 平台名映射的域名关键词（如「知乎」→zhihu，URL 含即算）；
    ② 直接子串匹配（忽略大小写）。参考资料本身来自真实网页（标题/URL/摘要）。
    """
    if not refs_text or not src:
        return False
    s = src.strip().lower()
    if not s:
        return False
    if s in refs_text.lower():
        return True
    domain = _SOURCE_DOMAIN_MAP.get(src.strip())
    if domain and domain in refs_text.lower():
        return True
    return False


def _sanitize_sources(markdown: str, refs_text: str) -> str:
    """代码层来源校验：把方案中所有「来源：X」标注逐一与联网参考资料比对。

    X 能在参考资料中找到 → 保留；找不到（或无参考资料）→ 替换为「价格待核实」。
    这是不依赖 LLM 自觉的硬校验，从根上消灭编造的「来源：景区官网/携程/美团」等假出处。
    同时处理两种形态：行内「来源：X」与表格「来源」列。
    """
    if not markdown:
        return markdown

    def _repl(m: "re.Match") -> str:
        src = m.group(1).strip()
        if _ref_contains(refs_text, src):
            return m.group(0)
        return "价格待核实"

    # (a) 行内/段落来源标注：来源：X / 来源: X / （来源：X）
    out = re.sub(r"来源[：:]\s*([^，。；;|）)\n]+)", _repl, markdown)

    # (b) 表格「来源」列：定位表头含「来源」的列，逐行校验单元格
    lines = out.split("\n")
    header_line_idx = None
    src_col = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("|") and "---" not in s:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if "来源" in cells:
                header_line_idx = i
                src_col = cells.index("来源")
                break
    if src_col is not None and header_line_idx is not None:
        for i in range(header_line_idx + 1, len(lines)):
            s = lines[i].strip()
            if not s.startswith("|") or "---" in s:
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) <= src_col:
                continue
            v = cells[src_col].strip()
            if v and v != "来源" and not _ref_contains(refs_text, v):
                cells[src_col] = "价格待核实"
                lines[i] = "| " + " | ".join(cells) + " |"
        out = "\n".join(lines)
    return out


# 临时规划（右侧栏实时汇总）六项要素字段
TEMP_PLAN_KEYS = ["daily", "spots", "transport", "lodging", "dining", "budget"]

# 【标签】→ 临时规划字段映射
_TAG_TO_KEY = {
    "交通方式": "transport", "交通": "transport",
    "住宿选择": "lodging", "住宿": "lodging",
    "预算明细": "budget", "预算": "budget",
    "餐饮安排": "dining", "餐饮": "dining",
    "景点游览": "spots", "景点": "spots",
    "每日行程": "daily", "行程": "daily",
}


def _parse_tagged(text: str) -> dict:
    """从专家的结构化发言中解析【标签】内容，归入临时规划字段（六项要素骨架）。

    格式约定（见 _STRUCTURED_SPEAK / round1/2 prompt）：
      【交通方式】一句话…【住宿选择】一句话…
    未识别标签的内容丢弃（不进入临时规划，只作为群聊发言展示）。
    """
    out: dict[str, list[str]] = {}
    for m in re.finditer(r"【([^】]{1,12})】([^【]*)", text):
        tag = m.group(1).strip()
        content = m.group(2).strip()
        if not content:
            continue
        key = _TAG_TO_KEY.get(tag)
        if not key:
            continue
        out.setdefault(key, []).append(content)
    return out


def _extract_plan_json(text: str) -> dict | None:
    """从主持人整合文本中提取 ```json ... ``` 代码块并解析。

    返回 dict 失败返回 None（调用方降级走 markdown 兜底）。
    """
    m = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if not m:
        # 兼容：有的 LLM 会输出 ``` { ... } ``` 或裸 JSON
        m = re.search(r"```\s*\n?(\{.*?\})\s*\n?```", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _plan_data_to_markdown(data: dict) -> str:
    """将结构化 plan data 序列化为六项要素 markdown（用于 Word 导出等纯文本渲染）。"""
    lines: list[str] = []
    meta = data.get("meta") or {}
    lines.append(f"## 行程概览")
    lines.append(f"- 出行人：{meta.get('travelers', '-')}")
    lines.append(f"- 总预算：约 {meta.get('total', '-')}")
    lines.append(f"- 整体风格：{meta.get('style', '-')}")
    lines.append(f"- 节奏：{meta.get('pace', '-')}")
    lines.append("")
    days = data.get("days") or []
    lines.append("## （一）每日行程安排")
    for i, d in enumerate(days, 1):
        tag = d.get("tag", "")
        title = d.get("title", "")
        head = f"**Day {i} · {title}**" + (f"（{tag}）" if tag else "")
        lines.append(head)
        for it in (d.get("items") or []):
            lines.append(f"- {it.get('time', '-')}：{it.get('text', '-')}")
        lines.append("")
    spots = data.get("spots") or []
    if spots:
        lines.append("## （二）景点游览方案")
        lines.append("| 顺序 | 景点 | 停留时长 | 门票 |")
        lines.append("| --- | --- | --- | --- |")
        for i, s in enumerate(spots, 1):
            lines.append(f"| {i} | {s.get('name','-')} | {s.get('stay','-')} | {s.get('fee','-')} |")
        lines.append("")
    for key, title in [("transport", "（三）交通方案"), ("lodging", "（四）住宿选择"), ("dining", "（五）餐饮安排"), ("budget", "（六）预算明细")]:
        val = data.get(key)
        if val:
            lines.append(f"## {title}")
            if isinstance(val, list):
                for v in val:
                    lines.append(f"- {v}")
            else:
                lines.append(f"{val}")
            lines.append("")
    return "\n".join(lines).strip()


def _parse_template_to_data(plan_md: str, travelers: str, budget: int, days: int) -> dict | None:
    """把 _PLAN_TEMPLATE（markdown）解析为简版 data，用于前端卡片渲染兜底。

    仅取行程概览（meta）和每日行程前几个 title+items，能力有限，够用就好。
    """
    out: dict = {
        "meta": {"travelers": travelers, "total": f"¥{budget}", "style": "人文·美食", "pace": "松弛不赶"},
        "days": [],
        "spots": [],
        "transport": "",
        "lodging": "",
        "dining": "",
        "budget": "",
    }
    if not plan_md:
        return None
    # 提取每个 **Day N · ...** 后跟的列表项
    for m in re.finditer(r"\*\*(Day\s*\d+)\s*·\s*([^*]+?)\*\*", plan_md):
        day_title = m.group(2).strip().rstrip("（)）")
        # 抓接下来 3-6 个 "- xx：yy" 行
        start = m.end()
        nxt = re.search(r"\*\*(Day|\u4e00|\u4e8c|\u4e09|\u4ee5|\u53e3|\u53c2)\*\*|\n##", plan_md[start:])
        seg = plan_md[start: start + nxt.start()] if nxt else plan_md[start:start + 500]
        items = []
        for it in re.finditer(r"-\s*(\S+?[：:])\s*(.+)", seg):
            items.append({"time": it.group(1).rstrip("：:"), "text": it.group(2).strip()})
        if items:
            out["days"].append({"tag": "", "title": day_title, "items": items[:6]})
    # 抓取景点表格
    if "## （二）景点游览方案" in plan_md:
        sp_section = plan_md.split("## （二）景点游览方案", 1)[1]
        sp_section = sp_section.split("\n##", 1)[0]
        for row in re.finditer(r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", sp_section):
            if row.group(1).strip() == "顺序":
                continue
            out["spots"].append({
                "name": row.group(2).strip(),
                "stay": row.group(3).strip(),
                "fee": row.group(4).strip(),
            })
    return out if out["days"] else None


async def run_autogen_discussion(
    requirement: str,
    dest: str = "杭州",
    days: int = 3,
    budget: int = 2000,
    travelers: str = "1 人",
    user_input=None,
    should_stop=None,
):
    """多轮群辩 + 确认门 异步生成器，逐条 yield SSE 事件字典。

    user_input: async def(user_prompt: str) -> str，由路由层用 Future 驱动（等待用户经 resume 接口回填）。
    should_stop: Callable[[], bool]，每阶段前检查（暂停/取消开关），返回 True 时中止并 yield error。
    """
    if user_input is None:
        raise RuntimeError("run_autogen_discussion 需要 user_input 回调")

    def _stop() -> bool:
        return bool(should_stop()) if should_stop else False

    task_ctx = (
        f"任务：为「{travelers}」规划「{dest}{days}日游」，当地预算 ¥{budget}（不含往返大交通，"
        f"仅用于住宿/餐饮/门票/市内交通）。用户需求：{requirement}"
    )
    transcript: list[str] = []
    last_by: dict[str, str] = {}
    # 临时规划（右侧栏实时汇总）：六项要素骨架 + days_draft（主持人行程草案 JSON 字符串），讨论中实时归并
    temp_plan: dict = {k: [] for k in TEMP_PLAN_KEYS}

    async def _speak(autogen_name: str, user_prompt: str, fallback: str):
        """让某角色发言：yield role_start/content*/role_end，并把文本记入 transcript。"""
        m = moa_member(autogen_name)
        yield {"type": "role_start", "data": {
            "role_id": m["id"], "name": m["name"], "emoji": m["emoji"],
            "color": m["color"], "specialty": m["specialty"],
        }}
        if autogen_name == "host":
            system = build_host_system()
        else:
            p = next(x for x in PERSONAS if x["name"] == autogen_name)
            system = build_persona_system(p)
        # mock 模式直接走脚本兜底，保证无 Key 也能产出完整、合理的群辩内容
        if settings.use_mock_llm:
            text = fallback
        else:
            text = await _llm_text(system, user_prompt)
            if not text:
                text = fallback
        for chunk in _chunk_text(text):
            yield {"type": "content", "data": {"role_id": m["id"], "delta": chunk}}
            await asyncio.sleep(0.03)
        yield {"type": "role_end", "data": {"role_id": m["id"]}}
        transcript.append(f"{DISPLAY_NAME.get(autogen_name, autogen_name)}：{text}")
        last_by[autogen_name] = text
        # 专家发言后：按【标签】归入临时规划并实时推送（主持人不参与聚合）
        if autogen_name != "host":
            for k, items in _parse_tagged(text).items():
                temp_plan[k].extend(items)
            yield {"type": "temp_plan", "data": {
                # days_draft 是 JSON 字符串（主持人草案），不能 list() 拆成字符
                "plan": {k: (list(v) if isinstance(v, list) else v) for k, v in temp_plan.items()}
            }}

    async def _speak_all(specs):
        """并发驱动多位专家发言，按事件到达顺序流式 yield（群聊并发效果）。

        specs: list of (autogen_name, user_prompt, fallback)。
        同轮专家发言彼此独立，并发可将「N 次串行调用」压缩为「1 次并发批次」，
        显著缩短整场时延；各自的 transcript/last_by 副作用在事件循环内串行提交，无竞态。
        """
        q: "asyncio.Queue" = asyncio.Queue()

        async def _produce(name, prompt, fallback):
            async for ev in _speak(name, prompt, fallback):
                await q.put(ev)
            await q.put(None)  # 该专家发言结束哨兵

        tasks = [asyncio.create_task(_produce(n, p, f)) for (n, p, f) in specs]
        finished = 0
        while finished < len(tasks):
            ev = await q.get()
            if ev is None:
                finished += 1
            else:
                yield ev
        # 收尾并暴露潜在异常，避免静默丢失
        for t in tasks:
            if t.exception():
                t.result()

    # ---- 开场前：联网搜索一次，整场所有发言阶段复用同一份参考资料 ----
    # （Bing 主路 ~1s；mock 模式/搜索失败返回空，refs_block 为空串不污染任何 prompt）
    search_refs = await _gather_search_refs(dest=dest, days=days, budget=budget, requirement=requirement)
    refs_block = _refs_block(search_refs)

    # ---- 阶段：开场 ----
    if _stop():
        yield {"type": "error", "data": {"error": "AI 助理服务已暂停"}}
        return
    yield {"type": "stage", "data": {"stage": "opening", "label": "主持人开场"}}
    async for ev in _speak(
        "host",
        f"{task_ctx}\n{refs_block}"
        f"【角色：主持人】请只用 1-2 句话（30-80 字）开场，介绍自己的角色（我是本场{dest}{days}日游的主持人）+ 简述接下来的流程（先请四位专家各自表态，再交叉辩论，最后由我整合出右侧栏的最终方案）。"
        f"**严禁**：① 替任何专家写发言；② 使用「## 财务总监/美食达人/... 发言」这种角色大标题——专家的发言由他们自己后续输出；③ 列具体景点/价格/行程——方案细节由我在最后整合时统一给到右侧栏。",
        _SCRIPTED_OPENING.format(dest=dest, days=days, budget=budget),
    ):
        yield ev

    # ---- 阶段：首轮发言（4 位专家并发） ----
    if _stop():
        yield {"type": "error", "data": {"error": "AI 助理服务已暂停"}}
        return
    yield {"type": "stage", "data": {"stage": "round1", "label": "专家首轮表态"}}
    round1_specs = [
        (p["name"],
         f"{task_ctx}\n{refs_block}你是「{p['display_name']}」（{p['peers']} 之外的一位职能专家）。\n"
         f"请按你的职责标签输出 **3-5 个【标签】块**（每块 1 句话，合计 80~180 字），"
         f"给出你在自己职责领域内的核心建议：财务总监负责【交通方式】【住宿选择】【预算明细】，美食达人负责【餐饮安排】，"
         f"人文使者负责【景点游览】，风光猎人负责【景点游览】【安全提示】。"
         f"建议要多一些——讨论共 2 轮，凑够 3 天行程每天需要 3-4 个不同建议（地点/餐厅/酒店）。",
         _SCRIPTED_ROUND1[p["id"]])
        for p in EXPERT_ORDER
    ]
    async for ev in _speak_all(round1_specs):
        yield ev

    # ---- 阶段：主持人排每日行程草案（基于 round1 专家推荐粗排，临时规划 Day 卡立即可见）----
    if _stop():
        yield {"type": "error", "data": {"error": "AI 助理服务已暂停"}}
        return
    yield {"type": "stage", "data": {"stage": "draft", "label": "主持人排每日行程草案"}}
    draft_prompt = (
        f"{task_ctx}\n讨论记录：\n{chr(10).join(transcript)}\n\n"
        f"{refs_block}"
        "你是主持人。请基于以上专家推荐，先排一版【每日行程草案】（Day 1/2/3 各 3-4 个时段），"
        "**只输出 JSON**（```json 代码块包裹，无其他文字）：\n"
        '{"days": [{"tag": "风格标签", "title": "主题", "items": [{"time": "上午", "text": "具体地点+活动（时长/门票）"}]}]}\n'
        "要求：Day 1/2/3 各含上午/下午/晚上（可加清晨/中午），每段给出具体地点和活动。"
    )
    draft_text = await _llm_text(build_host_system(), draft_prompt)
    if not draft_text:
        draft_text = _SCRIPTED_DAILY.format(dest=dest, days=days, budget=budget)
    draft_data = _extract_plan_json(draft_text)
    # mock 模式 / LLM 未按 JSON 输出时：回退用脚本草案，保证临时规划 Day 卡有内容
    if not draft_data or not draft_data.get("days"):
        draft_data = _extract_plan_json(_SCRIPTED_DAILY)
    if draft_data and draft_data.get("days"):
        # 存草案 JSON 字符串到 temp_plan.days_draft（前端解析渲染 Day 卡）
        temp_plan["days_draft"] = json.dumps(draft_data.get("days"), ensure_ascii=False)
        yield {"type": "temp_plan", "data": {
            "plan": {k: (list(v) if isinstance(v, list) else v) for k, v in temp_plan.items()}
        }}

    # ---- 阶段：主持人向用户确认偏好（await_user，暂停等待回答） ----
    if _stop():
        yield {"type": "error", "data": {"error": "AI 助理服务已暂停"}}
        return
    yield {"type": "stage", "data": {"stage": "ask_user", "label": "主持人向你确认偏好"}}
    question = (
        f"用户，收到你的需求了。这趟「{dest}{days}日游」当地预算 ¥{budget}，你更看重哪一点？"
        f"比如：极致省钱 / 吃好喝好 / 文化沉浸 / 出片好看，或让我帮你权衡？"
        f"也欢迎补充任何偏好（同行人、体力、忌口等）。"
    )
    yield {"type": "await_user", "data": {"prompt": question}}
    answer = (await user_input(question)).strip()
    transcript.append(f"用户：{answer}")
    # 把用户回答回灌给后续角色，使辩论更贴合
    task_ctx += f"\n（用户补充偏好：{answer}）"

    # ---- 阶段：交叉辩论（4 位专家并发，各自基于同一轮1记录反驳/妥协） ----
    if _stop():
        yield {"type": "error", "data": {"error": "AI 助理服务已暂停"}}
        return
    yield {"type": "stage", "data": {"stage": "round2", "label": "交叉辩论·互相妥协"}}
    round2_specs = [
        (p["name"],
         f"{task_ctx}\n{refs_block}你是「{p['display_name']}」（{p['peers']} 之外的一位职能专家）。\n"
         f"目前讨论记录：\n{chr(10).join(transcript)}\n\n"
         f"请用 **2-3 个【标签】块**（每块 1 句话，合计 60~120 字）做【反驳或妥协】，必须 @点名至少一位其他专家，"
         f"并在你自己的职责标签内给出调整（财务：交通/住宿/预算；美食：餐饮；人文：景点游览；风光：景点游览/安全提示）；"
         f"第二轮要补充新地点/餐厅，不要重复 round1 已经说过的。",
         _SCRIPTED_ROUND2[p["id"]])
        for p in EXPERT_ORDER
    ]
    async for ev in _speak_all(round2_specs):
        yield ev

    # ---- 阶段：主持人整合 ----
    if _stop():
        yield {"type": "error", "data": {"error": "AI 助理服务已暂停"}}
        return
    yield {"type": "stage", "data": {"stage": "integrate", "label": "主持人整合方案"}}
    # 联网参考资料已在开场前统一搜索（search_refs / refs_block），此处复用，不再重复搜索
    integrate_prompt = (
        f"{task_ctx}\n讨论记录：\n{chr(10).join(transcript)}\n\n"
        f"{refs_block}"
        "请整合 3 套方案给用户挑选（A/B/C），按以下格式输出。\n\n"
        "【输出格式：先输出 markdown 版本（用户“听”的内容，3 方案完整 + 实用小贴士 + 互动问句），"
        "再用一个 ```json 代码块输出【方案 A 的 days 数组】给前端卡片化使用】\n\n"
        "Markdown 模板（务必照此结构）：\n"
        "🏛️ **方案**\n"
        "\n"
        "**方案 A：<风格名>**\n"
        "Day 1：地点1-地点2-**地点3**（需购票/预约/免费）。 Day 2：地点1-地点2-...-晚上地点。 Day 3：...-返程。\n"
        "\n"
        "**方案 B：<风格名>**\n"
        "Day 1：...。 Day 2：...。 Day 3：...。\n"
        "\n"
        "**方案 C：<风格名>**\n"
        "Day 1：...。 Day 2：...。 Day 3：...。\n"
        "\n"
        "---\n"
        "💡 **实用小贴士**\n"
        "- 交通：...\n"
        "- 预约：...\n"
        "- 美食：...\n"
        "[互动问句] 这三套方案中，哪一套的底层逻辑最契合您本次出行的核心诉求呢？\n\n"
        "JSON 块结构（仅方案 A 的 days，给前端 Day 卡）：\n"
        "```json\n"
        "{\n"
        '  "days": [\n'
        '    {"tag": "<方案A风格标签>", "title": "<主题>", "items": [\n'
        '      {"time": "上午", "text": "具体地点+活动（时长/门票）"}\n'
        "    ]}\n"
        "  ]\n"
        "}\n"
        "```\n"
        "【硬约束】\n"
        "- 价格/营业时间必须来自【联网参考资料】，没有的信息写「价格待核实」，严禁编造来源\n"
        "- 每个景点/活动后尽量标来源（公众号/景区官网/大众点评/高德/本地宝等）\n"
        "- 地点名加粗（**XX**）便于用户扫读\n"
        "- 总预算控制在 2000 元以内"
    )
    plan_md = await _llm_text(build_host_system(), integrate_prompt)
    if settings.use_mock_llm or not plan_md or not _is_plan_like(plan_md):
        # mock 模式直接走 _PLAN_TEMPLATE 兜底（mock LLM 返回短文本不带 3 方案结构）
        # 真实模式 LLM 失败时也走模板。模板内嵌 ```json 块含方案 A 的 days。
        plan_md = _PLAN_TEMPLATE
    # 代码层来源校验：与联网参考资料比对，无出处的「来源：X」一律替换为「价格待核实」
    plan_md = _sanitize_sources(plan_md, search_refs)

    # 结构化提取（主持人按 prompt 输出 ```json ... ``` 代码块）
    plan_data = _extract_plan_json(plan_md)
    # 若 LLM 未按 JSON 输出，回退从文本结构里再尝试一次（去掉 markdown 标记后剥 JSON）
    if plan_data is None:
        plan_data = _extract_plan_json(plan_md.replace("##", ""))
    # 若 LLM 输出了 JSON 但 markdown 仍是 LLM 原文（未按 JSON 生成 markdown），则用 data 重生 markdown
    # 但如果 plan_md 是 _PLAN_TEMPLATE（🏛️ 方案 ... 3 方案版），不要再用 data 覆盖
    if plan_data and (not plan_md.lstrip().startswith("##") or "行程概览" not in plan_md):
        if not plan_md.lstrip().startswith("🏛️"):
            plan_md = _plan_data_to_markdown(plan_data)
    # 若回退路径：plan_md 是 _PLAN_TEMPLATE，但同样补一份 data（前端用 _PLAN_TEMPLATE 兜底渲染 markdown）
    if plan_data is None:
        plan_data = _parse_template_to_data(plan_md, travelers, budget, days)

    # 团队讨论摘要（金句）
    quotes = []
    for p in EXPERT_ORDER:
        line = last_by.get(p["name"]) or _SCRIPTED_QUOTES[p["id"]]
        mm = moa_member(p["name"])
        quotes.append({
            "role_id": mm["id"], "name": mm["name"], "emoji": mm["emoji"],
            "color": mm["color"], "text": line,
        })

    # ---- 阶段：确认门（await_confirm，可多轮修订） ----
    revise_limit = 5
    while True:
        if _stop():
            yield {"type": "error", "data": {"error": "AI 助理服务已暂停"}}
            return
        yield {"type": "await_confirm", "data": {"plan": {"markdown": plan_md, "data": plan_data, "quotes": quotes}}}
        decision = (await user_input("请确认或提出修改意见")).strip()
        if is_confirm(decision):
            break
        if revise_limit <= 0:
            break
        revise_limit -= 1
        revise_prompt = (
            f"用户对你刚才的旅游规划提出了修改意见，请据此修订（保持原格式规范，不要编造信息）：\n\n"
            f"{decision}\n\n"
            f"{refs_block}——原有草案——\n{plan_md}"
        )
        revised = await _llm_text(build_host_system(), revise_prompt)
        if revised and _is_plan_like(revised):
            plan_md = _sanitize_sources(revised, search_refs)
        else:
            plan_md = plan_md + f"\n\n> 修订说明：{decision}（已记录，联网数据以实际为准）"

    # ---- 完成 ----
    yield {"type": "done", "data": {"plan": {"markdown": plan_md, "data": plan_data, "quotes": quotes}}}
