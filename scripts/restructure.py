"""
Script de reestructuración: monolito → microservicios.

Crea:
  common/          ← código compartido (models, middleware, services, etc.)
  services/auth/   ← Module A
  services/products/ ← Module B
  services/documents/ ← Module C
  services/capitados/ ← Module D
  services/audit/  ← Module E
  services/billing/ ← Module F
  nginx/nginx.conf
  monitoring/prometheus.yml
  docker-compose.yml
"""
from __future__ import annotations

import os
import shutil
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write(path: str, content: str) -> None:
    mkdir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def copy_with_rewrite(src: str, dst: str, replacements: list[tuple[str, str]]) -> None:
    """Copia un archivo aplicando reemplazos de texto."""
    mkdir(os.path.dirname(dst))
    with open(src, "r", encoding="utf-8") as f:
        content = f.read()
    for old, new in replacements:
        content = content.replace(old, new)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(content)


def copy_dir_with_rewrite(src_dir: str, dst_dir: str, replacements: list[tuple[str, str]]) -> None:
    """Copia recursivamente un directorio aplicando reemplazos a archivos .py."""
    for dirpath, dirnames, filenames in os.walk(src_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        rel = os.path.relpath(dirpath, src_dir)
        dst_path = os.path.join(dst_dir, rel)
        mkdir(dst_path)
        for filename in filenames:
            if filename.endswith(".pyc"):
                continue
            src_file = os.path.join(dirpath, filename)
            dst_file = os.path.join(dst_path, filename)
            if filename.endswith(".py"):
                copy_with_rewrite(src_file, dst_file, replacements)
            else:
                shutil.copy2(src_file, dst_file)


# ─── Reemplazos de imports ─────────────────────────────────────────────────────

# Para common/: app.X → common.X, app.http.middleware → common.middleware
COMMON_REPLACEMENTS = [
    ("from app.config", "from common.config"),
    ("from app.database", "from common.database"),
    ("from app.models", "from common.models"),
    ("from app.exceptions", "from common.exceptions"),
    ("from app.services.auth_service", "from common.services.auth_service"),
    ("from app.services.permission_service", "from common.services.permission_service"),
    ("from app.services.token_service", "from common.services.token_service"),
    ("from app.services.config", "from common.services.config"),
    ("from app.services.ip_country", "from common.services.ip_country"),
    ("from app.services.pdf", "from common.services.pdf"),
    ("from app.services.template_render", "from common.services.template_render"),
    ("from app.services.uploaded_file", "from common.services.uploaded_file"),
    ("from app.services.regalias", "from common.services.regalias"),
    ("from app.services.business_units", "from common.services.business_units"),
    ("from app.services.capitated", "from common.services.capitated"),
    ("from app.http.middleware.auth", "from common.middleware.auth"),
    ("from app.http.middleware.permission", "from common.middleware.permission"),
    ("from app.http.middleware.force_password_change", "from common.middleware.force_password_change"),
    ("from app.http.middleware.verify_recaptcha", "from common.middleware.verify_recaptcha"),
    ("from app.support", "from common.support"),
    ("from app.notifications", "from common.notifications"),
]

# Para service controllers: además de common, requests internos del servicio
def service_replacements(service_name: str) -> list[tuple[str, str]]:
    base = list(COMMON_REPLACEMENTS)
    # requests del servicio propio
    base += [
        ("from app.http.requests.admin.", "from app.requests."),
        ("from app.http.requests.auth.", "from app.requests."),
        ("from app.http.requests.customer.", "from app.requests."),
    ]
    return base


# ─── 1. common/ ───────────────────────────────────────────────────────────────

def build_common():
    print("Building common/...")
    common = os.path.join(ROOT, "common")
    mkdir(common)
    write(os.path.join(common, "__init__.py"), "")

    # config.py
    copy_with_rewrite(
        os.path.join(APP, "config.py"),
        os.path.join(common, "config.py"),
        [("from app.", "from common.")],
    )

    # database.py
    copy_with_rewrite(
        os.path.join(APP, "database.py"),
        os.path.join(common, "database.py"),
        [("from app.config", "from common.config")],
    )

    # models/
    copy_dir_with_rewrite(
        os.path.join(APP, "models"),
        os.path.join(common, "models"),
        [("from app.models", "from common.models")],
    )

    # exceptions/
    copy_dir_with_rewrite(
        os.path.join(APP, "exceptions"),
        os.path.join(common, "exceptions"),
        [("from app.", "from common.")],
    )

    # middleware/ (from app/http/middleware/)
    copy_dir_with_rewrite(
        os.path.join(APP, "http", "middleware"),
        os.path.join(common, "middleware"),
        COMMON_REPLACEMENTS,
    )

    # services/ (shared: auth, permission, token, config, ip_country, pdf, template_render, uploaded_file, regalias, business_units, capitated)
    for svc_dir in [
        "auth_service.py", "permission_service.py", "token_service.py",
    ]:
        src = os.path.join(APP, "services", svc_dir)
        if os.path.exists(src):
            copy_with_rewrite(src, os.path.join(common, "services", svc_dir), COMMON_REPLACEMENTS)

    for svc_subdir in ["config", "ip_country", "pdf", "template_render", "uploaded_file", "regalias", "business_units", "capitated"]:
        src = os.path.join(APP, "services", svc_subdir)
        if os.path.exists(src):
            copy_dir_with_rewrite(src, os.path.join(common, "services", svc_subdir), COMMON_REPLACEMENTS)

    write(os.path.join(common, "services", "__init__.py"), "")

    # support/
    copy_dir_with_rewrite(
        os.path.join(APP, "support"),
        os.path.join(common, "support"),
        COMMON_REPLACEMENTS,
    )

    # notifications/
    copy_dir_with_rewrite(
        os.path.join(APP, "notifications"),
        os.path.join(common, "notifications"),
        COMMON_REPLACEMENTS,
    )

    print("  common/ done.")


# ─── 2. services/ ─────────────────────────────────────────────────────────────

SERVICES = {
    "auth": {
        "port": 8001,
        "controllers": ["acl_controller", "users_controller"],
        "auth_controllers": ["login_controller", "password_controller"],
        "requests_admin": ["acl_request", "user_request"],
        "requests_auth": ["login_request", "password_request"],
    },
    "products": {
        "port": 8002,
        "controllers": [
            "products_controller", "plan_versions_controller", "plan_version_countries_controller",
            "coverages_controller", "countries_controller", "zones_controller",
            "locale_controller", "config_controller",
        ],
        "requests_admin": [
            "product_request", "plan_version_request", "plan_version_country_request",
            "coverage_request", "geo_request", "config_request",
        ],
    },
    "documents": {
        "port": 8003,
        "controllers": ["templates_controller"],
        "public_controllers": ["file_controller", "capitated_contract_pdf_controller"],
        "requests_admin": ["template_request"],
    },
    "capitados": {
        "port": 8004,
        "controllers": [
            "capitated_controller", "capitated_batch_controller",
            "companies_controller", "business_units_controller", "regalias_controller",
        ],
        "requests_admin": [
            "capitated_request", "capitated_batch_request",
            "company_request", "business_unit_request", "regalia_request",
        ],
    },
    "audit": {
        "port": 8005,
        "controllers": [],
        "requests_admin": [],
    },
    "billing": {
        "port": 8006,
        "controllers": [],
        "requests_admin": [],
    },
}


def copy_service_controllers(svc: str, cfg: dict) -> None:
    svc_dir = os.path.join(ROOT, "services", svc)
    repl = service_replacements(svc)

    # admin controllers
    for ctrl in cfg.get("controllers", []):
        src = os.path.join(APP, "http", "controllers", "admin", f"{ctrl}.py")
        dst = os.path.join(svc_dir, "app", "controllers", f"{ctrl}.py")
        if os.path.exists(src):
            copy_with_rewrite(src, dst, repl)

    # auth controllers
    for ctrl in cfg.get("auth_controllers", []):
        src = os.path.join(APP, "http", "controllers", "auth", f"{ctrl}.py")
        dst = os.path.join(svc_dir, "app", "controllers", f"{ctrl}.py")
        if os.path.exists(src):
            copy_with_rewrite(src, dst, repl)

    # public controllers
    for ctrl in cfg.get("public_controllers", []):
        src = os.path.join(APP, "http", "controllers", "public", f"{ctrl}.py")
        dst = os.path.join(svc_dir, "app", "controllers", f"{ctrl}.py")
        if os.path.exists(src):
            copy_with_rewrite(src, dst, repl)

    # admin requests/schemas
    for req in cfg.get("requests_admin", []):
        src = os.path.join(APP, "http", "requests", "admin", f"{req}.py")
        dst = os.path.join(svc_dir, "app", "requests", f"{req}.py")
        if os.path.exists(src):
            copy_with_rewrite(src, dst, repl)

    # auth requests
    for req in cfg.get("requests_auth", []):
        src = os.path.join(APP, "http", "requests", "auth", f"{req}.py")
        dst = os.path.join(svc_dir, "app", "requests", f"{req}.py")
        if os.path.exists(src):
            copy_with_rewrite(src, dst, repl)

    # __init__.py files
    for subdir in ["controllers", "requests"]:
        write(os.path.join(svc_dir, "app", subdir, "__init__.py"), "")
    write(os.path.join(svc_dir, "app", "__init__.py"), "")


def build_service_main(svc: str, cfg: dict) -> str:
    """Genera el main.py de cada servicio."""
    port = cfg["port"]
    controllers = cfg.get("controllers", [])
    auth_controllers = cfg.get("auth_controllers", [])
    public_controllers = cfg.get("public_controllers", [])
    all_ctrls = controllers + auth_controllers + public_controllers

    imports = "\n".join([f"from app.controllers.{c} import router as {c}_router" for c in all_ctrls])
    includes = "\n".join([f"app.include_router({c}_router)" for c in all_ctrls])

    # Special cases
    if svc == "auth":
        imports = """from app.controllers.login_controller import router as login_router
from app.controllers.password_controller import router as password_router
from app.controllers.acl_controller import router as acl_router
from app.controllers.users_controller import router, impersonate_router"""
        includes = """app.include_router(login_router)
app.include_router(password_router)
app.include_router(router)
app.include_router(impersonate_router)
app.include_router(acl_router)"""

    elif svc == "products":
        imports = """from app.controllers.products_controller import router as products_router
from app.controllers.plan_versions_controller import router as plan_versions_router
from app.controllers.plan_version_countries_controller import pv_country_router, pv_repatriation_router
from app.controllers.coverages_controller import catalog_router, pv_cov_router
from app.controllers.countries_controller import router as countries_router
from app.controllers.zones_controller import router as zones_router
from app.controllers.locale_controller import router as locale_router
from app.controllers.config_controller import router as config_router"""
        includes = """app.include_router(products_router)
app.include_router(plan_versions_router)
app.include_router(pv_country_router)
app.include_router(pv_repatriation_router)
app.include_router(catalog_router)
app.include_router(pv_cov_router)
app.include_router(countries_router)
app.include_router(zones_router)
app.include_router(locale_router)
app.include_router(config_router)"""

    elif svc == "documents":
        imports = """from app.controllers.templates_controller import router as templates_router
from app.controllers.file_controller import router as files_router
from app.controllers.capitated_contract_pdf_controller import router as capitated_pdf_router"""
        includes = """app.include_router(templates_router)
app.include_router(files_router)
app.include_router(capitated_pdf_router)"""

    elif svc == "capitados":
        imports = """from app.controllers.capitated_controller import router as capitated_router
from app.controllers.capitated_batch_controller import router as capitated_batch_router
from app.controllers.companies_controller import router as companies_router
from app.controllers.business_units_controller import router as business_units_router
from app.controllers.regalias_controller import router as regalias_router"""
        includes = """app.include_router(capitated_router)
app.include_router(capitated_batch_router)
app.include_router(companies_router)
app.include_router(business_units_router)
app.include_router(regalias_router)"""

    elif svc == "audit":
        imports = "from app.controllers.audit_controller import router as audit_router"
        includes = "app.include_router(audit_router)"

    elif svc == "billing":
        imports = """from app.controllers.subscription_controller import router as subscription_router
from app.controllers.stripe_webhook_controller import router as stripe_router"""
        includes = """app.include_router(subscription_router)
app.include_router(stripe_router)"""

    service_title = svc.capitalize()

    return f'''"""
Yastubo — Service: {service_title}
Port: {port}
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
{imports}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from common.database import engine
    await engine.dispose()


app = FastAPI(
    title=f"Yastubo — {service_title}",
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

{includes}


@app.exception_handler(RequestNotFoundException)
async def request_not_found_handler(request: Request, exc: RequestNotFoundException):
    return JSONResponse(status_code=404, content={{"detail": str(exc), "error_code": exc.error_code, "context": exc.context}})


@app.exception_handler(TokenException)
async def token_exception_handler(request: Request, exc: TokenException):
    return JSONResponse(status_code=401, content={{"detail": str(exc), "error_code": exc.error_code}})


@app.exception_handler(TransactionNotFoundException)
async def transaction_not_found_handler(request: Request, exc: TransactionNotFoundException):
    return JSONResponse(status_code=404, content={{"detail": str(exc), "error_code": exc.error_code, "context": exc.context}})


@app.exception_handler(BaseAppException)
async def base_app_exception_handler(request: Request, exc: BaseAppException):
    return JSONResponse(status_code=500, content={{"detail": str(exc), "error_code": exc.error_code}})


@app.get("/health")
def health():
    return {{"status": "ok", "service": "{svc}"}}
'''


def build_service_dockerfile(svc: str, port: int) -> str:
    return f"""FROM python:3.13-slim

WORKDIR /app

# System deps for WeasyPrint (documents service) and aiomysql
RUN apt-get update && apt-get install -y \\
    gcc \\
    default-libmysqlclient-dev \\
    pkg-config \\
    && rm -rf /var/lib/apt/lists/*

# Copy common package
COPY common/ /app/common/

# Copy service
COPY services/{svc}/app/ /app/app/

# Install deps
COPY services/{svc}/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app

EXPOSE {port}

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "{port}"]
"""


BASE_REQUIREMENTS = """fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy[asyncio]>=2.0.0
aiomysql>=0.2.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
prometheus-fastapi-instrumentator>=7.0.0
"""

SERVICE_EXTRA_REQS = {
    "auth": "python-multipart>=0.0.9\nhttpx>=0.27.0\n",
    "products": "openpyxl>=3.1.0\n",
    "documents": "weasyprint>=62.0\njinja2>=3.1.0\npython-multipart>=0.0.9\n",
    "capitados": "openpyxl>=3.1.0\nhttpx>=0.27.0\n",
    "audit": "",
    "billing": "stripe>=10.0.0\n",
}


def build_services():
    print("Building services/...")
    for svc, cfg in SERVICES.items():
        print(f"  Building services/{svc}/ ...")
        svc_dir = os.path.join(ROOT, "services", svc)
        mkdir(svc_dir)

        copy_service_controllers(svc, cfg)
        write(os.path.join(svc_dir, "app", "main.py"), build_service_main(svc, cfg))
        write(os.path.join(svc_dir, "Dockerfile"), build_service_dockerfile(svc, cfg["port"]))
        write(os.path.join(svc_dir, "requirements.txt"), BASE_REQUIREMENTS + SERVICE_EXTRA_REQS.get(svc, ""))

    print("  services/ done.")


# ─── 3. Audit controller (nuevo) ──────────────────────────────────────────────

AUDIT_CONTROLLER = '''"""
Auditoría & Trazabilidad — Module E
Endpoints de lectura del registro inmutable de acciones.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_db
from common.middleware.permission import require_permission
from common.models.audit_log import AuditLog
from common.models.user import User
from app.requests.audit_request import AuditLogOut, AuditLogsResponse, PaginationMeta

router = APIRouter(prefix="/admin/audit", tags=["admin:audit"])

_PERMISSION = "admin.audit.read"


@router.get("", response_model=AuditLogsResponse)
async def audit_index(
    user_id: Optional[int] = Query(default=None),
    action: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    _current_user: User = Depends(require_permission(_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> AuditLogsResponse:
    """Lista paginada del log de auditoría con filtros."""
    import math
    q = select(AuditLog).order_by(AuditLog.created_at.desc())

    if user_id is not None:
        q = q.where(AuditLog.target_user_id == user_id)
    if action:
        q = q.where(AuditLog.action.ilike(f"%{action}%"))
    if date_from:
        q = q.where(func.date(AuditLog.created_at) >= date_from)
    if date_to:
        q = q.where(func.date(AuditLog.created_at) <= date_to)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    items = list((await db.execute(q.offset((page - 1) * per_page).limit(per_page))).scalars().all())

    return AuditLogsResponse(
        data=[AuditLogOut(
            id=log.id,
            action=log.action,
            context_json=log.context_json,
            target_user_id=log.target_user_id,
            created_at=str(log.created_at),
        ) for log in items],
        meta=PaginationMeta(
            current_page=page,
            last_page=max(1, math.ceil(total / per_page)),
            per_page=per_page,
            total=total,
        ),
    )
'''

AUDIT_REQUEST = '''from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    action: str
    context_json: Optional[str] = None
    target_user_id: Optional[int] = None
    created_at: str


class PaginationMeta(BaseModel):
    current_page: int
    last_page: int
    per_page: int
    total: int


class AuditLogsResponse(BaseModel):
    data: list[AuditLogOut]
    meta: PaginationMeta
'''


# ─── 4. Billing placeholders (nuevo) ──────────────────────────────────────────

BILLING_SUBSCRIPTION_CONTROLLER = '''"""
Billing & Subscriptions — Module F
Máquina de estados: Lead → Active → Morosa → Cancelled
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_db
from common.middleware.auth import get_current_user
from common.models.user import User

router = APIRouter(prefix="/customer/subscription", tags=["customer:billing"])


@router.get("/status")
async def subscription_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Estado actual de la suscripción del cliente. Placeholder — implementar con Stripe."""
    return {"status": "pending_implementation", "user_id": current_user.id}
'''

BILLING_STRIPE_CONTROLLER = '''"""
Stripe Webhook Controller — Module F
Recibe eventos de Stripe y actualiza el estado de la suscripción.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/webhooks/stripe", tags=["webhooks:stripe"])


@router.post("")
async def stripe_webhook(request: Request) -> dict:
    """
    Recibe webhooks de Stripe.
    Eventos a manejar:
    - invoice.paid           → Active
    - invoice.payment_failed → Morosa
    - customer.subscription.deleted → Cancelled
    Placeholder — implementar con stripe SDK + idempotency keys.
    """
    payload = await request.body()
    # TODO: verify stripe signature, process event, update subscription state
    return {"received": True}
'''


# ─── 5. nginx.conf ────────────────────────────────────────────────────────────

NGINX_CONF = """events {
    worker_connections 1024;
}

http {
    upstream auth_service      { server auth:8001; }
    upstream products_service  { server products:8002; }
    upstream documents_service { server documents:8003; }
    upstream capitados_service { server capitados:8004; }
    upstream audit_service     { server audit:8005; }
    upstream billing_service   { server billing:8006; }

    server {
        listen 80;

        # ── Auth & ACL (Module A) ──────────────────────────────────────────
        location ~ ^/(admin/login|customer/login|admin/logout|customer/logout|admin/password|customer/password|admin/users|admin/acl) {
            proxy_pass http://auth_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # ── Products & Plans (Module B) ────────────────────────────────────
        location ~ ^/admin/(products|coverages|countries|zones|locale|config) {
            proxy_pass http://products_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # ── Documents & Templates (Module C) ──────────────────────────────
        location ~ ^/(admin/templates|files) {
            proxy_pass http://documents_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # ── Capitados B2B (Module D) ───────────────────────────────────────
        location ~ ^/admin/(companies|business-units|regalias) {
            proxy_pass http://capitados_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # ── Audit (Module E) ───────────────────────────────────────────────
        location /admin/audit {
            proxy_pass http://audit_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # ── Billing & Subscriptions (Module F) ────────────────────────────
        location ~ ^/(customer/subscription|webhooks/stripe) {
            proxy_pass http://billing_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
"""

# ─── 6. Prometheus config ─────────────────────────────────────────────────────

PROMETHEUS_YML = """global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: yastubo-auth
    static_configs:
      - targets: ['auth:8001']
    metrics_path: /metrics

  - job_name: yastubo-products
    static_configs:
      - targets: ['products:8002']
    metrics_path: /metrics

  - job_name: yastubo-documents
    static_configs:
      - targets: ['documents:8003']
    metrics_path: /metrics

  - job_name: yastubo-capitados
    static_configs:
      - targets: ['capitados:8004']
    metrics_path: /metrics

  - job_name: yastubo-audit
    static_configs:
      - targets: ['audit:8005']
    metrics_path: /metrics

  - job_name: yastubo-billing
    static_configs:
      - targets: ['billing:8006']
    metrics_path: /metrics
"""

# ─── 7. docker-compose.yml ────────────────────────────────────────────────────

DOCKER_COMPOSE = """version: '3.9'

x-common-env: &common-env
  DB_HOST: mariadb
  DB_PORT: 3306
  DB_NAME: ${DB_NAME:-gfa}
  DB_USER: ${DB_USER:-gfa}
  DB_PASSWORD: ${DB_PASSWORD:-gfa}
  SECRET_KEY: ${SECRET_KEY:-change-me-in-production}
  APP_ENV: ${APP_ENV:-local}
  APP_DEBUG: ${APP_DEBUG:-true}

x-service-base: &service-base
  build:
    context: .
  restart: unless-stopped
  depends_on:
    mariadb:
      condition: service_healthy
    redis:
      condition: service_healthy
  environment:
    <<: *common-env

services:

  # ── Infrastructure ──────────────────────────────────────────────────────────

  mariadb:
    image: mariadb:11
    restart: unless-stopped
    environment:
      MYSQL_DATABASE: ${DB_NAME:-gfa}
      MYSQL_USER: ${DB_USER:-gfa}
      MYSQL_PASSWORD: ${DB_PASSWORD:-gfa}
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD:-root}
    volumes:
      - mariadb_data:/var/lib/mysql
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── Microservices ───────────────────────────────────────────────────────────

  auth:
    <<: *service-base
    build:
      context: .
      dockerfile: services/auth/Dockerfile
    ports:
      - "8001:8001"

  products:
    <<: *service-base
    build:
      context: .
      dockerfile: services/products/Dockerfile
    ports:
      - "8002:8002"

  documents:
    <<: *service-base
    build:
      context: .
      dockerfile: services/documents/Dockerfile
    ports:
      - "8003:8003"

  capitados:
    <<: *service-base
    build:
      context: .
      dockerfile: services/capitados/Dockerfile
    ports:
      - "8004:8004"

  audit:
    <<: *service-base
    build:
      context: .
      dockerfile: services/audit/Dockerfile
    ports:
      - "8005:8005"

  billing:
    <<: *service-base
    build:
      context: .
      dockerfile: services/billing/Dockerfile
    environment:
      <<: *common-env
      STRIPE_SECRET_KEY: ${STRIPE_SECRET_KEY:-}
      STRIPE_WEBHOOK_SECRET: ${STRIPE_WEBHOOK_SECRET:-}
    ports:
      - "8006:8006"

  # ── API Gateway ─────────────────────────────────────────────────────────────

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - auth
      - products
      - documents
      - capitados
      - audit
      - billing

  # ── Observability ───────────────────────────────────────────────────────────

  prometheus:
    image: prom/prometheus:latest
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus

  grafana:
    image: grafana/grafana:latest
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_USER: ${GRAFANA_USER:-admin}
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-yastubo}
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  mariadb_data:
  prometheus_data:
  grafana_data:
"""

# ─── 8. .env.example ─────────────────────────────────────────────────────────

ENV_EXAMPLE = """# App
APP_NAME=Yastubo
APP_ENV=local
APP_DEBUG=true
APP_URL=http://localhost

# Database
DB_HOST=mariadb
DB_PORT=3306
DB_NAME=gfa
DB_USER=gfa
DB_PASSWORD=gfa
DB_ROOT_PASSWORD=root

# Auth
SECRET_KEY=change-me-in-production-use-openssl-rand-hex-32

# Stripe (Module F)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=yastubo

# reCAPTCHA (opcional)
RECAPTCHA_SECRET=
RECAPTCHA_SITE_KEY=
"""


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Root: {ROOT}")
    build_common()
    build_services()

    # Audit controller & request
    audit_svc = os.path.join(ROOT, "services", "audit")
    write(os.path.join(audit_svc, "app", "controllers", "audit_controller.py"), AUDIT_CONTROLLER)
    write(os.path.join(audit_svc, "app", "requests", "audit_request.py"), AUDIT_REQUEST)

    # Billing controllers
    billing_svc = os.path.join(ROOT, "services", "billing")
    write(os.path.join(billing_svc, "app", "controllers", "subscription_controller.py"), BILLING_SUBSCRIPTION_CONTROLLER)
    write(os.path.join(billing_svc, "app", "controllers", "stripe_webhook_controller.py"), BILLING_STRIPE_CONTROLLER)
    write(os.path.join(billing_svc, "app", "requests", "__init__.py"), "")

    # nginx
    write(os.path.join(ROOT, "nginx", "nginx.conf"), NGINX_CONF)

    # monitoring
    write(os.path.join(ROOT, "monitoring", "prometheus.yml"), PROMETHEUS_YML)

    # docker-compose
    write(os.path.join(ROOT, "docker-compose.yml"), DOCKER_COMPOSE)

    # .env.example
    write(os.path.join(ROOT, ".env.example"), ENV_EXAMPLE)

    print("\nRestructuring complete!")
    print("New structure:")
    for path in [
        "common/", "services/auth/", "services/products/", "services/documents/",
        "services/capitados/", "services/audit/", "services/billing/",
        "nginx/nginx.conf", "monitoring/prometheus.yml", "docker-compose.yml",
    ]:
        full = os.path.join(ROOT, path)
        exists = "OK" if os.path.exists(full) else "MISSING"
        print(f"  [{exists}] {path}")


if __name__ == "__main__":
    main()
