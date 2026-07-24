"""Questionnaire router: get items, submit responses."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User, UserStatus
from app.models.questionnaire import QuestionnaireItem, QuestionnaireResponse
from app.schemas.questionnaire import (
    QuestionnaireItemResponse,
    QuestionnaireSubmitRequest,
    QuestionnaireSubmitResponse,
)
from app.services.state_machine import transition_status

router = APIRouter()


@router.get("/items", response_model=list[QuestionnaireItemResponse])
async def get_questionnaire_items(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get active questionnaire items applicable to the current user's group.

    Single-blind: items are filtered by the participant's assigned group so that
    H (pure-human) sees tool/method-worded questions while SOA/MOA see AI-assistant
    wording. Items with NULL / "ALL" applicable_groups are shown to everyone.
    """
    result = await db.execute(
        select(QuestionnaireItem)
        .where(QuestionnaireItem.is_active == True)
        .order_by(QuestionnaireItem.sort_order)
    )
    all_items = result.scalars().all()

    group_val = user.group.value if user.group else None

    def _applies(item: QuestionnaireItem) -> bool:
        ag = item.applicable_groups
        if not ag or ag.strip().upper() == "ALL":
            return True
        return group_val in [g.strip() for g in ag.split(",") if g.strip()]

    items = [item for item in all_items if _applies(item)]

    return [
        QuestionnaireItemResponse(
            id=str(item.id),
            construct=item.construct,
            question_text=item.question_text,
            question_type=item.question_type.value,
            options=item.options,
            scale_level=item.scale_level,
            sort_order=item.sort_order,
            applicable_groups=item.applicable_groups,
        )
        for item in items
    ]


@router.post("/submit", response_model=QuestionnaireSubmitResponse)
async def submit_questionnaire(
    req: QuestionnaireSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit questionnaire responses and complete the experiment."""
    if user.status != UserStatus.TASK_COMPLETED:
        raise HTTPException(status_code=400, detail="请先完成任务")

    for resp in req.responses:
        qr = QuestionnaireResponse(
            user_id=user.id,
            item_id=resp["item_id"],
            response_value=str(resp["response_value"]),
        )
        db.add(qr)

    user = await transition_status(db, user, UserStatus.QUESTIONNAIRE_COMPLETED)
    await db.commit()

    return QuestionnaireSubmitResponse(submitted=True, response_count=len(req.responses))
