# yastubo-python

Monolito FastAPI — Fase 2 de la migración de [gfa-emisiones](https://github.com/jsgalvish/gfa-emisiones) (Laravel 12 / PHP 8.3).

## Descripción

Este proyecto es un **espejo funcional 1:1** del monolito PHP, reconstruido en Python con FastAPI. El objetivo es reproducir cada ruta, modelo, servicio y regla de negocio del sistema original antes de introducir cualquier cambio arquitectónico.

- **Fase 1** — Monolito PHP (gfa-emisiones) ← producción actual
- **Fase 2** — Monolito Python (este repo) ← espejo exacto, misma BD
- **Fase 3** — Descomposición en microservicios (futuro)

## Stack

| Capa | Tecnología |
|------|-----------|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| Migraciones | Alembic |
| Auth | python-jose (JWT) + passlib (bcrypt) |
| Base de datos | MySQL 8 (compartida con Fase 1 en desarrollo) |
| Frontend | Vue 3 + Vite (reconstruido desde cero) |
| Configuración | pydantic-settings |

## Estructura del proyecto

Espeja la estructura PHP 1:1:

```
app/                    # Código de la aplicación (espeja PHP app/)
  casts/                # Tipos personalizados
  console/commands/     # Comandos CLI
  exceptions/           # Excepciones personalizadas
  http/
    controllers/        # Manejadores de rutas (admin/, auth/, dev/)
    middleware/         # Middleware HTTP
    requests/           # Esquemas de validación de requests
  models/               # Modelos SQLAlchemy
    concerns/           # Mixins de modelos
  notifications/        # Notificaciones por email (admin/, customer/)
  observers/            # Observadores de eventos de modelos
  policies/             # Políticas de autorización
  providers/            # Providers / bootstrap de la app
  services/             # Lógica de negocio
  support/              # Clases utilitarias y helpers
config/                 # Módulos de configuración
database/
  migrations/           # Migraciones Alembic
  factories/            # Factories para datos de prueba
public/                 # Archivos estáticos y assets compilados
resources/
  css/                  # Hojas de estilo
  js/                   # Componentes Vue 3 y utilidades
  lang/                 # Traducciones i18n (en/, es/)
  views/                # Plantillas Jinja2
routes/                 # Definición de rutas (admin/, customer/, public/)
tests/
  Feature/              # Tests de integración
  Unit/                 # Tests unitarios
```

## Instalación

```bash
# 1. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Instalar dependencias
pip install -e ".[dev]"

# 3. Copiar archivo de entorno
cp .env.example .env

# 4. Ejecutar migraciones
alembic upgrade head

# 5. Iniciar servidor
uvicorn app.main:app --reload --port 8001
```

## Variables de entorno

Ver `.env.example` para todas las variables disponibles. Variables clave:

| Variable | Descripción |
|----------|-------------|
| `DB_HOST` | Host MySQL |
| `DB_NAME` | Nombre de la base de datos |
| `SECRET_KEY` | Clave de firma JWT |
| `APP_STORAGE_DIR` | Directorio de almacenamiento compartido |

## Desarrollo

```bash
# Ejecutar tests
pytest

# Linter
ruff check .

# Frontend (Vite)
npm install
npm run dev
```
