"""
Punto de entrada de la aplicación FastAPI.

Cambios aplicados por auditoría de skills:
  - HIGH-3: CORS middleware para permitir requests cross-origin
  - HIGH-4: Lifespan context manager para startup/shutdown
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.http.controllers.admin import acl_controller as admin_acl
from app.http.controllers.admin import companies_controller as admin_companies
from app.http.controllers.admin import plan_versions_controller as admin_plan_versions
from app.http.controllers.admin import products_controller as admin_products
from app.http.controllers.admin import countries_controller as admin_countries
from app.http.controllers.admin import users_controller as admin_users
from app.http.controllers.admin import zones_controller as admin_zones
from app.http.controllers.auth import login_controller, password_controller


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
app.include_router(admin_acl.router)
app.include_router(admin_countries.router)
app.include_router(admin_zones.router)
app.include_router(admin_companies.router)
app.include_router(admin_products.router)
app.include_router(admin_plan_versions.router)


@app.get("/")
def root() -> dict:
    return {"status": "ok", "app": settings.app_name}
