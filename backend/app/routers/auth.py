"""Auth router: register, login, demographics, consent, status."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User, UserStatus
from app.schemas.auth import (
    RegisterRequest, LoginRequest, DemographicsRequest,
    TokenResponse, UserResponse,
    AdminLoginRequest, AdminTokenResponse,
)
from app.services.auth_service import (
    hash_password, verify_password,
    create_user_token, create_admin_token, decode_access_token,
)
from app.services.group_service import assign_group
from app.services.state_machine import transition_status
from app.config import settings

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new participant. Group assignment happens after consent."""
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        status=UserStatus.REGISTERED,
    )
    db.add(user)
    await db.flush()

    token = create_user_token(str(user.id), None, user.status.value)
    await db.commit()
    return TokenResponse(access_token=token, user_id=str(user.id), status=user.status.value)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email + password."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = create_user_token(str(user.id), user.group.value if user.group else None, user.status.value)
    return TokenResponse(access_token=token, user_id=str(user.id), status=user.status.value)


@router.post("/consent", response_model=TokenResponse)
async def sign_consent(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Sign informed consent — triggers group assignment (single-blind).

    Returns a fresh JWT that includes the newly assigned group so the
    frontend can render group-specific UI (e.g. the AI assistant panel)
    without exposing the group name in the user profile response.
    """
    user = await transition_status(db, user, UserStatus.CONSENTED)

    # Assign group after consent
    group = await assign_group(db, user)
    user.group = group
    await db.flush()
    await db.commit()

    token = create_user_token(
        str(user.id),
        user.group.value if user.group else None,
        user.status.value,
    )
    return TokenResponse(access_token=token, user_id=str(user.id), status=user.status.value)


@router.post("/demographics", response_model=UserResponse)
async def update_demographics(
    req: DemographicsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update demographic info (age, gender, education, etc.)."""
    user.age = req.age
    user.gender = req.gender
    user.education = req.education
    user.tech_frequency = req.tech_frequency
    user.ai_experience = req.ai_experience
    await db.commit()
    return UserResponse(
        id=str(user.id), email=user.email, status=user.status.value,
        age=user.age, gender=user.gender, education=user.education,
        tech_frequency=user.tech_frequency, ai_experience=user.ai_experience,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user info (no group info exposed — single-blind)."""
    return UserResponse(
        id=str(user.id), email=user.email, status=user.status.value,
        age=user.age, gender=user.gender, education=user.education,
        tech_frequency=user.tech_frequency, ai_experience=user.ai_experience,
    )


@router.post("/admin/login", response_model=AdminTokenResponse)
async def admin_login(req: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    """Admin login."""
    from app.models.admin_user import AdminUser
    result = await db.execute(select(AdminUser).where(AdminUser.username == req.username))
    admin = result.scalar_one_or_none()

    if not admin or not verify_password(req.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="管理员账号或密码错误")

    token = create_admin_token(admin.username)
    return AdminTokenResponse(access_token=token, username=admin.username)
