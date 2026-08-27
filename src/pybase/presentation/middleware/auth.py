import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from pybase.core.config import get_settings
from pybase.modules.auth.security import decode_token

logger = logging.getLogger(__name__)

settings = get_settings()


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.auth.enabled:
            return await call_next(request)

        if _is_public_path(request.url.path, settings.auth.public_paths):
            return await call_next(request)

        token = _extract_token(request)
        if token is None:
            return _unauthorized("请先登录")

        try:
            payload = decode_token(token, expected_type="access")
        except Exception as exc:
            return _unauthorized(str(exc))

        request.state.user_id = int(payload["sub"])

        return await call_next(request)


def _is_public_path(path: str, public_paths: tuple[str, ...]) -> bool:
    for prefix in public_paths:
        if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
            return True
    return False


def _extract_token(request: Request) -> str | None:
    authorization: str | None = request.headers.get("Authorization")
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


def _unauthorized(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"code": "AUTHENTICATION_FAILED", "message": message},
    )
