"""
Modelos SQLAlchemy 2.0 — espejo 1:1 de app/Models de PHP.

Importar desde aquí para garantizar que todas las tablas
estén registradas en Base.metadata antes de crear el schema.
"""

# ── Otros ─────────────────────────────────────────────────────────────────────
from app.models.audit_log import AuditLog
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

# ── Unidades de negocio ───────────────────────────────────────────────────────
from app.models.business_unit import BusinessUnit
from app.models.business_unit_commission_user import BusinessUnitCommissionUser
from app.models.business_unit_membership import BusinessUnitMembership
from app.models.capitated_batch_item_log import CapitatedBatchItemLog
from app.models.capitated_batch_log import CapitatedBatchLog
from app.models.capitated_contract import CapitatedContract
from app.models.capitated_monthly_record import CapitatedMonthlyRecord

# ── Capitados ─────────────────────────────────────────────────────────────────
from app.models.capitated_product_insured import CapitatedProductInsured
from app.models.capitated_void_reason import CapitatedVoidReason

# ── Empresa ───────────────────────────────────────────────────────────────────
from app.models.company import Company
from app.models.company_commission_user import CompanyCommissionUser
from app.models.company_user import CompanyUser
from app.models.concerns.has_directory import HasDirectory
from app.models.concerns.has_translatable_json import HasTranslatableJson

# ── Configuración ─────────────────────────────────────────────────────────────
from app.models.config_item import ConfigItem

# ── Catálogo geográfico ───────────────────────────────────────────────────────
from app.models.country import Country
from app.models.coverage import Coverage

# ── Coberturas ────────────────────────────────────────────────────────────────
from app.models.coverage_category import CoverageCategory
from app.models.customer_profile import CustomerProfile

# ── Archivos y plantillas ─────────────────────────────────────────────────────
from app.models.file import File
from app.models.password_history import PasswordHistory
from app.models.permission import (
    Permission,
    model_has_permissions,
    model_has_roles,
    role_has_permissions,
)
from app.models.plan_version import (
    PlanVersion,
    plan_version_countries,
    plan_version_repatriation_countries,
)
from app.models.plan_version_age_surcharge import PlanVersionAgeSurcharge
from app.models.plan_version_coverage import PlanVersionCoverage

# ── Productos y planes ────────────────────────────────────────────────────────
from app.models.product import Product
from app.models.regalia import Regalia

# ── Roles y permisos ──────────────────────────────────────────────────────────
from app.models.role import Role
from app.models.staff_profile import StaffProfile
from app.models.system_setting import SystemSetting
from app.models.template import Template
from app.models.template_version import TemplateVersion
from app.models.unit_of_measure import UnitOfMeasure

# ── Usuarios y perfiles ───────────────────────────────────────────────────────
from app.models.user import User
from app.models.user_preference import UserPreference
from app.models.zone import Zone

__all__ = [  # noqa: RUF022 — grouped by domain, not alphabetically
    # Base
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    "HasDirectory",
    "HasTranslatableJson",
    # Usuarios
    "User",
    "StaffProfile",
    "CustomerProfile",
    "PasswordHistory",
    "UserPreference",
    # Roles y permisos
    "Role",
    "Permission",
    "model_has_roles",
    "model_has_permissions",
    "role_has_permissions",
    # Empresa
    "Company",
    "CompanyUser",
    "CompanyCommissionUser",
    # Unidades de negocio
    "BusinessUnit",
    "BusinessUnitMembership",
    "BusinessUnitCommissionUser",
    # Catálogo
    "Country",
    "Zone",
    # Productos y planes
    "Product",
    "PlanVersion",
    "plan_version_countries",
    "plan_version_repatriation_countries",
    "PlanVersionCoverage",
    "PlanVersionAgeSurcharge",
    # Coberturas
    "CoverageCategory",
    "Coverage",
    "UnitOfMeasure",
    # Archivos y plantillas
    "File",
    "Template",
    "TemplateVersion",
    # Configuración
    "ConfigItem",
    "SystemSetting",
    # Capitados
    "CapitatedProductInsured",
    "CapitatedContract",
    "CapitatedMonthlyRecord",
    "CapitatedBatchLog",
    "CapitatedBatchItemLog",
    "CapitatedVoidReason",
    # Otros
    "AuditLog",
    "Regalia",
]
