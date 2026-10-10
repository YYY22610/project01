"""Pydantic schemas for questionnaire."""
import warnings

from pydantic import BaseModel
from typing import Optional, Any


# `construct` 是问卷的研究构念，对应数据库 questionnaire_items.construct 列、
# 前端 types/index.ts 的 construct 字段与 constructLabel 映射，属于对外 API 契约，
# 不能改名（改名需同步 DB 列 + 前端 + 全部调用点）。
#
# 它与 pydantic.BaseModel 的内置方法 construct() 同名，Pydantic 在建类时会对每个
# 此类字段发 UserWarning（源码 _fields.py 中硬编码的 warnings.warn，无配置项可关）。
# 改用 Python 属性名 construct_ + alias 虽能消除告警，但 pydantic 默认序列化不走
# by_alias，会把响应里的 construct 变成 construct_ 而破坏前端契约，
# 需要给所有 schema 全局补 by_alias=True，收益不足以抵消风险，故保留字段名、
# 就地精确过滤这一条告警（不用 module="pydantic" 全局过滤，避免掩盖其他真实告警）。
warnings.filterwarnings(
    "ignore",
    message=r'Field name "construct" .*',
    category=UserWarning,
)


class QuestionnaireItemResponse(BaseModel):
    id: str
    construct: str
    question_text: str
    question_type: str
    options: Optional[Any] = None
    scale_level: int
    sort_order: int
    applicable_groups: Optional[str] = None


class QuestionnaireSubmitRequest(BaseModel):
    responses: list[dict]  # [{"item_id": "...", "response_value": "4"}]


class QuestionnaireSubmitResponse(BaseModel):
    submitted: bool
    response_count: int


class QuestionnaireItemCreate(BaseModel):
    construct: str
    question_text: str
    question_type: str = "likert"
    options: Optional[Any] = None
    scale_level: int = 5
    sort_order: int = 0


# Admin CRUD schemas — frontend uses simplified field names
class QuestionnaireItemAdminCreate(BaseModel):
    construct: str
    text: str
    type: str
    options: Optional[Any] = None
    scale_level: int = 5
    sort_order: int = 0
    is_active: bool = True
    applicable_groups: Optional[str] = "ALL"


class QuestionnaireItemAdminUpdate(BaseModel):
    construct: Optional[str] = None
    text: Optional[str] = None
    type: Optional[str] = None
    options: Optional[Any] = None
    scale_level: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    applicable_groups: Optional[str] = None
