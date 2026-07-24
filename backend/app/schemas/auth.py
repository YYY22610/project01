"""Pydantic schemas for authentication."""
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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
