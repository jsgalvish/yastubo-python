# Yastubo Python

**Sistema de gestion de seguros** — Backend FastAPI con arquitectura de microservicios.

Fase 2 de la migracion de [gfa-emisiones](https://github.com/jsgalvish/gfa-emisiones) (Laravel 12 / PHP 8.3).
Espejo funcional 1:1 del monolito PHP, reconstruido en Python con FastAPI.

| Fase | Descripcion | Estado |
|------|-------------|--------|
| **Fase 1** | Monolito PHP (gfa-emisiones) | Produccion actual |
| **Fase 2** | Monolito Python (este repo) | En desarrollo |
| **Fase 3** | Descomposicion en microservicios | Futuro |

---

## Stack tecnologico

| Capa | Tecnologia |
|------|-----------|
| Lenguaje | Python 3.13+ |
| Framework | FastAPI 0.115+ |
| ORM | SQLAlchemy 2.0 (async) |
| DB Driver (async) | aiomysql |
| DB Driver (sync) | pymysql (Alembic, scripts) |
| Migraciones | Alembic |
| Auth | python-jose (JWT) + bcrypt (paridad `$2y$` con PHP) |
| Base de datos | MariaDB 11 / MySQL 8 |
| Cache/Sesiones | Redis 7 |
| API Gateway | Nginx |
| PDF | xhtml2pdf + Jinja2 |
| Email | SMTP (Gmail compatible) |
| Pagos | Stripe (suscripciones, webhooks, Connect Express) |
| Observabilidad | Prometheus + Grafana |
| Testing | pytest + pytest-asyncio + pytest-cov |
| Linting | ruff (E, W, F, I, UP, B, C4, SIM, ASYNC, RUF) |
| Type checking | mypy |
| Contenedores | Docker + Docker Compose 3.9 |

---

## Arquitectura

El sistema se compone de **7 microservicios** independientes detras de un API Gateway Nginx, compartiendo una base de datos MariaDB y cache Redis:

```
                    +--------------------------+
                    |    Nginx API Gateway     |
                    |        (Puerto 80)       |
                    +----+----+----+----+------+
                         |    |    |    |
         +-------+-------+----+----+----+-------+-------+
         |       |       |    |    |    |       |       |
         v       v       v    v    v    v       v       v
      +------+ +----+ +----+ +---+ +---+ +-----+ +------+
      | Auth | |Prod| |Docs| |Cap| |Aud| | Bill| | Chat |
      | 8001 | |8002| |8003| |8004|8005| | 8006| | 8007 |
      +------+ +----+ +----+ +---+ +---+ +-----+ +------+
         |       |       |    |    |    |       |       |
         +-------+-------+----+----+----+-------+-------+
                         |              |
                    +----+----+    +----+----+
                    | MariaDB |    |  Redis  |
                    |  (3306) |    |  (6379) |
                    +---------+    +---------+
```

### Microservicios

| Modulo | Servicio | Puerto | Descripcion |
|--------|----------|--------|-------------|
| A | **auth** | 8001 | Autenticacion JWT, usuarios, ACL, roles y permisos |
| B | **products** | 8002 | Productos, planes, coberturas, paises, zonas, config |
| C | **documents** | 8003 | Plantillas HTML/PDF, archivos, contratos |
| D | **capitados** | 8004 | Empresas, unidades de negocio, contratos capitados B2B |
| E | **audit** | 8005 | Logs de auditoria |
| F | **billing** | 8006 | Suscripciones Stripe, webhooks, Connect Express, CRM |
| G | **chatbot** | 8007 | Integracion n8n/SofIA para chatbot |

---

## Inicio rapido

### Requisitos previos

- Docker y Docker Compose v2+
- (Opcional) Python 3.13+ para desarrollo local sin Docker

### 1. Clonar y configurar

```bash
git clone https://github.com/jsgalvish/yastubo-python.git
cd yastubo-python
cp .env.example .env
```

### 2. Levantar con Docker Compose

```bash
# Levantar toda la infraestructura + servicios
docker compose up -d

# Verificar que todos los servicios estan corriendo
docker compose ps
```

Esto levanta:

| Servicio | URL |
|----------|-----|
| API Gateway | http://localhost |
| Auth | http://localhost:8001 |
| Products | http://localhost:8002 |
| Documents | http://localhost:8003 |
| Capitados | http://localhost:8004 |
| Audit | http://localhost:8005 |
| Billing | http://localhost:8006 |
| Chatbot | http://localhost:8007 |
| MariaDB | localhost:3307 |
| Redis | localhost:6379 |
| Mailhog (SMTP test) | http://localhost:8025 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

### 3. Desarrollo local (sin Docker)

```bash
# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Instalar dependencias (incluye dev)
pip install -e ".[dev]"

# Ejecutar migraciones
alembic upgrade head

# Iniciar un servicio individual
uvicorn services.auth.app.main:app --reload --port 8001
```

---

## Variables de entorno

Archivo `.env.example` con todas las variables disponibles:

| Variable | Descripcion | Default |
|----------|-------------|---------|
| `APP_NAME` | Nombre de la aplicacion | `Yastubo` |
| `APP_ENV` | Entorno (local/staging/production) | `local` |
| `APP_DEBUG` | Modo debug | `true` |
| `DB_HOST` | Host de MariaDB/MySQL | `mariadb` |
| `DB_PORT` | Puerto de la BD | `3306` |
| `DB_NAME` | Nombre de la base de datos | `gfa` |
| `DB_USER` | Usuario de BD | `gfa` |
| `DB_PASSWORD` | Password de BD | `gfa` |
| `SECRET_KEY` | Clave de firma JWT | (cambiar en produccion) |
| `STRIPE_SECRET_KEY` | Clave secreta de Stripe | — |
| `STRIPE_WEBHOOK_SECRET` | Secreto para webhooks Stripe | — |
| `GRAFANA_USER` | Usuario admin de Grafana | `admin` |
| `GRAFANA_PASSWORD` | Password de Grafana | `yastubo` |
| `RECAPTCHA_SECRET` | Secreto reCAPTCHA v3 (opcional) | — |
| `SMTP_HOST` | Host del servidor SMTP | — |
| `SMTP_PORT` | Puerto SMTP | `587` |
| `SMTP_USER` | Usuario SMTP | — |
| `SMTP_PASSWORD` | Password SMTP | — |
| `SMTP_FROM` | Email remitente | `noreply@yastubo.com` |

---

## Documentacion de la API (OpenAPI / Swagger)

Cada microservicio expone documentacion interactiva automatica gracias a FastAPI:

| Servicio | Swagger UI | ReDoc |
|----------|-----------|-------|
| Auth | http://localhost:8001/docs | http://localhost:8001/redoc |
| Products | http://localhost:8002/docs | http://localhost:8002/redoc |
| Documents | http://localhost:8003/docs | http://localhost:8003/redoc |
| Capitados | http://localhost:8004/docs | http://localhost:8004/redoc |
| Audit | http://localhost:8005/docs | http://localhost:8005/redoc |
| Billing | http://localhost:8006/docs | http://localhost:8006/redoc |
| Chatbot | http://localhost:8007/docs | http://localhost:8007/redoc |

Cada servicio tambien expone:
- `GET /health` — Health check
- `GET /metrics` — Metricas Prometheus

### Resumen de endpoints

El sistema cuenta con **150+ endpoints** distribuidos en los 7 servicios. Consultar [`docs/ENDPOINTS.md`](docs/ENDPOINTS.md) para el catalogo completo.

---

## Estructura del proyecto

```
yastubo-python/
|-- app/                          # Capa de aplicacion (re-exports de common/)
|   |-- main.py                   # App FastAPI unificada (testing)
|   |-- http/middleware/          # Middleware: auth, permisos, recaptcha
|   |-- models/                   # Re-exports de common/models
|   |-- services/                 # Re-exports de common/services
|   +-- notifications/            # Templates de email
|
|-- common/                       # Codigo de dominio compartido
|   |-- config.py                 # Settings (pydantic-settings)
|   |-- database.py               # SQLAlchemy engine & session factory
|   |-- models/                   # 40+ modelos SQLAlchemy ORM
|   |   |-- base.py               # Base, TimestampMixin, SoftDeleteMixin
|   |   |-- concerns/             # Mixins: HasDirectory, HasTranslatableJson
|   |   |-- user.py               # User, StaffProfile, CustomerProfile
|   |   |-- company.py            # Company, CompanyUser
|   |   |-- product.py            # Product, PlanVersion, PlanVersionCoverage
|   |   +-- ...                   # 40+ archivos de modelos
|   |-- services/                 # Logica de negocio
|   |   |-- auth_service.py       # JWT / tokens
|   |   |-- permission_service.py # Evaluacion RBAC
|   |   |-- billing/              # Stripe billing
|   |   |-- pdf/                  # Generacion de PDFs
|   |   +-- ...
|   +-- middleware/               # Middleware HTTP compartido
|
|-- services/                     # 7 microservicios (containerizados)
|   |-- auth/                     # Modulo A (puerto 8001)
|   |-- products/                 # Modulo B (puerto 8002)
|   |-- documents/                # Modulo C (puerto 8003)
|   |-- capitados/                # Modulo D (puerto 8004)
|   |-- audit/                    # Modulo E (puerto 8005)
|   |-- billing/                  # Modulo F (puerto 8006)
|   +-- chatbot/                  # Modulo G (puerto 8007)
|       +-- app/
|           |-- main.py           # Entry point del servicio
|           |-- controllers/      # Endpoints
|           +-- requests/         # Schemas de validacion
|
|-- config/                       # Configuracion standalone
|-- database/migrations/          # Migraciones Alembic
|-- tests/                        # Suite de pruebas (pytest)
|-- resources/                    # Assets frontend, templates, i18n
|-- monitoring/                   # Prometheus + Grafana config
|-- nginx/                        # Configuracion del API Gateway
|-- scripts/                      # Scripts utilitarios
|-- docker-compose.yml            # Orquestacion local
|-- docker-compose.swarm.yml      # Produccion (Docker Swarm)
|-- Makefile                      # Pipeline QA
+-- pyproject.toml                # Dependencias y config de herramientas
```

---

## Modelo de datos

El sistema cuenta con **40+ modelos SQLAlchemy** organizados en los siguientes dominios. Consultar [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) para el diagrama completo.

### Dominios principales

| Dominio | Modelos | Tabla(s) clave |
|---------|---------|----------------|
| **Usuarios** | User, StaffProfile, CustomerProfile, PasswordHistory | `users`, `staff_profiles`, `customer_profiles` |
| **RBAC** | Role, Permission + 3 tablas pivot | `roles`, `permissions`, `model_has_roles` |
| **Empresas** | Company, CompanyUser, BusinessUnit, BusinessUnitMembership | `companies`, `business_units` |
| **Geografia** | Country, Zone | `countries`, `zones`, `country_zone` |
| **Productos** | Product, PlanVersion, PlanVersionCoverage, PlanVersionAgeSurcharge | `products`, `plan_versions` |
| **Coberturas** | CoverageCategory, Coverage, UnitOfMeasure | `coverages`, `coverage_categories` |
| **Capitados** | CapitatedProductInsured, CapitatedContract, CapitatedMonthlyRecord, CapitatedBatchLog | `capitados_contracts`, `capitados_batch_logs` |
| **Documentos** | File, Template, TemplateVersion | `files`, `templates`, `template_versions` |
| **Auditoria** | AuditLog | `audit_logs` |
| **Billing** | Subscription, Regalia | `subscriptions`, `regalias` |

### Mixins

- **TimestampMixin** — Agrega `created_at`, `updated_at` automaticos
- **SoftDeleteMixin** — Agrega `deleted_at` para borrado logico
- **HasTranslatableJson** — Campos JSON traducibles (es/en)
- **HasDirectory** — Tracking automatico de directorios

---

## Migraciones

Las migraciones se gestionan con **Alembic** sobre SQLAlchemy 2.0.

```bash
# Ejecutar todas las migraciones pendientes
alembic upgrade head

# Crear nueva migracion
alembic revision --autogenerate -m "descripcion del cambio"

# Ver estado actual
alembic current

# Revertir ultima migracion
alembic downgrade -1

# Ver historial
alembic history
```

La base de datos se comparte con el monolito PHP (Fase 1), por lo que las migraciones deben ser compatibles con ambos sistemas durante la transicion.

---

## Suite de pruebas

### Ejecutar tests

```bash
# Suite completa con cobertura
make test

# Tests rapidos (sin cobertura, falla al primer error)
make test-fast

# Solo tests unitarios
make test-unit

# Solo tests de integracion
make test-integration

# Con pytest directamente
pytest                          # completo
pytest tests/auth/              # solo auth
pytest tests/admin/test_acl.py  # archivo especifico
pytest -k "test_login"          # por nombre
```

### Cobertura

- **Objetivo minimo**: 55% (enforced via `--cov-fail-under=55`)
- **Modulos cubiertos**: `common/` y `services/`
- **Reporte HTML**: `coverage_html/index.html`

### Estructura de tests

```
tests/
|-- conftest.py                    # Fixtures: DB en memoria, client HTTP, tokens
|-- auth/
|   +-- test_auth.py               # Login, JWT, passwords, realm isolation (33 tests)
|-- admin/
|   |-- test_acl.py                # Roles, permisos, matrix, toggle (32 tests)
|   |-- test_users.py              # CRUD usuarios, perfiles, status (35 tests)
|   |-- test_companies.py          # Empresas, branding, memberships (32 tests)
|   |-- test_geo.py                # Paises, zonas, relaciones M2M (32 tests)
|   |-- test_products.py           # Productos, tipos, campos traducibles (22 tests)
|   |-- test_plan_versions.py      # Versiones, pricing, paises (22 tests)
|   |-- test_business_units.py     # Jerarquia, ancestor_chain (20 tests)
|   |-- test_templates.py          # CRUD, versiones, HTML/PDF (19 tests)
|   |-- test_coverages.py          # Categorias, unidades, formato (15 tests)
|   |-- test_config.py             # Settings del sistema (14 tests)
|   |-- test_regalias.py           # Comisiones, fuentes polimorficas (11 tests)
|   |-- test_capitated.py          # Personas, contratos, UUID (11 tests)
|   +-- test_capitated_batches.py  # Procesamiento batch, errores (12 tests)
|-- models/
|   +-- test_models.py             # Estructura, relaciones, mixins (60 tests)
|-- roles/
|   +-- test_roles.py              # PermissionService, asignacion (23 tests)
+-- support/
    +-- test_support.py            # Formato, JSON, helpers (53 tests)
```

**Total: 447 tests** cubriendo rutas criticas: RBAC, autenticacion, capitados, usuarios y modelos.

### Infraestructura de testing

- **Base de datos**: SQLite en memoria (aiosqlite) — aislamiento completo
- **HTTP Client**: `httpx.AsyncClient` con override de dependencias FastAPI
- **Fixtures**: `create_actor_token()` genera JWT con permisos especificos
- **Markers**: `@pytest.mark.unit` y `@pytest.mark.integration`

---

## Pipeline QA

El `Makefile` define el pipeline completo de calidad:

```bash
# Pipeline QA completo (format + lint + typecheck + test)
make qa

# Comandos individuales
make install         # pip install -e ".[dev]"
make format          # ruff format
make format-check    # verificar formato sin modificar
make lint            # ruff check
make lint-fix        # corregir automaticamente
make typecheck       # mypy
make test            # pytest completo
make clean           # limpiar __pycache__, .coverage, etc.
```

### Herramientas de calidad

| Herramienta | Proposito | Configuracion |
|-------------|-----------|---------------|
| **ruff** | Linting + formato | `pyproject.toml` [tool.ruff] |
| **mypy** | Type checking | `pyproject.toml` [tool.mypy] |
| **pytest** | Testing | `pyproject.toml` [tool.pytest] |
| **pytest-cov** | Cobertura de codigo | Min 55%, HTML report |

---

## Docker

### Desarrollo local

```bash
# Levantar todo
docker compose up -d

# Reconstruir un servicio especifico
docker compose build auth
docker compose up -d auth

# Ver logs de un servicio
docker compose logs -f auth

# Detener todo
docker compose down

# Detener y eliminar volumenes (reset completo)
docker compose down -v
```

### Estructura de contenedores

Cada servicio tiene su propio `Dockerfile` en `services/<nombre>/Dockerfile`:

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY common/ /app/common/        # Codigo compartido
COPY config/ /app/config/
COPY services/<nombre>/app/ /app/app/
COPY resources/ /app/resources/
COPY services/<nombre>/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH=/app
EXPOSE 800X
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "800X"]
```

### Produccion (Docker Swarm)

```bash
# Deploy
docker stack deploy -c docker-compose.swarm.yml yastubo

# Escalar un servicio
docker service scale yastubo_auth=3

# Ver estado
docker service ls

# Remover stack
docker stack rm yastubo
```

Configuracion de produccion (`docker-compose.swarm.yml`):
- Zero-downtime deployments (`order: start-first`)
- Limites de recursos (CPU/memoria por servicio)
- Auto-restart on failure (max 3 intentos)
- Replicas configurables (auth y billing: 2 por defecto)

---

## Observabilidad

### Prometheus

- **URL**: http://localhost:9090
- **Config**: `monitoring/prometheus.yml`
- Cada servicio expone metricas en `GET /metrics` via `prometheus-fastapi-instrumentator`

### Grafana

- **URL**: http://localhost:3000
- **Credenciales**: admin / yastubo (configurables via env)
- **Dashboard**: `monitoring/grafana/dashboard_yastubo.json`

---

## Routing (Nginx API Gateway)

El API Gateway Nginx (`nginx/nginx.conf`) enruta las peticiones al servicio correspondiente:

| Patron de ruta | Servicio |
|----------------|----------|
| `/admin/login`, `/customer/login`, `/admin/users`, `/admin/acl` | auth (8001) |
| `/admin/products`, `/admin/coverages`, `/admin/countries`, `/admin/zones`, `/admin/config`, `/admin/dashboard` | products (8002) |
| `/admin/templates`, `/files/*` | documents (8003) |
| `/admin/companies`, `/admin/business-units`, `/admin/regalias` | capitados (8004) |
| `/admin/audit` | audit (8005) |
| `/customer/subscription`, `/webhooks/stripe`, `/admin/subscriptions` | billing (8006) |
| `/chatbot` | chatbot (8007) |

---

## Plan de migracion (Fase 2)

Espejo funcional 1:1 del monolito PHP. Cada paso corresponde a controladores del sistema original.

| # | Descripcion | Controladores PHP | Estado |
|---|-------------|-------------------|--------|
| 1 | Support / Utils | — | Completado |
| 2 | Modelos SQLAlchemy | — | Completado |
| 3 | Auth JWT | LoginController, PasswordController | Completado |
| 4 | Roles y permisos | — | Completado |
| 5 | Usuarios admin | UsersController | Completado |
| 6 | ACL | RolesPermissionsController | Completado |
| 7 | Catalogos geograficos | CountryController, ZoneController | Completado |
| 8 | Empresas | CompanyController | En progreso |
| 9 | Unidades de negocio | BusinessUnitController | En progreso |
| 10 | Catalogo de coberturas | CoverageCatalogController | En progreso |
| 11 | Productos | ProductController | En progreso |
| 12 | Versiones de plan | PlanVersionController | En progreso |
| 13 | Paises de plan | PlanVersionCountryController | En progreso |
| 14 | Plantillas | TemplateController | En progreso |
| 15 | Regalias y config | RegaliasController, ConfigController | En progreso |
| 16 | Capitados | CapitatedBatchController, CapitatedContractController | En progreso |
| 17 | Archivos | FileController | En progreso |
| 18 | Dashboard | DashboardController | En progreso |

---

## Licencia

Proyecto privado. Todos los derechos reservados.
