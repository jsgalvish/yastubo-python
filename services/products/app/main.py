"""
Yastubo — Service: Products
Port: 8002
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
from app.controllers.products_controller import router as products_router
from app.controllers.plan_versions_controller import router as plan_versions_router
from app.controllers.plan_version_countries_controller import pv_country_router, pv_repatriation_router
from app.controllers.coverages_controller import catalog_router, pv_cov_router
from app.controllers.countries_controller import router as countries_router
from app.controllers.zones_controller import router as zones_router
from app.controllers.locale_controller import router as locale_router
from app.controllers.config_controller import router as config_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from common.database import engine
    await engine.dispose()


app = FastAPI(
    title=f"Yastubo — Products",
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

app.include_router(products_router)
app.include_router(plan_versions_router)
app.include_router(pv_country_router)
app.include_router(pv_repatriation_router)
app.include_router(catalog_router)
app.include_router(pv_cov_router)
app.include_router(countries_router)
app.include_router(zones_router)
app.include_router(locale_router)
app.include_router(config_router)


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
    return {"status": "ok", "service": "products"}
