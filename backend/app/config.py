"""Application configuration using Pydantic Settings."""
import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/travel_experiment"

    # JWT
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Admin defaults
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # LLM
    LLM_API_KEY: str = ""
    LLM_API_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"

    # Email
    # 发信后端：smtp / resend / mock（留空则按「有 SMTP 配置→有 Resend key→mock」自动选择）
    EMAIL_BACKEND: str = ""
    # SMTP（推荐，国内可达，QQ/163/Gmail/腾讯企业邮/阿里云均支持）
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""          # 发信账号，如 123456@qq.com
    SMTP_PASSWORD: str = ""      # 授权码（不是登录密码）
    SMTP_USE_SSL: bool = True    # 465 端口用 SSL；587 端口请改为 False 并设置 SMTP_USE_TLS=True
    SMTP_USE_TLS: bool = False   # 587 端口用 STARTTLS
    SENDER_EMAIL: str = "experiment@example.com"  # 发件人，QQ 邮箱需与 SMTP_USER 一致
    # Resend（备选，需国外信用卡 + 验证域名）
    RESEND_API_KEY: str = ""

    # Search
    BING_SEARCH_API_KEY: str = ""
    GOOGLE_SEARCH_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def use_mock_llm(self) -> bool:
        return not self.LLM_API_KEY


settings = Settings()
