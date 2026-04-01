# Catalogo de endpoints

Documentacion completa de los 150+ endpoints del sistema, organizados por microservicio.

> Cada servicio expone documentacion interactiva Swagger UI en `http://localhost:800X/docs`

---

## Modulo A — Auth (puerto 8001)

### Login

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/admin/login` | Login de administrador |
| POST | `/customer/login` | Login de cliente |
| POST | `/admin/logout` | Logout de administrador |
| POST | `/customer/logout` | Logout de cliente |

### Passwords

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/password/policy` | Obtener politica de passwords |
| POST | `/password/check` | Validar password en tiempo real |
| POST | `/admin/password/change` | Cambiar password de admin |
| POST | `/customer/password/change` | Cambiar password de cliente |
| POST | `/admin/password/force` | Forzar cambio de password (admin) |
| POST | `/customer/password/force` | Forzar cambio de password (cliente) |
| POST | `/admin/forgot-password` | Solicitar reset de password (admin) |
| POST | `/admin/reset-password` | Resetear password con token (admin) |
| POST | `/customer/forgot-password` | Solicitar reset de password (cliente) |
| POST | `/customer/reset-password` | Resetear password con token (cliente) |

### Locale

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/customer/locale` | Cambiar idioma del cliente (es/en/pt) |

### Usuarios (Admin)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/users` | Listar usuarios paginados con filtros |
| GET | `/admin/users/search` | Buscar usuarios (autocomplete) |
| POST | `/admin/users` | Crear usuario con password temporal |
| GET | `/admin/users/{user_id}` | Detalle de usuario con roles |
| PUT | `/admin/users/{user_id}` | Actualizar usuario, roles, perfil |
| DELETE | `/admin/users/{user_id}` | Soft-delete de usuario |
| POST | `/admin/users/{user_id}/restore` | Restaurar usuario eliminado |
| PUT | `/admin/users/{user_id}/status` | Cambiar estado del usuario |
| POST | `/admin/users/{user_id}/impersonate` | Suplantar usuario (superadmin) |
| POST | `/admin/impersonate/stop` | Detener suplantacion |
| POST | `/admin/users/{user_id}/sessions/revoke` | Revocar sesiones |
| POST | `/admin/users/{user_id}/send-reset` | Marcar para reset de password |
| POST | `/admin/users/{user_id}/lock` | Bloquear cuenta |
| POST | `/admin/users/{user_id}/unlock` | Desbloquear cuenta |

### ACL (Roles y permisos)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/acl/roles/{guard}/matrix` | Obtener matriz roles/permisos |
| POST | `/admin/acl/roles/{guard}/roles` | Crear rol |
| PUT | `/admin/acl/roles/{guard}/roles/{role_id}` | Actualizar rol |
| POST | `/admin/acl/roles/{guard}/permissions` | Crear permiso |
| PUT | `/admin/acl/roles/{guard}/permissions/{perm_id}` | Actualizar permiso |
| POST | `/admin/acl/roles/{guard}/toggle` | Toggle permiso para rol |

---

## Modulo B — Products (puerto 8002)

### Productos

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/products` | Listar productos |
| POST | `/admin/products` | Crear producto |
| GET | `/admin/products/{product_id}` | Detalle de producto |
| PUT | `/admin/products/{product_id}` | Actualizar producto |

### Versiones de plan

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/products/{pid}/plans` | Listar versiones |
| POST | `/admin/products/{pid}/plans` | Crear version |
| GET | `/admin/products/{pid}/plans/{vid}` | Detalle de version |
| PUT | `/admin/products/{pid}/plans/{vid}` | Actualizar version |
| DELETE | `/admin/products/{pid}/plans/{vid}` | Eliminar version |
| POST | `/admin/products/{pid}/plans/{vid}/clone` | Clonar version |
| GET | `/admin/products/{pid}/plans/{vid}/pdf` | Preview PDF |
| GET | `/admin/products/{pid}/plans/{vid}/terms-html` | Obtener terminos HTML |
| PATCH | `/admin/products/{pid}/plans/{vid}/terms-html` | Actualizar terminos HTML |

### Recargos por edad

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/products/{pid}/plans/{vid}/age-surcharges` | Listar recargos |
| POST | `/admin/products/{pid}/plans/{vid}/age-surcharges` | Crear recargo |
| PATCH | `/admin/products/{pid}/plans/{vid}/age-surcharges/{sid}` | Actualizar recargo |
| DELETE | `/admin/products/{pid}/plans/{vid}/age-surcharges/{sid}` | Eliminar recargo |

### Catalogo de coberturas

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/coverages` | Listar categorias con coberturas |
| POST | `/admin/coverages/categories` | Crear categoria |
| PUT | `/admin/coverages/categories/{cid}` | Actualizar categoria |
| POST | `/admin/coverages/categories/{cid}/archive` | Archivar categoria |
| POST | `/admin/coverages/categories/{cid}/restore` | Restaurar categoria |
| GET | `/admin/coverages/categories/archived` | Listar categorias archivadas |
| POST | `/admin/coverages/categories/{cid}/reorder` | Reordenar coberturas |
| POST | `/admin/coverages/items` | Crear cobertura |
| PUT | `/admin/coverages/items/{cov_id}` | Actualizar cobertura |
| POST | `/admin/coverages/items/{cov_id}/archive` | Archivar cobertura |
| POST | `/admin/coverages/items/{cov_id}/restore` | Restaurar cobertura |
| DELETE | `/admin/coverages/items/{cov_id}` | Eliminar cobertura |
| GET | `/admin/coverages/items/{cov_id}/usages` | Ver usos en versiones de plan |

### Coberturas de version de plan

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/products/{pid}/plans/{vid}/coverages/available` | Coberturas disponibles |
| POST | `/admin/products/{pid}/plans/{vid}/coverages` | Agregar cobertura |
| DELETE | `/admin/products/{pid}/plans/{vid}/coverages/{pvc_id}` | Remover cobertura |
| POST | `/admin/products/{pid}/plans/{vid}/coverages/reorder` | Reordenar |
| PATCH | `/admin/products/{pid}/plans/{vid}/coverages/{pvc_id}` | Actualizar valor |

### Paises

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/countries` | Listar paises |
| POST | `/admin/countries` | Crear pais |
| GET | `/admin/countries/{country_id}` | Detalle de pais |
| PUT | `/admin/countries/{country_id}` | Actualizar pais |
| PUT | `/admin/countries/{country_id}/toggle-active` | Toggle estado activo |

### Zonas

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/zones` | Listar zonas con paises |
| POST | `/admin/zones` | Crear zona |
| GET | `/admin/zones/{zone_id}` | Detalle de zona |
| PUT | `/admin/zones/{zone_id}` | Actualizar zona |
| PUT | `/admin/zones/{zone_id}/toggle-active` | Toggle estado activo |
| GET | `/admin/zones/{zone_id}/countries` | Paises en zona |
| GET | `/admin/zones/{zone_id}/countries/available` | Paises disponibles |
| POST | `/admin/zones/{zone_id}/countries/{country_id}` | Agregar pais a zona |
| DELETE | `/admin/zones/{zone_id}/countries/{country_id}` | Remover pais de zona |

### Paises de version de plan

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/products/{pid}/plans/{vid}/countries` | Listar paises de version |
| POST | `/admin/products/{pid}/plans/{vid}/countries` | Agregar pais |
| POST | `/admin/products/{pid}/plans/{vid}/countries/attach-zone` | Agregar paises de zona |
| PATCH | `/admin/products/{pid}/plans/{vid}/countries/{cid}` | Actualizar precio |
| DELETE | `/admin/products/{pid}/plans/{vid}/countries/{cid}` | Remover pais |
| POST | `/admin/products/{pid}/plans/{vid}/countries/detach-by-zone` | Remover paises de zona |

### Paises de repatriacion

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/products/{pid}/plans/{vid}/repatriation-countries` | Listar paises |
| POST | `/admin/products/{pid}/plans/{vid}/repatriation-countries` | Agregar pais |
| POST | `.../repatriation-countries/attach-zone` | Agregar paises de zona |
| DELETE | `.../repatriation-countries/{cid}` | Remover pais |
| POST | `.../repatriation-countries/detach-by-zone` | Remover paises de zona |

### Configuracion y dashboard

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/dashboard` | Metricas del dashboard |
| GET | `/admin/config` | Listar items de configuracion |
| POST | `/admin/config` | Crear item |
| GET | `/admin/config/{item_id}` | Detalle de item |
| PUT | `/admin/config/{item_id}/definition` | Actualizar definicion |
| PUT | `/admin/config/{item_id}/value` | Actualizar valor |
| DELETE | `/admin/config/{item_id}` | Eliminar item |
| POST | `/admin/config/{item_id}/upload` | Subir archivo a config |
| DELETE | `/admin/config/{item_id}/file` | Eliminar archivo de config |
| POST | `/admin/locale` | Cambiar idioma del admin |

---

## Modulo C — Documents (puerto 8003)

### Archivos (publico)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/files/{uuid}` | Descargar/ver archivo por UUID |
| GET | `/files/temp/{file_id}` | Descargar archivo temporal con firma |

### Plantillas

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/templates` | Listar plantillas |
| POST | `/admin/templates` | Crear plantilla |
| GET | `/admin/templates/{tid}` | Detalle con versiones |
| PATCH | `/admin/templates/{tid}/basic` | Actualizar nombre y slug |
| PATCH | `/admin/templates/{tid}/test-data` | Actualizar datos de prueba |
| DELETE | `/admin/templates/{tid}` | Soft-delete |
| POST | `/admin/templates/{tid}/clone` | Clonar plantilla |

### Versiones de plantilla

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/admin/templates/{tid}/versions` | Crear version |
| GET | `/admin/templates/{tid}/versions/{vid}` | Detalle de version |
| PATCH | `/admin/templates/{tid}/versions/{vid}/basic` | Actualizar contenido |
| PATCH | `/admin/templates/{tid}/versions/{vid}/test-data` | Actualizar datos de prueba |
| POST | `/admin/templates/{tid}/versions/{vid}/activate` | Activar version |
| POST | `/admin/templates/{tid}/versions/{vid}/deactivate` | Desactivar version |
| POST | `/admin/templates/{tid}/versions/{vid}/clone` | Clonar version |
| DELETE | `/admin/templates/{tid}/versions/{vid}` | Eliminar version |
| GET | `/admin/templates/{tid}/versions/{vid}/pdf` | Preview PDF |
| GET | `/admin/templates/{tid}/active/pdf` | Preview PDF de version activa |

---

## Modulo D — Capitados (puerto 8004)

### Productos capitados

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/companies/{cid}/capitados` | Listar productos capitados |

### Personas aseguradas

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/companies/{cid}/capitados/persons` | Listar personas paginado |
| GET | `/admin/companies/{cid}/capitados/persons/{pid}` | Detalle con contratos |

### Contratos

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/companies/{cid}/capitados/contracts` | Listar contratos con busqueda |
| GET | `/admin/companies/{cid}/capitados/contracts/{cid}` | Detalle de contrato |

### Empresas

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/companies` | Listar empresas |
| POST | `/admin/companies` | Crear empresa |
| GET | `/admin/companies/{company_id}` | Detalle de empresa |
| PUT | `/admin/companies/{company_id}` | Actualizar empresa |

### Unidades de negocio

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/business-units` | Listar unidades de negocio |
| POST | `/admin/business-units` | Crear unidad de negocio |
| GET | `/admin/business-units/{bu_id}` | Detalle de unidad |
| PUT | `/admin/business-units/{bu_id}` | Actualizar unidad |

### Regalias

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/regalias` | Listar regalias |
| POST | `/admin/regalias` | Crear regalia |
| PUT | `/admin/regalias/{regalia_id}` | Actualizar regalia |
| DELETE | `/admin/regalias/{regalia_id}` | Eliminar regalia |

---

## Modulo E — Audit (puerto 8005)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/audit/actions` | Listar acciones de auditoria disponibles |
| GET | `/admin/audit` | Listar logs de auditoria paginados con filtros |

---

## Modulo F — Billing (puerto 8006)

### Suscripciones (cliente)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/customer/subscription/status` | Estado de suscripcion actual |
| POST | `/customer/subscription/create` | Crear suscripcion en Stripe |
| POST | `/customer/subscription/checkout` | Crear sesion de Stripe Checkout |
| POST | `/customer/subscription/sync` | Sincronizar estado con Stripe |
| POST | `/customer/subscription/cancel` | Cancelar suscripcion |

### Suscripciones (admin)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/subscriptions` | Listar suscripciones paginadas |
| GET | `/admin/subscriptions/stats` | Metricas de suscripciones |

### Stripe Connect

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/admin/connect/accounts` | Crear cuenta Express |
| GET | `/admin/connect/accounts` | Listar cuentas Express |

### CRM (Zoho)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/admin/crm/sync-log` | Logs de sincronizacion Zoho |
| GET | `/admin/crm/dashboard` | Dashboard de CRM sync |

### Webhooks

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/webhooks/stripe` | Receptor de webhooks de Stripe |

---

## Modulo G — Chatbot (puerto 8007)

> Protegido con header `X-Chatbot-Api-Key`

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/chatbot/client` | Buscar cliente por documento |
| POST | `/chatbot/reset-password` | Enviar email de reset de password |

---

## Endpoints comunes (todos los servicios)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | Metricas Prometheus |
