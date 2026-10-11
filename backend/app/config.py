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

    # 运行环境：dev / production。非 dev 环境将强制要求显式配置强密钥，防止默认值上线。
    APP_ENV: str = "dev"

    # LLM
    LLM_API_KEY: str = ""
    LLM_API_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    # 是否允许使用 Mock LLM。开发/自测时可留 True；正式收实验数据前设 False，
    # 此时若 LLM_API_KEY 为空将拒绝启动（防止用 Mock 的虚假回答污染数据）。
    ALLOW_MOCK_LLM: bool = True

    # LLM 并发限流：同时在飞的真实 LLM 请求上限。
    # DashScope(Qwen/OpenAI 兼容)有 QPS 限制，多人同时对话（含 MOA 群辩多 Agent）
    # 会短时并发打出大量请求，超限会返回 429 打断正在对话的参与者、污染实验数据。
    # 超出部分排队等待，而非直接打上游。20 人规模实测 5 较稳妥。
    LLM_MAX_CONCURRENCY: int = 5
    # 等待并发许可的最长秒数，超时返回友好提示，避免无限排队。
    LLM_CONCURRENCY_WAIT_TIMEOUT: float = 180.0

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
    # MOA 群辩搜索增强：主持人整合方案前自动联网搜索（DuckDuckGo 网页版抓取，免 Key），
    # 把真实网页摘要注入整合 prompt，让价格/营业时间有据可依。演示环境网络不稳可设 false 关闭。
    SEARCH_ENHANCE: bool = True

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def use_mock_llm(self) -> bool:
        return not self.LLM_API_KEY


settings = Settings()

# 安全启动校验：非 dev 环境必须显式配置强密钥与管理员口令，杜绝默认值/弱密钥上线。
# 默认 SECRET_KEY 是公开值，若在生产环境沿用，任何人可伪造管理员 JWT 并接管系统。
if settings.APP_ENV != "dev":
    if (
        not settings.SECRET_KEY
        or settings.SECRET_KEY == "dev-secret-key-change-in-production"
        or len(settings.SECRET_KEY) < 32
    ):
        raise RuntimeError(
            "生产环境必须显式配置 SECRET_KEY（长度 ≥ 32 的随机字符串，如 "
            "`python -c \"import secrets; print(secrets.token_hex(32))\"`），"
            "禁止使用默认密钥，否则任何人可伪造管理员 JWT。"
        )
    if not settings.ADMIN_PASSWORD or settings.ADMIN_PASSWORD == "admin123":
        raise RuntimeError("生产环境必须显式配置 ADMIN_PASSWORD，禁止使用默认口令。")

# 实验模式禁止 Mock：当显式关闭 ALLOW_MOCK_LLM 时，若没有真实 Key，
# 禁止以 Mock 启动——否则会向实验数据注入虚假 AI 回答，污染结论。
# 该约束与运行环境无关：开发环境只要显式设 ALLOW_MOCK_LLM=false 也会生效。
if not settings.ALLOW_MOCK_LLM and settings.use_mock_llm:
    raise RuntimeError(
        "当前配置 ALLOW_MOCK_LLM=false（实验模式禁止 Mock LLM），但 LLM_API_KEY 为空，"
        "使用 Mock 会向实验数据注入虚假的 AI 回答。请配置真实 LLM_API_KEY 后再启动。"
    )
