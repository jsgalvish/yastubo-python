"""
Yastubo — Service: Audit
Port: 8005
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from common.config import settings
from common.exceptions import (
    BaseAppException,
    RequestNotFoundException,
    TokenException,
    TransactionNotFoundException,
)

from .controllers.audit_controller import router as audit_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from common.database import engine

    await engine.dispose()


app = FastAPI(
    title="Yastubo — Audit",
    version="1.0.0",
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

app.include_router(audit_router)


@app.exception_handler(RequestNotFoundException)
async def request_not_found_handler(request: Request, exc: RequestNotFoundException):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc), "error_code": exc.error_code, "context": exc.context},
    )


@app.exception_handler(TokenException)
async def token_exception_handler(request: Request, exc: TokenException):
    return JSONResponse(status_code=401, content={"detail": str(exc), "error_code": exc.error_code})


@app.exception_handler(TransactionNotFoundException)
async def transaction_not_found_handler(request: Request, exc: TransactionNotFoundException):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc), "error_code": exc.error_code, "context": exc.context},
    )


@app.exception_handler(BaseAppException)
async def base_app_exception_handler(request: Request, exc: BaseAppException):
    return JSONResponse(status_code=500, content={"detail": str(exc), "error_code": exc.error_code})


@app.get("/health")
def health():
    return {"status": "ok", "service": "audit"}
