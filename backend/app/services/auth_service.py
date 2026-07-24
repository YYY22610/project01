"""Authentication service: JWT, password hashing, token validation."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt

from app.config import settings


def hash_password(password: str) -> str:
    # 直接调用 bcrypt，避免 passlib 与 bcrypt 版本耦合
    # （passlib 1.7.4 与 bcrypt>=4.1 不兼容，会导致注册/登录 500）
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # 哈希格式非法（如空串、截断）时安全返回 False，而非抛 500
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_user_token(user_id: str, group: str | None, status: str) -> str:
    payload = {
        "sub": str(user_id),
        "group": group,
        "status": status,
        "role": "user",
    }
    return create_access_token(payload)


def create_admin_token(username: str) -> str:
    payload = {
        "sub": username,
        "role": "admin",
    }
    return create_access_token(payload)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
