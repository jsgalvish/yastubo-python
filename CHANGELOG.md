# Changelog

## [Fase 1] - 2026-03-10

### Estructura inicial del proyecto

Creación de la estructura de carpetas 1:1 con el monolito PHP (`gfa-emisiones`).

#### Agregado
- Estructura completa de `app/` espejando `app/` de PHP
  - `casts/`, `console/commands/`, `exceptions/`
  - `http/controllers/` (admin, auth, dev), `http/middleware/`, `http/requests/`
  - `models/concerns/`, `notifications/`, `observers/`, `policies/`, `providers/`
  - `services/` (business_units, capitated, config, ip_country, pdf, regalias, template_render, uploaded_file)
  - `support/helpers/`
- `config/` — módulos de configuración
- `database/migrations/` y `database/factories/`
- `public/` — assets estáticos
- `resources/` — css, js (Vue 3), lang (en/es), views (Jinja2)
  - Estructura de vistas espejando PHP: admin, customer, dev, emails, layouts, partials, pdf, public
- `routes/` — admin/auth, admin/public, customer/auth, customer/public, public
- `tests/Feature/` y `tests/Unit/`
- `pyproject.toml` — dependencias del proyecto
- `.env` — variables de entorno (desarrollo local)
- `.gitignore`
- `README.md`
- `app/config.py` — configuración base con pydantic-settings
