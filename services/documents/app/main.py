"""
Yastubo — Service: Documents
Port: 8003
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
from app.controllers.templates_controller import router as templates_router
from app.controllers.file_controller import router as files_router
from app.controllers.capitated_contract_pdf_controller import router as capitated_pdf_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from common.database import engine
    await engine.dispose()


app = FastAPI(
    title=f"Yastubo — Documents",
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

app.include_router(templates_router)
app.include_router(files_router)
app.include_router(capitated_pdf_router)


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
    return {"status": "ok", "service": "documents"}
