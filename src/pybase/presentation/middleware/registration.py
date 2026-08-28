from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pybase.presentation.middleware.access_log import AccessLogMiddleware
from pybase.presentation.middleware.auth import AuthMiddleware
from pybase.presentation.middleware.request_context import RequestContextMiddleware


def register_middlewares(app: FastAPI) -> None:
    """按从外到内的执行顺序注册中间件。"""
    # FastAPI 后注册的中间件位于更外层，因此 CORS 必须最后注册，
    # 确保预检请求（OPTIONS）在最外层被处理，不会被内部中间件（如 Auth）拦截。
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )