"""Questionnaire router: get items, submit responses."""
from fastapi import APIRouter, Depends, HTTPException, Query
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


def item_applies_to_group(item: QuestionnaireItem, group_val: str | None) -> bool:
    """Whether an item is shown to a participant in the given experiment group.

    2026-10-14 questionnaire: every item is written with applicable_groups = "ALL"
    because the instrument now handles the control condition through instruction
    text rather than group-specific rewording. The field is kept so the admin
    backend can still filter by group if rewording is ever restored.
    """
    ag = item.applicable_groups
    if not ag or ag.strip().upper() == "ALL":
        return True
    return group_val in [g.strip() for g in ag.split(",") if g.strip()]


@router.get("/items", response_model=list[QuestionnaireItemResponse])
async def get_questionnaire_items(
    phase: str = Query("post", pattern="^(pre|post)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get active questionnaire items for a stage, filtered by the participant's group.

    `phase=pre` is used by the consent page (before consent, when the user has no
    group yet — hence applicable_groups must be "ALL" for pre items), `phase=post`
    by the questionnaire page after the task completes.
    """
    result = await db.execute(
        select(QuestionnaireItem)
        .where(
            QuestionnaireItem.is_active == True,
            QuestionnaireItem.phase == phase,
        )
        .order_by(QuestionnaireItem.sort_order)
    )
    all_items = result.scalars().all()

    group_val = user.group.value if user.group else None
    items = [item for item in all_items if item_applies_to_group(item, group_val)]

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
            phase=item.phase,
            is_reverse=bool(item.is_reverse),
            section_note=item.section_note,
        )
        for item in items
    ]


async def write_responses(
    db: AsyncSession,
    user: User,
    responses: list[dict],
    expected_phase: str,
) -> list[tuple[QuestionnaireItem, str]]:
    """Persist questionnaire answers, validating that items belong to `expected_phase`.

    Returns a list of (item, response_value) pairs — callers that need the item
    metadata (e.g. the consent endpoint mapping demographics onto legacy User
    columns by sort_order) use the return value instead of re-querying.
    Raises 400 on unknown items, items from the wrong phase, or duplicate item_ids.
    """
    item_ids = [str(r["item_id"]) for r in responses]
    if len(set(item_ids)) != len(item_ids):
        raise HTTPException(status_code=400, detail="提交的题目存在重复")

    items = (
        (await db.execute(
            select(QuestionnaireItem).where(QuestionnaireItem.id.in_(item_ids))
        )).scalars().all()
    )
    by_id = {str(item.id): item for item in items}
    missing = set(item_ids) - set(by_id)
    if missing:
        raise HTTPException(status_code=400, detail=f"题目不存在: {sorted(missing)[:5]}")

    wrong_phase = [i for i in by_id.values() if i.phase != expected_phase]
    if wrong_phase:
        raise HTTPException(status_code=400, detail="题目不属于当前问卷阶段")

    written: list[tuple[QuestionnaireItem, str]] = []
    for r in responses:
        item = by_id[str(r["item_id"])]
        value = str(r["response_value"])
        db.add(QuestionnaireResponse(
            user_id=user.id,
            item_id=r["item_id"],
            response_value=value,
        ))
        written.append((item, value))
    return written


@router.post("/submit", response_model=QuestionnaireSubmitResponse)
async def submit_questionnaire(
    req: QuestionnaireSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit the post-task questionnaire (phase=post) and complete the experiment."""
    if user.status != UserStatus.TASK_COMPLETED:
        raise HTTPException(status_code=400, detail="请先完成任务")

    written = await write_responses(db, user, req.responses, expected_phase="post")

    user = await transition_status(db, user, UserStatus.QUESTIONNAIRE_COMPLETED)
    await db.commit()

    return QuestionnaireSubmitResponse(submitted=True, response_count=len(written))
