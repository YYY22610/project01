"""State machine service — controls user experiment flow."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserStatus


VALID_TRANSITIONS = {
    UserStatus.REGISTERED: {UserStatus.CONSENTED},
    UserStatus.CONSENTED: {UserStatus.DEMO_COMPLETED},
    UserStatus.DEMO_COMPLETED: {UserStatus.TASK_IN_PROGRESS},
    UserStatus.TASK_IN_PROGRESS: {UserStatus.TASK_COMPLETED},
    UserStatus.TASK_COMPLETED: {UserStatus.QUESTIONNAIRE_COMPLETED},
}


async def transition_status(db: AsyncSession, user: User, new_status: UserStatus) -> User:
    """
    Transition user to a new status if the transition is valid.
    Raises ValueError if the transition is not allowed.
    """
    current = UserStatus(user.status)
    if new_status not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid status transition: {current.value} -> {new_status.value}")

    user.status = new_status
    await db.flush()
    return user


async def get_next_allowed_statuses(user: User) -> list[str]:
    """Get the list of statuses the user can transition to."""
    current = UserStatus(user.status)
    return [s.value for s in VALID_TRANSITIONS.get(current, set())]
