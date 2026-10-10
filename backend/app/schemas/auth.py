"""Pydantic schemas for authentication."""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    # 密码可选：实验平台支持无密码注册（仅邮箱 + 人口统计），传入时仍按原逻辑哈希
    password: Optional[str] = Field(default=None, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class EmailLoginRequest(BaseModel):
    """仅邮箱登录（实验平台允许已注册邮箱直接登录，无需密码）。"""
    email: EmailStr


class DemographicsRequest(BaseModel):
    age: int = Field(ge=10, le=100)
    gender: str = Field(max_length=20)
    education: str = Field(max_length=50)
    tech_frequency: str = Field(max_length=50)
    ai_experience: str = Field(max_length=50)


# 实验前置问卷 10 题（A1~A5 两段），登录后「知情同意」页面提交
class PreSurveySubmission(BaseModel):
    """实验前置问卷 10 题原始答案。

    字段命名沿用 docx 顺序：q1~q10。
    q1: 是否使用过生成式 AI（生成式AI经验）：yes/no
    q2: 是否具备国内外旅行经验（旅行经验）：domestic/abroad/both/never
    q3: 过去 6 个月 LLM 使用频率：never/rarely/sometimes/often/daily
    q4: 智能体认知（多选，列表）：agent_principle/agent_openclaw/agent_built/agent_deployed/agent_helpful/none
    q5: LLM 使用时长：lt_1m/m_1_3/m_3_6/gte_6m
    q6: 性别：male/female
    q7: 年龄段：18-24/25-34/35-44/45-54/55-64/65+
    q8: 最高学历：high_school/bachelor/master/phd
    q9: 婚姻状况：married/unmarried
    q10: 当前职业：student/full_time/part_time/freelance/unemployed/retired/other
    """
    q1: str = Field(max_length=20)
    q2: str = Field(max_length=20)
    q3: str = Field(max_length=20)
    q4: list[str] = Field(default_factory=list)
    q5: str = Field(max_length=20)
    q6: str = Field(max_length=20)
    q7: str = Field(max_length=20)
    q8: str = Field(max_length=20)
    q9: str = Field(max_length=20)
    q10: str = Field(max_length=20)


class ConsentWithSurveyRequest(BaseModel):
    """知情同意 + 前置问卷一并提交。"""
    agreed: bool
    survey: PreSurveySubmission


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    status: str


class UserResponse(BaseModel):
    id: str
    email: str
    status: str
    age: int | None = None
    gender: str | None = None
    education: str | None = None
    tech_frequency: str | None = None
    ai_experience: str | None = None
    pre_survey: dict | None = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
