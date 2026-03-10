"""
Modelos SQLAlchemy 2.0 — espejo 1:1 de app/Models de PHP.

Importar desde aquí para garantizar que todas las tablas
estén registradas en Base.metadata antes de crear el schema.
"""

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.concerns.has_directory import HasDirectory
from app.models.concerns.has_translatable_json import HasTranslatableJson

# ── Usuarios y perfiles ───────────────────────────────────────────────────────
from app.models.user import User
from app.models.staff_profile import StaffProfile
from app.models.customer_profile import CustomerProfile
from app.models.password_history import PasswordHistory
from app.models.user_preference import UserPreference

# ── Roles y permisos ──────────────────────────────────────────────────────────
from app.models.role import Role

# ── Empresa ───────────────────────────────────────────────────────────────────
from app.models.company import Company
from app.models.company_user import CompanyUser
from app.models.company_commission_user import CompanyCommissionUser

# ── Unidades de negocio ───────────────────────────────────────────────────────
from app.models.business_unit import BusinessUnit
from app.models.business_unit_membership import BusinessUnitMembership
from app.models.business_unit_commission_user import BusinessUnitCommissionUser

# ── Catálogo geográfico ───────────────────────────────────────────────────────
from app.models.country import Country
from app.models.zone import Zone

# ── Productos y planes ────────────────────────────────────────────────────────
from app.models.product import Product
from app.models.plan_version import PlanVersion
from app.models.plan_version_coverage import PlanVersionCoverage
from app.models.plan_version_age_surcharge import PlanVersionAgeSurcharge

# ── Coberturas ────────────────────────────────────────────────────────────────
from app.models.coverage_category import CoverageCategory
from app.models.coverage import Coverage
from app.models.unit_of_measure import UnitOfMeasure

# ── Archivos y plantillas ─────────────────────────────────────────────────────
from app.models.file import File
from app.models.template import Template
from app.models.template_version import TemplateVersion

# ── Configuración ─────────────────────────────────────────────────────────────
from app.models.config_item import ConfigItem
from app.models.system_setting import SystemSetting

# ── Capitados ─────────────────────────────────────────────────────────────────
from app.models.capitated_product_insured import CapitatedProductInsured
from app.models.capitated_contract import CapitatedContract
from app.models.capitated_monthly_record import CapitatedMonthlyRecord
from app.models.capitated_batch_log import CapitatedBatchLog
from app.models.capitated_batch_item_log import CapitatedBatchItemLog
from app.models.capitated_void_reason import CapitatedVoidReason

# ── Otros ─────────────────────────────────────────────────────────────────────
from app.models.audit_log import AuditLog
from app.models.regalia import Regalia

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
    # Roles
    "Role",
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
