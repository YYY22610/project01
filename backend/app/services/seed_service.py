"""Seed service: insert initial data on first startup."""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.admin_user import AdminUser
from app.models.system_config import SystemConfig
from app.models.questionnaire import QuestionnaireItem, QuestionConstruct, QuestionType
from app.services.auth_service import hash_password
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_CONFIGS = [
    ("task_days", "3", "旅行天数"),
    ("task_budget", "1000", "旅行预算(元)"),
    ("target_email", "experiment@example.com", "收件邮箱"),
    ("destination", "杭州", "目的地"),
    ("target_sample_size", "100", "目标样本量"),
    ("experiment_active", "true", "实验是否开启"),
    ("block_size", "6", "区组大小"),
    ("agent_service_paused", "false", "AI助理服务是否暂停"),
]

# 问卷题项说明：
# - 元组结构: (构念, 题干, 题型, 量表级数, 排序, 选项, 适用分组)
# - 适用分组: "ALL"=所有人; "SOA,MOA"=仅 AI 助理组; "H"=仅纯人工组
# - 单盲设计：H 组题项改写为"工具/方法"评价，SOA/MOA 组保留 AI 助理表述；
#   task_load 与 manipulation_check 为各组共用。
DEFAULT_QUESTIONS = [
    # ===== 共用：任务负荷 (NASA-TLX) =====
    (QuestionConstruct.TASK_LOAD, "完成旅行规划任务让我感到脑力负荷很大", QuestionType.likert, 7, 1, None, "ALL"),
    (QuestionConstruct.TASK_LOAD, "我需要在多个工具/步骤之间频繁切换，增加了我的负担", QuestionType.likert, 7, 2, None, "ALL"),
    (QuestionConstruct.TASK_LOAD, "整体而言，完成本次任务所需的努力程度很高", QuestionType.likert, 7, 3, None, "ALL"),

    # ===== 感知信任 trust =====
    (QuestionConstruct.TRUST, "我信任AI助理为我生成的行程规划建议", QuestionType.likert, 5, 4, None, "SOA,MOA"),
    (QuestionConstruct.TRUST, "我认为AI助理提供的旅行信息（如景点、路线）是可靠的", QuestionType.likert, 5, 5, None, "SOA,MOA"),
    (QuestionConstruct.TRUST, "我在使用AI助理的过程中，感到我的操作与数据是安全、可控的", QuestionType.likert, 5, 6, None, "SOA,MOA"),
    (QuestionConstruct.TRUST, "我信任本次任务所用工具/方法为我生成的行程规划建议", QuestionType.likert, 5, 4, None, "H"),
    (QuestionConstruct.TRUST, "我认为通过工具/方法获得的旅行信息（如景点、路线）是可靠的", QuestionType.likert, 5, 5, None, "H"),
    (QuestionConstruct.TRUST, "我在使用工具/方法的过程中，感到我的操作与数据是安全、可控的", QuestionType.likert, 5, 6, None, "H"),

    # ===== 感知自主性 autonomy =====
    (QuestionConstruct.AUTONOMY, "我能自主决定如何完成任务，而非被AI助理主导", QuestionType.likert, 5, 7, None, "SOA,MOA"),
    (QuestionConstruct.AUTONOMY, "在整个任务过程中，我对进度有充分的掌控", QuestionType.likert, 5, 8, None, "SOA,MOA"),
    (QuestionConstruct.AUTONOMY, "我可以根据自己的想法随时调整完成任务的方式", QuestionType.likert, 5, 9, None, "SOA,MOA"),
    (QuestionConstruct.AUTONOMY, "我能自主决定如何完成任务，而非被工具/方法主导", QuestionType.likert, 5, 7, None, "H"),
    (QuestionConstruct.AUTONOMY, "在整个任务过程中，我对进度有充分的掌控", QuestionType.likert, 5, 8, None, "H"),
    (QuestionConstruct.AUTONOMY, "我可以根据自己的想法随时调整完成任务的方式", QuestionType.likert, 5, 9, None, "H"),

    # ===== 满意度 satisfaction =====
    (QuestionConstruct.SATISFACTION, "我对完成旅行规划任务的整体体验感到满意", QuestionType.likert, 5, 10, None, "SOA,MOA"),
    (QuestionConstruct.SATISFACTION, "我满意AI助理在任务中提供的支持与响应质量", QuestionType.likert, 5, 11, None, "SOA,MOA"),
    (QuestionConstruct.SATISFACTION, "我对完成旅行规划任务的整体体验感到满意", QuestionType.likert, 5, 10, None, "H"),
    (QuestionConstruct.SATISFACTION, "我满意完成任务过程中工具/方法所提供的支持质量", QuestionType.likert, 5, 11, None, "H"),

    # ===== 未来使用意愿 future_use =====
    (QuestionConstruct.FUTURE_USE, "如果未来有类似的任务，我愿意继续使用AI助理", QuestionType.likert, 5, 12, None, "SOA,MOA"),
    (QuestionConstruct.FUTURE_USE, "我会向他人推荐用AI助理做旅行规划", QuestionType.likert, 5, 13, None, "SOA,MOA"),
    (QuestionConstruct.FUTURE_USE, "如果未来有类似的任务，我愿意继续使用本工具/方法", QuestionType.likert, 5, 12, None, "H"),
    (QuestionConstruct.FUTURE_USE, "我会向他人推荐用本工具/方法做旅行规划", QuestionType.likert, 5, 13, None, "H"),

    # ===== 共用：操纵检验 =====
    (QuestionConstruct.MANIPULATION_CHECK, "在本次任务中，你是否使用了AI助理来协助完成旅行规划？", QuestionType.choice, 0, 14, ["是", "否", "不确定"], "ALL"),
    (QuestionConstruct.MANIPULATION_CHECK, "你认为本次任务中为你提供辅助的AI助理数量是？", QuestionType.choice, 0, 15, ["0个（纯人工）", "1个", "多个"], "ALL"),
]


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

        # 3. Questionnaire items
        result = await db.execute(select(QuestionnaireItem).limit(1))
        if result.scalar_one_or_none() is None:
            for construct, text, q_type, scale, order, options, groups in DEFAULT_QUESTIONS:
                db.add(QuestionnaireItem(
                    construct=construct,
                    question_text=text,
                    question_type=q_type,
                    scale_level=scale,
                    options=options,
                    sort_order=order,
                    applicable_groups=groups,
                ))
            logger.info("Seeded questionnaire items")

        await db.commit()
        logger.info("Seed data inserted successfully")
