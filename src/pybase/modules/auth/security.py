from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from pybase.core.config import get_settings

settings = get_settings()


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.auth.access_token_expire_minutes)
    )
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.auth.secret_key, algorithm=settings.auth.algorithm)


def create_refresh_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.auth.refresh_token_expire_minutes)
    )
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.auth.secret_key, algorithm=settings.auth.algorithm)


def decode_token(token: str, *, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(
            token, settings.auth.secret_key, algorithms=[settings.auth.algorithm]
        )
    except jwt.ExpiredSignatureError:
        from pybase.core.exceptions import UnauthorizedError
        raise UnauthorizedError("令牌已过期，请重新登录")
    except jwt.InvalidTokenError:
        from pybase.core.exceptions import UnauthorizedError
        raise UnauthorizedError("无效的令牌")
    if payload.get("type") != expected_type:
        from pybase.core.exceptions import UnauthorizedError
        raise UnauthorizedError("令牌类型不匹配")
    return payload