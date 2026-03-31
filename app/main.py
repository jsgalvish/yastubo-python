"""
Punto de entrada de la aplicación FastAPI.

Cambios aplicados por auditoría de skills:
  - HIGH-3: CORS middleware para permitir requests cross-origin
  - HIGH-4: Lifespan context manager para startup/shutdown
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.exceptions import (
    BaseAppException,
    RequestNotFoundException,
    TokenException,
    TransactionNotFoundException,
)
from app.http.controllers.admin import acl_controller as admin_acl
from app.http.controllers.admin import business_units_controller as admin_business_units
from app.http.controllers.admin import capitated_batch_controller as admin_capitated_batches
from app.http.controllers.admin import capitated_controller as admin_capitated
from app.http.controllers.admin import companies_controller as admin_companies
from app.http.controllers.admin import config_controller as admin_config
from app.http.controllers.admin import countries_controller as admin_countries
from app.http.controllers.admin import coverages_controller as admin_coverages
from app.http.controllers.admin import locale_controller as admin_locale
from app.http.controllers.admin import plan_version_countries_controller as admin_pv_countries
from app.http.controllers.admin import plan_versions_controller as admin_plan_versions
from app.http.controllers.admin import products_controller as admin_products
from app.http.controllers.admin import regalias_controller as admin_regalias
from app.http.controllers.admin import templates_controller as admin_templates
from app.http.controllers.admin import users_controller as admin_users
from app.http.controllers.admin import zones_controller as admin_zones
from app.http.controllers.auth import login_controller, password_controller
from app.http.controllers.public import capitated_contract_pdf_controller as public_capitated_pdf
from app.http.controllers.public import file_controller as public_files


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown de la aplicación."""
    # Startup: aquí se pueden inicializar pools, caches, etc.
    yield
    # Shutdown: aquí se pueden cerrar conexiones, limpiar recursos.
    from app.database import engine

    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.app_debug,
    lifespan=lifespan,
)

# CORS — permite requests desde el frontend (ajustar origins en producción)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(login_controller.router)
app.include_router(password_controller.router)
app.include_router(admin_users.router)
app.include_router(admin_users.impersonate_router)
app.include_router(admin_acl.router)
app.include_router(admin_countries.router)
app.include_router(admin_zones.router)
app.include_router(admin_companies.router)
app.include_router(admin_products.router)
app.include_router(admin_plan_versions.router)
app.include_router(admin_coverages.catalog_router)
app.include_router(admin_coverages.pv_cov_router)
app.include_router(admin_pv_countries.pv_country_router)
app.include_router(admin_pv_countries.pv_repatriation_router)
app.include_router(admin_regalias.router)
app.include_router(admin_business_units.router)
app.include_router(admin_capitated.router)
app.include_router(admin_capitated_batches.router)
app.include_router(admin_templates.router)
app.include_router(admin_config.router)
app.include_router(admin_locale.router)

# ── Public routes (no auth) ──────────────────────────────────────────────────
app.include_router(public_capitated_pdf.router)
app.include_router(public_files.router)

# ── Static files (email assets, etc.) ───────────────────────────────────────
_static_dir = Path(__file__).resolve().parent.parent / "resources" / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# ── Exception handlers ───────────────────────────────────────────────────────


@app.exception_handler(RequestNotFoundException)
async def request_not_found_handler(request: Request, exc: RequestNotFoundException):
    return JSONResponse(
        status_code=404,
        content={
            "detail": str(exc) or "Recurso no encontrado.",
            "error_code": exc.error_code,
            "context": exc.context,
        },
    )


@app.exception_handler(TokenException)
async def token_exception_handler(request: Request, exc: TokenException):
    return JSONResponse(
        status_code=401,
        content={
            "detail": str(exc) or "Error de autenticación.",
            "error_code": exc.error_code,
        },
    )


@app.exception_handler(TransactionNotFoundException)
async def transaction_not_found_handler(request: Request, exc: TransactionNotFoundException):
    return JSONResponse(
        status_code=404,
        content={
            "detail": str(exc) or "Transacción no encontrada.",
            "error_code": exc.error_code,
            "context": exc.context,
        },
    )


@app.exception_handler(BaseAppException)
async def base_app_exception_handler(request: Request, exc: BaseAppException):
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc) or "Error interno.",
            "error_code": exc.error_code,
        },
    )


@app.get("/")
def root() -> dict:
    return {"status": "ok", "app": settings.app_name}
