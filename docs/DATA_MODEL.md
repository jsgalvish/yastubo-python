# Modelo de datos

Documentacion del modelo de datos del sistema Yastubo. Todos los modelos estan definidos como clases SQLAlchemy 2.0 en `common/models/`.

---

## Diagrama de relaciones

```
+-------------------+       +-------------------+       +-------------------+
|      users        |       |      roles        |       |   permissions     |
|-------------------|       |-------------------|       |-------------------|
| id (PK)           |  M:M  | id (PK)           |  M:M  | id (PK)           |
| realm (enum)      |<----->| name              |<----->| name              |
| email             |       | guard_name        |       | guard_name        |
| password          |       | scope             |       | description       |
| first_name        |       | level             |       +-------------------+
| last_name         |       | label (JSON)      |
| status            |       +-------------------+
| force_pwd_change  |              via model_has_roles
| locale            |              via model_has_permissions
| last_login_at     |              via role_has_permissions
+--------+----------+
         |
    +----+----+-------------------+
    |         |                   |
    v         v                   v
+--------+ +----------+  +--------------+
| staff_ | | customer_|  | password_    |
|profiles| | profiles |  | histories    |
+--------+ +----------+  +--------------+

+-------------------+       +-------------------+
|    companies      |       |  business_units   |
|-------------------|       |-------------------|
| id (PK)           |  1:M  | id (PK)           |
| name              |<----->| parent_id (self)  |  <-- jerarquia recursiva
| short_code        |       | name              |
| email             |       | type              |
| status            |       | status            |
| stripe_customer_id|       | branding (JSON)   |
| branding (JSON)   |       +-------------------+
+--------+----------+              |
         |                    M:M via memberships
    M:M via company_user      (user_id, role_id)
         |
         v
+-------------------+
|    products       |
|-------------------|
| id (PK)           |
| company_id (FK)   |
| product_type      |  enum: plan_regular, plan_capitado
| name (JSON)       |  traducible es/en
| description (JSON)|
| status            |
+--------+----------+
         |
         | 1:M
         v
+-------------------+       +-------------------+
|   plan_versions   |       |    countries      |
|-------------------|       |-------------------|
| id (PK)           |  M:M  | id (PK)           |
| product_id (FK)   |<----->| name (JSON)       |
| name              |       | iso2, iso3        |
| status            |       | continent_code    |
| terms_html        |       | phone_code        |
| public_price      |       | is_active         |
| cost_price        |       +-------------------+
| price_1..4        |              |
| max_entry_age     |         M:M via country_zone
| zone_id (FK)      |              |
+--------+----------+              v
    |    |               +-------------------+
    |    | 1:M           |      zones        |
    |    v               |-------------------|
    | +------------------| id (PK)           |
    | | plan_version_    | name              |
    | | coverages        | description       |
    | |------------------| is_active         |
    | | id (PK)          +-------------------+
    | | plan_version_id  |
    | | coverage_id (FK) |
    | | sort_order       |
    | | value_int/dec/txt|
    | +------------------+
    |
    | 1:M
    v
+-------------------------+
| plan_version_age_       |
| surcharges              |
|-------------------------|
| id (PK)                 |
| plan_version_id (FK)    |
| min_age, max_age        |
| percent, amount         |
+-------------------------+

+-------------------+       +-------------------+
| coverage_         |       |  units_of_        |
| categories        |  1:M  |  measure          |
|-------------------|<----->|-------------------|
| id (PK)           |       | id (PK)           |
| name              |       | name (JSON)       |
| status            |       | measure_type      |
| sort_order        |       | abbreviation      |
+-------------------+       +-------------------+
         |
         | 1:M
         v
+-------------------+
|    coverages      |
|-------------------|
| id (PK)           |
| category_id (FK)  |
| unit_id (FK)      |
| name (JSON)       |
| description (JSON)|
| status            |
| sort_order        |
+-------------------+

+------------------------------+       +----------------------------+
| capitados_product_insureds   |       | capitados_contracts        |
|------------------------------|       |----------------------------|
| id (PK)                     |  1:M  | id (PK)                    |
| company_id (FK)             |<----->| uuid (auto)                |
| product_id (FK)             |       | company_id (FK)            |
| document_number             |       | product_id (FK)            |
| full_name                   |       | person_id (FK)             |
| sex                         |       | status (enum)              |
| residence_country_id (FK)   |       | entry_date                 |
| repatriation_country_id(FK) |       | valid_until                |
| age_reported                |       | entry_age                  |
| status                      |       +----------------------------+
+------------------------------+               |
                                          1:M   |
                                               v
                                +----------------------------+
                                | capitados_monthly_records  |
                                |----------------------------|
                                | id (PK)                    |
                                | contract_id (FK)           |
                                | coverage_month             |
                                | plan_version_id (FK)       |
                                | price_base, price_final    |
                                | age_surcharge_percent      |
                                | status                     |
                                +----------------------------+

+----------------------------+       +----------------------------+
| capitados_batch_logs       |       | capitados_batch_item_logs  |
|----------------------------|  1:M  |----------------------------|
| id (PK)                   |<----->| id (PK)                    |
| company_id (FK)           |       | batch_log_id (FK)          |
| coverage_month            |       | person_id (FK)             |
| source (excel)            |       | status                     |
| status (enum)             |       | error messages             |
| total_rows, applied, etc. |       +----------------------------+
+----------------------------+

+-------------------+       +-------------------+
|    templates      |  1:M  | template_versions |
|-------------------|<----->|-------------------|
| id (PK)           |       | id (PK)           |
| name              |       | template_id (FK)  |
| slug (unique)     |       | version           |
| type (html/pdf)   |       | content           |
| test_data_json    |       | is_active         |
| active_version_id |       +-------------------+
+-------------------+

+-------------------+       +-------------------+
|      files        |       |    audit_logs     |
|-------------------|       |-------------------|
| id (PK)           |       | id (PK)           |
| uuid (auto)       |       | action            |
| disk              |       | context_json      |
| path              |       | target_user_id    |
| original_name     |       | performed_by_id   |
| mime_type         |       | created_at        |
| size              |       +-------------------+
| uploaded_by       |
| meta (JSON)       |
+-------------------+

+-------------------+       +-------------------+
|    regalias       |       |  subscriptions    |
|-------------------|       |-------------------|
| id (PK)           |       | id (PK)           |
| source_type       |       | (Stripe fields)   |
| source_id         |       +-------------------+
| beneficiary_id    |
| commission_pct    |
+-------------------+
```

---

## Detalle de modelos

### Usuarios y autenticacion

#### User (`users`)
| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | Integer PK | Identificador unico |
| realm | Enum (admin, customer) | Tipo de usuario |
| email | String (unique) | Email del usuario |
| password | String | Hash bcrypt ($2y$ compatible con PHP) |
| first_name | String | Nombre |
| last_name | String | Apellido |
| status | Enum (active, suspended, locked) | Estado de la cuenta |
| force_password_change | Boolean | Requiere cambio de password |
| locale | String | Idioma preferido (es/en/pt) |
| timezone | String | Zona horaria |
| last_login_at | DateTime | Ultimo inicio de sesion |
| email_verified_at | DateTime | Fecha de verificacion de email |

**Relaciones**: StaffProfile (1:1), CustomerProfile (1:1), PasswordHistory (1:M), CompanyUser (M:M), BusinessUnitMembership (M:M), AuditLog (1:M)

#### StaffProfile (`staff_profiles`)
| Campo | Tipo | Descripcion |
|-------|------|-------------|
| user_id | Integer PK/FK | Referencia al usuario |
| work_phone | String | Telefono de trabajo |
| commission_regular_first_year_pct | Decimal | Comision primer anio |
| commission_regular_renewal_pct | Decimal | Comision renovacion |
| commission_capitados_pct | Decimal | Comision capitados |

#### CustomerProfile (`customer_profiles`)
| Campo | Tipo | Descripcion |
|-------|------|-------------|
| user_id | Integer PK/FK | Referencia al usuario |
| doc_type | String | Tipo de documento |
| doc_number | String | Numero de documento |
| birth_date | Date | Fecha de nacimiento |
| gender | String | Genero |
| mobile_e164 | String | Telefono movil (formato E.164) |
| home_address_json | JSON | Direccion del hogar |
| billing_address_json | JSON | Direccion de facturacion |

---

### RBAC (Control de acceso basado en roles)

#### Role (`roles`)
| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | Integer PK | Identificador unico |
| name | String | Nombre interno del rol |
| guard_name | String | Scope: admin o customer |
| scope | String | system o unit |
| level | Integer | Nivel jerarquico |
| label | JSON | Etiqueta traducible (es/en) |

#### Permission (`permissions`)
| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | Integer PK | Identificador unico |
| name | String | Nombre del permiso |
| guard_name | String | Scope: admin o customer |
| description | String | Descripcion opcional |

**Tablas pivot**:
- `role_has_permissions` — M:M entre roles y permisos
- `model_has_roles` — M:M entre usuarios y roles (polimorfismo)
- `model_has_permissions` — M:M entre usuarios y permisos directos

---

### Empresas y unidades de negocio

#### Company (`companies`)
| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | Integer PK | Identificador unico |
| name | String | Nombre de la empresa |
| short_code | String | Codigo corto |
| email | String | Email de contacto |
| phone | String | Telefono |
| status | Enum | active, inactive, archived |
| stripe_customer_id | String | ID de cliente en Stripe |
| pdf_template_id | Integer FK | Plantilla PDF por defecto |
| branding | JSON | Logo, colores |

#### BusinessUnit (`business_units`)
| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | Integer PK | Identificador unico |
| parent_id | Integer FK (self) | Padre (estructura jerarquica) |
| name | String | Nombre |
| type | String | Tipo de unidad |
| status | String | Estado |
| branding | JSON | Branding personalizado |

**Metodo**: `ancestor_chain()` — retorna [root, ..., parent, self]

---

### Productos y planes

#### Product (`products`)
| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | Integer PK | Identificador unico |
| company_id | Integer FK | Empresa propietaria |
| product_type | Enum | plan_regular, plan_capitado |
| name | JSON | Nombre traducible (es/en) |
| description | JSON | Descripcion traducible |
| status | String | Estado del producto |

#### PlanVersion (`plan_versions`)
| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | Integer PK | Identificador unico |
| product_id | Integer FK | Producto padre |
| name | String | Nombre de la version |
| status | Enum | inactive, active, archived |
| terms_html | Text | Terminos y condiciones HTML |
| public_price | Decimal | Precio publico |
| cost_price | Decimal | Precio de costo |
| price_1..4 | Decimal | Precios adicionales |
| max_entry_age | Integer | Edad maxima de ingreso |
| max_renewal_age | Integer | Edad maxima de renovacion |

---

### Capitados

#### CapitatedContract (`capitados_contracts`)
| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id | Integer PK | Identificador unico |
| uuid | String (auto) | UUID publico |
| company_id | Integer FK | Empresa |
| product_id | Integer FK | Producto |
| person_id | Integer FK | Persona asegurada |
| status | Enum | active, expired, voided, rolled_back |
| entry_date | Date | Fecha de ingreso |
| valid_until | Date | Fecha de vencimiento |
| entry_age | Integer | Edad al ingreso |

---

### Mixins compartidos

#### TimestampMixin
Agrega automaticamente:
- `created_at` — DateTime con server_default
- `updated_at` — DateTime con onupdate

#### SoftDeleteMixin
Agrega:
- `deleted_at` — DateTime nullable (NULL = no eliminado)

#### HasTranslatableJson
Metodos helper para campos JSON con formato `{"es": "...", "en": "..."}`:
- `get_translation(field, locale)` — obtener traduccion
- `set_translation(field, locale, value)` — establecer traduccion

#### HasDirectory
Tracking automatico de estructura de directorios para archivos asociados al modelo.
