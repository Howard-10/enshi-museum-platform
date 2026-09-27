import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="恩施文博智能导览平台后端 API",
    )
    allowed_origins = list(
        {settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"}
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        # Keep the traceback in server logs while returning a stable JSON
        # response that still passes through CORS middleware.
        logger.exception("Unhandled API error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器暂时无法完成请求，请稍后重试。"},
        )

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
