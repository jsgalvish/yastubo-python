"""
Yastubo — Service: Auth
Port: 8001
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import sys, os
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
from app.controllers.login_controller import router as login_router
from app.controllers.password_controller import router as password_router
from app.controllers.acl_controller import router as acl_router
from app.controllers.users_controller import router, impersonate_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from common.database import engine
    await engine.dispose()


app = FastAPI(
    title=f"Yastubo — Auth",
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

app.include_router(login_router)
app.include_router(password_router)
app.include_router(router)
app.include_router(impersonate_router)
app.include_router(acl_router)


@app.exception_handler(RequestNotFoundException)
async def request_not_found_handler(request: Request, exc: RequestNotFoundException):
    return JSONResponse(status_code=404, content={"detail": str(exc), "error_code": exc.error_code, "context": exc.context})


@app.exception_handler(TokenException)
async def token_exception_handler(request: Request, exc: TokenException):
    return JSONResponse(status_code=401, content={"detail": str(exc), "error_code": exc.error_code})


@app.exception_handler(TransactionNotFoundException)
async def transaction_not_found_handler(request: Request, exc: TransactionNotFoundException):
    return JSONResponse(status_code=404, content={"detail": str(exc), "error_code": exc.error_code, "context": exc.context})


@app.exception_handler(BaseAppException)
async def base_app_exception_handler(request: Request, exc: BaseAppException):
    return JSONResponse(status_code=500, content={"detail": str(exc), "error_code": exc.error_code})


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth"}
