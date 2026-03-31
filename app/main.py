"""
Punto de entrada unificado — test harness.

Agrega los routers de TODOS los microservicios en una sola FastAPI app
para que los tests puedan validar todos los endpoints en un solo proceso.

En producción, cada microservicio corre su propio main.py via Docker.
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

# ── Audit service routers ───────────────────────────────────────────────────
from services.audit.app.controllers.audit_controller import router as audit_router
from services.auth.app.controllers.acl_controller import router as acl_router

# ── Auth service routers ────────────────────────────────────────────────────
from services.auth.app.controllers.login_controller import router as login_router
from services.auth.app.controllers.password_controller import router as password_router
from services.auth.app.controllers.users_controller import (
    impersonate_router,
)
from services.auth.app.controllers.users_controller import (
    router as users_router,
)
from services.capitados.app.controllers.business_units_controller import (
    router as business_units_router,
)
from services.capitados.app.controllers.capitated_batch_controller import (
    router as capitated_batch_router,
)
from services.capitados.app.controllers.capitated_controller import router as capitated_router

# ── Capitados service routers ───────────────────────────────────────────────
from services.capitados.app.controllers.companies_controller import router as companies_router
from services.capitados.app.controllers.regalias_controller import router as regalias_router
from services.documents.app.controllers.capitated_contract_pdf_controller import (
    router as capitated_pdf_router,
)
from services.documents.app.controllers.file_controller import router as files_router

# ── Documents service routers ───────────────────────────────────────────────
from services.documents.app.controllers.templates_controller import router as templates_router
from services.products.app.controllers.config_controller import router as config_router
from services.products.app.controllers.countries_controller import router as countries_router
from services.products.app.controllers.coverages_controller import (
    catalog_router as coverages_catalog_router,
)
from services.products.app.controllers.coverages_controller import (
    pv_cov_router,
)
from services.products.app.controllers.locale_controller import router as locale_router
from services.products.app.controllers.plan_version_countries_controller import (
    pv_country_router,
    pv_repatriation_router,
)
from services.products.app.controllers.plan_versions_controller import (
    router as plan_versions_router,
)

# ── Products service routers ────────────────────────────────────────────────
from services.products.app.controllers.products_controller import router as products_router
from services.products.app.controllers.zones_controller import router as zones_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from app.database import engine

    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
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

# ── Auth ────────────────────────────────────────────────────────────────────
app.include_router(login_router)
app.include_router(password_router)
app.include_router(users_router)
app.include_router(impersonate_router)
app.include_router(acl_router)

# ── Products ────────────────────────────────────────────────────────────────
app.include_router(countries_router)
app.include_router(zones_router)
app.include_router(products_router)
app.include_router(plan_versions_router)
app.include_router(coverages_catalog_router)
app.include_router(pv_cov_router)
app.include_router(pv_country_router)
app.include_router(pv_repatriation_router)
app.include_router(config_router)
app.include_router(locale_router)

# ── Documents ───────────────────────────────────────────────────────────────
app.include_router(templates_router)
app.include_router(capitated_pdf_router)
app.include_router(files_router)

# ── Capitados ───────────────────────────────────────────────────────────────
app.include_router(companies_router)
app.include_router(capitated_router)
app.include_router(capitated_batch_router)
app.include_router(business_units_router)
app.include_router(regalias_router)

# ── Audit ───────────────────────────────────────────────────────────────────
app.include_router(audit_router)

# ── Static files ────────────────────────────────────────────────────────────
_static_dir = Path(__file__).resolve().parent.parent / "resources" / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# ── Exception handlers ──────────────────────────────────────────────────────


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
