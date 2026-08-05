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


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
