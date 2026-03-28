"""
Modelos SQLAlchemy 2.0 — espejo 1:1 de app/Models de PHP.

Importar desde aquí para garantizar que todas las tablas
estén registradas en Base.metadata antes de crear el schema.
"""

from common.models.base import Base, SoftDeleteMixin, TimestampMixin
from common.models.concerns.has_directory import HasDirectory
from common.models.concerns.has_translatable_json import HasTranslatableJson

# ── Usuarios y perfiles ───────────────────────────────────────────────────────
from common.models.user import User
from common.models.staff_profile import StaffProfile
from common.models.customer_profile import CustomerProfile
from common.models.password_history import PasswordHistory
from common.models.user_preference import UserPreference

# ── Roles y permisos ──────────────────────────────────────────────────────────
from common.models.role import Role
from common.models.permission import Permission, model_has_roles, model_has_permissions, role_has_permissions

# ── Empresa ───────────────────────────────────────────────────────────────────
from common.models.company import Company
from common.models.company_user import CompanyUser
from common.models.company_commission_user import CompanyCommissionUser

# ── Unidades de negocio ───────────────────────────────────────────────────────
from common.models.business_unit import BusinessUnit
from common.models.business_unit_membership import BusinessUnitMembership
from common.models.business_unit_commission_user import BusinessUnitCommissionUser

# ── Catálogo geográfico ───────────────────────────────────────────────────────
from common.models.country import Country
from common.models.zone import Zone

# ── Productos y planes ────────────────────────────────────────────────────────
from common.models.product import Product
from common.models.plan_version import PlanVersion, plan_version_countries, plan_version_repatriation_countries
from common.models.plan_version_coverage import PlanVersionCoverage
from common.models.plan_version_age_surcharge import PlanVersionAgeSurcharge

# ── Coberturas ────────────────────────────────────────────────────────────────
from common.models.coverage_category import CoverageCategory
from common.models.coverage import Coverage
from common.models.unit_of_measure import UnitOfMeasure

# ── Archivos y plantillas ─────────────────────────────────────────────────────
from common.models.file import File
from common.models.template import Template
from common.models.template_version import TemplateVersion

# ── Configuración ─────────────────────────────────────────────────────────────
from common.models.config_item import ConfigItem
from common.models.system_setting import SystemSetting

# ── Capitados ─────────────────────────────────────────────────────────────────
from common.models.capitated_product_insured import CapitatedProductInsured
from common.models.capitated_contract import CapitatedContract
from common.models.capitated_monthly_record import CapitatedMonthlyRecord
from common.models.capitated_batch_log import CapitatedBatchLog
from common.models.capitated_batch_item_log import CapitatedBatchItemLog
from common.models.capitated_void_reason import CapitatedVoidReason

# ── Otros ─────────────────────────────────────────────────────────────────────
from common.models.audit_log import AuditLog
from common.models.regalia import Regalia

__all__ = [
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
