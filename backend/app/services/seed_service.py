"""Seed service: insert initial data on first startup."""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.admin_user import AdminUser
from app.models.system_config import SystemConfig
from app.models.questionnaire import (
    QuestionnaireItem,
    QuestionConstruct as C,
    QuestionPhase as P,
    QuestionType as T,
)
from app.services.auth_service import hash_password
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_CONFIGS = [
    ("task_days", "3", "旅行天数"),
    ("task_budget", "2000", "旅行预算(元)"),
    ("task_travelers", "1 人", "出行人数"),
    ("target_email", "experiment@example.com", "收件邮箱"),
    ("destination", "杭州", "目的地"),
    ("target_sample_size", "100", "目标样本量"),
    ("experiment_active", "true", "实验是否开启"),
    ("block_size", "6", "区组大小"),
    ("agent_service_paused", "false", "AI助理服务是否暂停"),
]


# =============================================================================
# 问卷题项定义 —— 依据《附件5 实验阶段问卷》(2026-10-14)
#
# 结构：
#   - tuple: (构念, 题干, 题型, 量表级数, 选项, 阶段, 反向计分, 指导语, 排序)
#   - 选项 None 表示普通李克特量表；双极量表（情绪体验）用 dict 存左右锚点
#   - 指导语只在题组第一题上写一次，前端渲染为题干上方的提示段落
#   - applicable_groups 一律 "ALL"：新问卷靠指导语处理未使用助理的被试，
#     不再为 H 组改写措辞（详见 database/migrate_questionnaire_v2.sql 注释）
#
# ⚠️ 前置问卷的 sort_order 被 backend/app/routers/auth.py 的
#    PRE_ORDER_* 常量引用（人口学 → users 旧列映射）。重排前置问卷必须同步改。
# =============================================================================

# 前置问卷 Q11~Q16 之前的指导语
_PRE_NOTE = (
    "以下题目测量您对“智能体助理用于旅游规划”的一般看法，请根据您目前的真实态度作答"
    "（1=非常不同意，2=不同意，3=不确定，4=同意，5=非常同意）。"
)

# 后置问卷 Q23~Q45 之前的指导语
_POST_NOTE = (
    "以下题目请结合本次旅游规划任务中的体验作答（未使用智能体助理的被试，"
    "请结合本次任务的整体感受与对使用智能体助理的预期作答）。"
    "1=非常不同意，2=不同意，3=不确定，4=同意，5=非常同意。"
)

# 情绪体验（Q41~Q45）题组指导语
_AFFECT_NOTE = (
    "完成本次旅游规划任务后，请选择您当前的感受"
    "（每题 1–5 分，1=最接近左端词，5=最接近右端词；"
    "未使用智能体助理的被试，请按对“使用智能体助理做旅游规划”的预期感受作答）："
)

PRE_QUESTIONS = [
    # ===== 人口统计 Q01~Q05 =====
    (C.DEMOGRAPHIC, "您的性别", T.choice, 0, ["男", "女"], False, None, 1),
    (C.DEMOGRAPHIC, "您的年龄", T.choice, 0,
     ["18–25 岁", "26–30 岁", "31–40 岁", "41–50 岁", "50 岁以上"], False, None, 2),
    (C.DEMOGRAPHIC, "您的最高学历", T.choice, 0,
     ["高中及以下", "大专", "本科", "硕士及以上"], False, None, 3),
    (C.DEMOGRAPHIC, "您的婚姻状况", T.choice, 0, ["未婚", "已婚"], False, None, 4),
    (C.DEMOGRAPHIC, "您目前从事的职业", T.choice, 0,
     ["学生", "企事业单位职员", "自由职业", "其他"], False, None, 5),

    # ===== AI 使用经验 Q06~Q09 =====
    (C.AI_EXPERIENCE,
     "您是否使用过生成式人工智能（如 ChatGPT、DeepSeek、豆包、千问、Kimi 等）？",
     T.choice, 0, ["是", "否"], False, None, 6),
    (C.AI_EXPERIENCE, "您是否具备国内外旅行经验？", T.choice, 0,
     ["无", "仅国内", "国内外均有"], False, None, 7),
    (C.AI_EXPERIENCE, "在过去 6 个月中，您使用大语言模型的频率是？", T.choice, 0,
     ["从不", "很少", "偶尔", "经常", "高频"], False, None, 8),
    (C.AI_EXPERIENCE, "您使用大语言模型的时长大约是？", T.choice, 0,
     ["少于 1 个月", "1–6 个月", "6–12 个月", "1 年以上"], False, None, 9),

    # ===== 智能体认知（多选）Q10 =====
    (C.AGENT_AWARENESS, "关于 AI 智能体，下列说法您认同哪些？（多选）", T.multiple, 0, [
        "我了解人工智能智能体（AI Agent）的基本工作原理",
        "我了解或听说过 OpenClaw、ArkClaw 等“龙虾”系列 AI 智能体",
        "我尝试过在智能体平台搭建智能体（Dify、Coze、Zapier、n8n 等）",
        "我尝试过部署或配置智能体助理（如 OpenClaw、飞书 x claw、腾讯 QClaw、字节 ArkClaw 等）",
        "我认为智能体助理能够辅助完成旅游规划类任务",
        "以上均不认同",
    ], False, None, 10),

    # ===== 社会影响 Q11~Q16（5 点李克特）=====
    (C.SOCIAL_INFLUENCE,
     "在我的社交圈（如朋友、家人和同事）中使用智能体助理做旅游规划反映了身份象征。",
     T.likert, 5, None, False, _PRE_NOTE, 11),
    (C.SOCIAL_INFLUENCE, "影响我行为的人不希望我使用智能体助理做旅游规划。",
     T.likert, 5, None, True, None, 12),  # 反向计分
    (C.SOCIAL_INFLUENCE,
     "在我的社交圈中，使用智能体助理做旅游规划的人比不使用的人更有声望。",
     T.likert, 5, None, False, None, 13),
    (C.SOCIAL_INFLUENCE, "我所重视其意见的人会更倾向于让我使用智能体助理做旅游规划。",
     T.likert, 5, None, False, None, 14),
    (C.SOCIAL_INFLUENCE, "对我重要的人会鼓励我使用智能体助理做旅游规划。",
     T.likert, 5, None, False, None, 15),
    (C.SOCIAL_INFLUENCE, "在我的社交圈中，使用智能体助理做旅游规划的人具有较高的形象。",
     T.likert, 5, None, False, None, 16),

    # ===== 感知拟人化 Q17~Q20（5 点李克特）=====
    (C.ANTHROPOMORPHISM, "智能体助理有自己的思想。", T.likert, 5, None, False, None, 17),
    (C.ANTHROPOMORPHISM, "智能体助理是有意识的。", T.likert, 5, None, False, None, 18),
    (C.ANTHROPOMORPHISM, "智能体助理会体验情感。", T.likert, 5, None, False, None, 19),
    (C.ANTHROPOMORPHISM, "智能体助理没有自己的自由意志。",
     T.likert, 5, None, True, None, 20),  # 反向计分
]

POST_QUESTIONS = [
    # ===== 操纵检验 / 参与感知 Q21~Q22 =====
    (C.MANIPULATION_CHECK, "在本次任务中，为您提供协助的智能体助理数量是：", T.choice, 0,
     ["0 个", "1 个", "2–3 个", "更多"], False, None, 21),
    (C.MANIPULATION_CHECK, "您认为本次行程规划结果在多大程度上由 AI 完成？", T.choice, 0,
     ["完全人工", "以人工为主", "各半", "以 AI 为主", "完全由 AI"], False, None, 22),

    # ===== 享乐动机 Q23~Q27 =====
    (C.HEDONIC_MOTIVATION, "我与智能体助理交互进行旅游规划很有趣。",
     T.likert, 5, None, False, _POST_NOTE, 23),
    (C.HEDONIC_MOTIVATION, "使用智能体助理做旅游规划很娱乐。", T.likert, 5, None, False, None, 24),
    (C.HEDONIC_MOTIVATION, "使用智能体助理做旅游规划很无趣。",
     T.likert, 5, None, True, None, 25),  # 反向计分
    (C.HEDONIC_MOTIVATION, "与智能体助理进行旅游规划交互是愉快的。",
     T.likert, 5, None, False, None, 26),
    (C.HEDONIC_MOTIVATION, "实际的旅游规划交互过程是愉悦的。", T.likert, 5, None, False, None, 27),

    # ===== 绩效期望 Q28~Q31 =====
    (C.PERFORMANCE_EXPECTANCY, "智能体助理比人类做旅游规划更准确。", T.likert, 5, None, False, None, 28),
    (C.PERFORMANCE_EXPECTANCY, "智能体助理在做旅游规划时更准确，人为错误更少。",
     T.likert, 5, None, False, None, 29),
    (C.PERFORMANCE_EXPECTANCY, "智能体助理提供的旅游规划服务比人类更稳定。",
     T.likert, 5, None, False, None, 30),
    (C.PERFORMANCE_EXPECTANCY, "智能体助理提供的旅游规划信息更加一致。",
     T.likert, 5, None, False, None, 31),

    # ===== 努力期望 Q32~Q35 =====
    (C.EFFORT_EXPECTANCY, "学习使用智能体助理做旅游规划对我来说很简单。",
     T.likert, 5, None, False, None, 32),
    (C.EFFORT_EXPECTANCY, "我与智能体助理的旅游规划交互是清晰且可理解的。",
     T.likert, 5, None, False, None, 33),
    (C.EFFORT_EXPECTANCY, "我发现使用智能体助理做旅游规划很容易。", T.likert, 5, None, False, None, 34),
    (C.EFFORT_EXPECTANCY, "我会轻易熟练使用智能体助理做旅游规划。", T.likert, 5, None, False, None, 35),

    # ===== 感知风险 Q36~Q40 =====
    (C.PERCEIVED_RISK, "我担心使用智能体助理进行旅游规划获取的信息可能存在质量问题。",
     T.likert, 5, None, False, None, 36),
    (C.PERCEIVED_RISK, "我担心使用智能体助理进行旅游规划可能导致研究想法和行程数据泄露。",
     T.likert, 5, None, False, None, 37),
    (C.PERCEIVED_RISK, "我担心使用智能体助理提供旅游规划信息可能引起侵权问题。",
     T.likert, 5, None, False, None, 38),
    (C.PERCEIVED_RISK, "我担心使用智能体助理进行旅游规划时的数据安全问题。",
     T.likert, 5, None, False, None, 39),
    (C.PERCEIVED_RISK, "我担心使用智能体助理进行旅游规划会剥夺我独立规划行程的机会。",
     T.likert, 5, None, False, None, 40),

    # ===== 情绪体验 Q41~Q45（双极 5 点：1=最接近左端词，5=最接近右端词）=====
    (C.AFFECTIVE_EXPERIENCE, "忧郁 —— 1 —— 2 —— 3 —— 4 —— 5 —— 满足",
     T.likert, 5, {"left": "忧郁", "right": "满足"}, False, _AFFECT_NOTE, 41),
    (C.AFFECTIVE_EXPERIENCE, "无聊 —— 1 —— 2 —— 3 —— 4 —— 5 —— 放松",
     T.likert, 5, {"left": "无聊", "right": "放松"}, False, None, 42),
    (C.AFFECTIVE_EXPERIENCE, "绝望 —— 1 —— 2 —— 3 —— 4 —— 5 —— 充满希望",
     T.likert, 5, {"left": "绝望", "right": "充满希望"}, False, None, 43),
    (C.AFFECTIVE_EXPERIENCE, "很不满意 —— 1 —— 2 —— 3 —— 4 —— 5 —— 很满意",
     T.likert, 5, {"left": "很不满意", "right": "很满意"}, False, None, 44),
    (C.AFFECTIVE_EXPERIENCE, "恼火 —— 1 —— 2 —— 3 —— 4 —— 5 —— 愉悦",
     T.likert, 5, {"left": "恼火", "right": "愉悦"}, False, None, 45),

    # ===== 接受意愿 Q46~Q48 =====
    (C.ACCEPTANCE_INTENTION, "我愿意接受智能体助理提供的旅游规划意见。",
     T.likert, 5, None, False, None, 46),
    (C.ACCEPTANCE_INTENTION, "我会乐于与智能体助理交互进行旅游规划。",
     T.likert, 5, None, False, None, 47),
    (C.ACCEPTANCE_INTENTION, "我可能会使用智能体助理进行旅游规划。",
     T.likert, 5, None, False, None, 48),

    # ===== 拒绝意愿 Q49~Q53 =====
    (C.RESISTANCE_INTENTION, "在旅游规划中，智能体助理处理信息的方式让我感觉缺乏人情味。",
     T.likert, 5, None, False, None, 49),
    (C.RESISTANCE_INTENTION, "即使智能体助理还存在不足，我也只能将就使用。",
     T.likert, 5, None, False, None, 50),
    (C.RESISTANCE_INTENTION, "我对在文旅决策中使用智能体助理持观望态度，暂不深入使用。",
     T.likert, 5, None, False, None, 51),
    (C.RESISTANCE_INTENTION, "完成这次旅游规划后，我不打算继续使用智能体助理。",
     T.likert, 5, None, False, None, 52),
    (C.RESISTANCE_INTENTION, "与依赖智能体助理相比，我更愿意自己独立完成旅游规划。",
     T.likert, 5, None, False, None, 53),

    # ===== 开放题 Q54 =====
    (C.OPEN_FEEDBACK, "关于本次旅游规划任务或智能体助理，您还有什么想说的？",
     T.text, 0, None, False, None, 54),
]

DEFAULT_QUESTIONS = PRE_QUESTIONS + POST_QUESTIONS


async def seed_initial_data():
    """Seed default admin, system configs, and questionnaire items."""
    async with async_session_factory() as db:
        # 1. Admin user
        result = await db.execute(select(AdminUser).where(AdminUser.username == settings.ADMIN_USERNAME))
        if result.scalar_one_or_none() is None:
            admin = AdminUser(
                username=settings.ADMIN_USERNAME,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
            )
            db.add(admin)
            logger.info("Seeded default admin user")

        # 2. System configs
        for key, value, desc in DEFAULT_CONFIGS:
            result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
            if result.scalar_one_or_none() is None:
                db.add(SystemConfig(key=key, value=value, description=desc))
        logger.info("Seeded system configs")

        # 3. Questionnaire items — only when the table is empty (idempotent guard).
        #    After changing PRE_QUESTIONS/POST_QUESTIONS you must clear
        #    questionnaire_items (responses cascade-delete) for the new set to load.
        result = await db.execute(select(QuestionnaireItem).limit(1))
        if result.scalar_one_or_none() is None:
            def _add(rows, phase):
                for construct, text, q_type, scale, options, is_reverse, note, order in rows:
                    db.add(QuestionnaireItem(
                        construct=construct,
                        question_text=text,
                        question_type=q_type,
                        scale_level=scale,
                        options=options,
                        sort_order=order,
                        applicable_groups="ALL",
                        phase=phase,
                        is_reverse=is_reverse,
                        section_note=note,
                    ))

            _add(PRE_QUESTIONS, P.PRE)
            _add(POST_QUESTIONS, P.POST)
            logger.info("Seeded questionnaire items: %d pre + %d post",
                        len(PRE_QUESTIONS), len(POST_QUESTIONS))

        await db.commit()
        logger.info("Seed data inserted successfully")
