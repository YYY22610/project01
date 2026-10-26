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


# 前置问卷（phase=pre）的 sort_order 布局 —— 与 seed_service.PRE_QUESTIONS 严格对应。
# 用 sort_order（而非 construct）定位人口学题，是因为 Q01~Q05 同属 demographic
# 构念、需要合并成一个表头显示，若按构念定位会互相覆盖。
# ⚠️ 若在管理后台重排前置问卷顺序，需同步修改这三个常量。
PRE_ORDER_GENDER = 1      # Q01 您的性别
PRE_ORDER_AGE = 2         # Q02 您的年龄
PRE_ORDER_EDUCATION = 3   # Q03 您的最高学历
PRE_ORDER_GENAI = 6       # Q06 是否使用过生成式人工智能
PRE_ORDER_LLM_FREQ = 8    # Q08 过去 6 个月使用大语言模型的频率

# 年龄段 → 整数中位数（用于 User.age 兼容旧导出列）
_AGE_VALUES = {
    "18–25 岁": 21,
    "26–30 岁": 28,
    "31–40 岁": 35,
    "41–50 岁": 45,
    "50 岁以上": 55,
}

# 是否使用过生成式 AI → 旧字段 ai_experience 映射
_AI_EXP = {
    "是": "basic",   # 使用过 → 视为有基础经验
    "否": "none",
}


def _split_multi(raw: str) -> list[str]:
    """Split a multi-choice answer. Separator must match what the frontend writes."""
    return [p.strip() for p in raw.split("|") if p.strip()]


def _first_choice(raw) -> str | None:
    """First selected option of a single- or multi-choice answer, else None."""
    if raw is None:
        return None
    parts = [p.strip() for p in str(raw).split("|") if p.strip()]
    return parts[0] if parts else None



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
    """签署知情同意 + 提交前置问卷（phase=pre） → 触发分组（单盲）。

    - 前置问卷题目全部来自 questionnaire_items（phase='pre'），前端 GET
      /api/questionnaire/items?phase=pre 拉取，本接口只负责落库
    - 答案写入 questionnaire_responses（与后置问卷同一张表），便于统一导出
    - 同时把人口学（性别/年龄/学历）+ AI 经验映射到 users 旧列，
      供管理后台与既有导出列（Age/Gender/Education/Tech_Frequency/AI_Experience）继续读取
    - 状态机：REGISTERED → CONSENTED；分配实验分组（单盲）
    - 返回含新 group 的 JWT
    """
    if not req.agreed:
        raise HTTPException(status_code=400, detail="请先勾选「我已阅读并同意」")

    if user.status != UserStatus.REGISTERED:
        raise HTTPException(status_code=400, detail="当前状态无需重复签署知情同意")

    from app.routers.questionnaire import write_responses

    written = await write_responses(db, user, req.responses, expected_phase="pre")

    # 人口学/AI 经验 → users 旧列（导出列仍读这些字段，保持向后兼容）
    answers = {item.sort_order: value for item, value in written}
    user.pre_survey = {
        **{f"q{order:02d}": value for order, value in sorted(answers.items())},
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    gender = _first_choice(answers.get(PRE_ORDER_GENDER))
    if gender:
        user.gender = gender
    age_val = _AGE_VALUES.get(_first_choice(answers.get(PRE_ORDER_AGE)) or "")
    if age_val is not None:
        user.age = age_val
    education = _first_choice(answers.get(PRE_ORDER_EDUCATION))
    if education:
        user.education = education
    freq = _first_choice(answers.get(PRE_ORDER_LLM_FREQ))
    if freq:
        user.tech_frequency = freq
    genai = _first_choice(answers.get(PRE_ORDER_GENAI))
    if genai:
        user.ai_experience = _AI_EXP.get(genai, genai)

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
