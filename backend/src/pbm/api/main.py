"""FastAPIアプリケーション(app factory)。

起動: uvicorn pbm.api.main:app --reload --port 8000
テスト: create_app(database_url=...) で一時DBに分離する。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import pbm
from pbm.api.routes import router
from pbm.domain.errors import (
    ApprovalRequiredError,
    CalculationError,
    InvalidTransitionError,
    MissingRequirementError,
    NotFoundError,
)
from pbm.persistence.db import create_engine_and_sessionmaker

logger = logging.getLogger("pbm.api")


def create_app(database_url: str | None = None) -> FastAPI:
    _engine, session_factory = create_engine_and_sessionmaker(database_url)

    app = FastAPI(
        title="Project BirdMan API",
        version=pbm.__version__,
        description="人力飛行機設計支援プラットフォーム(Phase 1: 初期サイジングMVP)",
    )
    app.state.session_factory = session_factory

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotFoundError)
    async def _not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidTransitionError)
    @app.exception_handler(ApprovalRequiredError)
    @app.exception_handler(MissingRequirementError)
    async def _conflict(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(CalculationError)
    async def _calc_error(_request: Request, exc: CalculationError) -> JSONResponse:
        # 計算エンジンのバグを示す。ログに全文を残す(NFR-010)
        logger.exception("計算エラー: %s", exc)
        return JSONResponse(status_code=500, content={"detail": f"計算エラー: {exc}"})

    app.include_router(router)
    return app


app = create_app()
