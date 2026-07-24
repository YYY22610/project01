"""Import all models so SQLAlchemy can register them on Base.metadata."""
from app.models.user import User, ExperimentGroup, UserStatus
from app.models.behavior_log import BehaviorLog, ActionType
from app.models.task_submission import TaskSubmission
from app.models.chat_message import ChatMessage
from app.models.questionnaire import QuestionnaireItem, QuestionnaireResponse, QuestionConstruct, QuestionType
from app.models.admin_score import AdminScore
from app.models.reminder import Reminder
from app.models.system_config import SystemConfig
from app.models.admin_user import AdminUser

# Collect all model classes for easy import
all_models = [
    User,
    BehaviorLog,
    TaskSubmission,
    ChatMessage,
    QuestionnaireItem,
    QuestionnaireResponse,
    AdminScore,
    Reminder,
    SystemConfig,
    AdminUser,
]

__all__ = [m.__name__ for m in all_models] + ["all_models"]
