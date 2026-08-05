"""Pydantic schemas for questionnaire."""
from pydantic import BaseModel
from typing import Optional, Any


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
