"""Auth router: register, login, demographics, consent, status."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User, UserStatus
from app.schemas.auth import (
    RegisterRequest, LoginRequest, EmailLoginRequest, DemographicsRequest,
    ConsentWithSurveyRequest,
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


# 年龄段 → 整数中位数（用于 User.age 兼容旧字段）
_AGE_RANGE_TO_INT = {
    "18-24": 21,
    "25-34": 30,
    "35-44": 40,
    "45-54": 50,
    "55-64": 60,
    "65+": 70,
}

# LLM 使用频率 → 旧字段 tech_frequency 映射
_FREQ_TO_TECH = {
    "never": "rarely",
    "rarely": "rarely",        # 不常使用（每月 1-2 次）
    "sometimes": "sometimes",  # 偶尔使用（每周 1-3 次）
    "often": "often",          # 频繁使用（每周 4-6 次）
    "daily": "daily",          # 几乎每天使用
}

# 是否使用过生成式 AI → 旧字段 ai_experience 映射
_AI_EXP = {
    "yes": "basic",            # 默认认为"使用过"=有基础经验
    "no": "none",
}


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new participant. Group assignment happens after consent."""
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    user = User(
        email=req.email,
        password_hash=hash_password(req.password) if req.password else None,
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

    # 无密码用户（免密注册）password_hash 为 None，需短路避免 verify_password 内 None 处理
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = create_user_token(str(user.id), user.group.value if user.group else None, user.status.value)
    return TokenResponse(access_token=token, user_id=str(user.id), status=user.status.value)


@router.post("/login-by-email", response_model=TokenResponse)
async def login_by_email(req: EmailLoginRequest, db: AsyncSession = Depends(get_db)):
    """邮箱直登：仅已注册邮箱即可登录（实验平台免密登录）。

    分组是否变化由前端比对 JWT 中的 group 与本地记录判断，
    若管理员改过分组，前端会再调用 /task/reset 让参与者重走流程。
    """
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="该邮箱未注册，请先注册")

    token = create_user_token(
        str(user.id),
        user.group.value if user.group else None,
        user.status.value,
    )
    return TokenResponse(access_token=token, user_id=str(user.id), status=user.status.value)


@router.post("/consent", response_model=TokenResponse)
async def sign_consent_with_survey(
    req: ConsentWithSurveyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """签署知情同意 + 提交前置问卷（10 题） → 触发分组（单盲）。

    - 校验 10 题答案已填齐
    - 将原始答案存到 users.pre_survey (JSONB)
    - 同时把人口学（性别/年龄/学历）+ AI 经验映射到旧字段（兼容旧统计/管理后台）
    - 状态机：REGISTERED → CONSENTED；分配实验分组（单盲）
    - 返回含新 group 的 JWT
    """
    if not req.agreed:
        raise HTTPException(status_code=400, detail="请先勾选「我已阅读并同意」")

    s = req.survey
    # 多选 q4 至少 1 项；若选"以上均不认同"则只允许单独选它
    if not s.q4 or (len(s.q4) > 1 and "none" in s.q4):
        raise HTTPException(status_code=400, detail="第 4 题选项无效（多选至少 1 项）")

    # 存原始 10 题答案
    user.pre_survey = {
        "q1_used_gen_ai": s.q1,
        "q2_travel_experience": s.q2,
        "q3_llm_frequency_6m": s.q3,
        "q4_agent_awareness": s.q4,
        "q5_llm_duration": s.q5,
        "q6_gender": s.q6,
        "q7_age_range": s.q7,
        "q8_education": s.q8,
        "q9_marital": s.q9,
        "q10_occupation": s.q10,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    # 映射到旧字段（向后兼容：管理后台/统计脚本可能仍读这些列）
    user.gender = s.q6
    user.age = _AGE_RANGE_TO_INT.get(s.q7)
    user.education = s.q8
    user.tech_frequency = _FREQ_TO_TECH.get(s.q3, s.q3)
    user.ai_experience = _AI_EXP.get(s.q1, s.q1)

    # 状态机迁移 + 分组
    user = await transition_status(db, user, UserStatus.CONSENTED)
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
    """Update demographic info (age, gender, education, etc.).

    保留旧端点供管理后台/数据回填使用；新用户走 /consent。
    """
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
        pre_survey=user.pre_survey,
    )


@router.post("/admin/login", response_model=AdminTokenResponse)
async def admin_login(req: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    """Admin login."""
    from app.models.admin_user import AdminUser
    result = await db.execute(select(AdminUser).where(AdminUser.username == req.username))
    admin = result.scalar_one_or_none()

    if not admin or not admin.password_hash or not verify_password(req.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="管理员账号或密码错误")

    token = create_admin_token(admin.username)
    return AdminTokenResponse(access_token=token, username=admin.username)
