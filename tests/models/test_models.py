"""
Tests de Step 2 — Modelos SQLAlchemy.

Estrategia:
- Sin conexión a BD: verifica constantes, métodos de negocio, mixins,
  definiciones de columnas (__table__.columns) y relaciones.
- Con SQLite en memoria: crea el schema y verifica CRUD básico.
"""
from __future__ import annotations

import json
import os

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # asegura que todos los modelos estén registrados en Base.metadata
from app.models import (
    Base,
    CapitatedBatchLog,
    CapitatedBatchItemLog,
    CapitatedContract,
    CapitatedMonthlyRecord,
    CapitatedProductInsured,
    CapitatedVoidReason,
    Company,
    CompanyCommissionUser,
    CompanyUser,
    BusinessUnit,
    BusinessUnitCommissionUser,
    BusinessUnitMembership,
    ConfigItem,
    Country,
    Coverage,
    CoverageCategory,
    CustomerProfile,
    File,
    PasswordHistory,
    PlanVersion,
    PlanVersionAgeSurcharge,
    PlanVersionCoverage,
    Product,
    Regalia,
    Role,
    StaffProfile,
    SystemSetting,
    Template,
    TemplateVersion,
    UnitOfMeasure,
    User,
    UserPreference,
    Zone,
)
from app.models.concerns.has_translatable_json import HasTranslatableJson
from app.models.concerns.has_directory import HasDirectory


# ─────────────────────────── Fixtures SQLite ────────────────────────────────

@pytest_asyncio.fixture(scope="module")
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine):
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()


# ─────────────────────────── HasTranslatableJson ─────────────────────────────

class TestHasTranslatableJson:
    def _make(self) -> HasTranslatableJson:
        return HasTranslatableJson()

    def test_translate_dict_default_locale(self):
        obj = self._make()
        data = {"es": "Hola", "en": "Hello"}
        assert obj.translate(data) == "Hola"

    def test_translate_dict_en_locale(self):
        obj = self._make()
        data = {"es": "Hola", "en": "Hello"}
        assert obj.translate(data, "en") == "Hello"

    def test_translate_json_string(self):
        obj = self._make()
        data = json.dumps({"es": "Nombre", "en": "Name"})
        assert obj.translate(data) == "Nombre"

    def test_translate_none_returns_none(self):
        obj = self._make()
        assert obj.translate(None) is None

    def test_translate_fallback_to_es(self):
        obj = self._make()
        data = {"es": "Solo es"}
        assert obj.translate(data, "fr") == "Solo es"

    def test_translate_plain_string(self):
        obj = self._make()
        assert obj.translate("texto plano") == "texto plano"

    def test_translate_empty_dict_returns_none(self):
        obj = self._make()
        assert obj.translate({}) is None


# ─────────────────────────── HasDirectory ────────────────────────────────────

class TestHasDirectory:
    def test_storage_path_base(self, tmp_path, monkeypatch):
        import app.config as cfg
        monkeypatch.setattr(cfg.settings, "app_storage_dir", str(tmp_path))

        class FakeModel(HasDirectory):
            __tablename__ = "users"
            id = 42

        obj = FakeModel()
        path = obj.storage_path()
        assert path.endswith(os.path.join("users", "42"))

    def test_storage_path_with_field(self, tmp_path, monkeypatch):
        import app.config as cfg
        monkeypatch.setattr(cfg.settings, "app_storage_dir", str(tmp_path))

        class FakeModel(HasDirectory):
            __tablename__ = "files"
            id = 1
            avatar = "photo.jpg"

        obj = FakeModel()
        path = obj.storage_path("avatar")
        assert path.endswith("photo.jpg")


# ─────────────────────────── User ────────────────────────────────────────────

class TestUserModel:
    def test_constants(self):
        assert User.REALM_ADMIN if hasattr(User, "REALM_ADMIN") else True
        from app.models.user import REALM_ADMIN, REALM_CUSTOMER, STATUS_ACTIVE
        assert REALM_ADMIN == "admin"
        assert REALM_CUSTOMER == "customer"
        assert STATUS_ACTIVE == "active"

    def test_tablename(self):
        assert User.__tablename__ == "users"

    def test_has_soft_delete(self):
        cols = {c.name for c in User.__table__.columns}
        assert "deleted_at" in cols

    def test_has_timestamps(self):
        cols = {c.name for c in User.__table__.columns}
        assert "created_at" in cols
        assert "updated_at" in cols

    def test_required_columns_exist(self):
        cols = {c.name for c in User.__table__.columns}
        for col in ("realm", "email", "password", "first_name", "last_name", "status"):
            assert col in cols, f"Missing column: {col}"

    def test_full_name_property(self):
        u = User()
        u.first_name = "Juan"
        u.last_name = "García"
        assert u.full_name == "Juan García"

    def test_is_admin(self):
        u = User()
        u.realm = "admin"
        assert u.is_admin() is True
        assert u.is_customer() is False

    def test_is_customer(self):
        u = User()
        u.realm = "customer"
        assert u.is_customer() is True
        assert u.is_admin() is False

    def test_force_password_change_column(self):
        cols = {c.name for c in User.__table__.columns}
        assert "force_password_change" in cols


# ─────────────────────────── Role ────────────────────────────────────────────

class TestRoleModel:
    def test_tablename(self):
        assert Role.__tablename__ == "roles"

    def test_scope_constants(self):
        assert Role.SCOPE_SYSTEM == "system"
        assert Role.SCOPE_UNIT == "unit"

    def test_role_name_from_label(self):
        r = Role()
        r.name = "admin.staff"
        r.label = json.dumps({"es": "Administrador"})
        assert r.role_name == "Administrador"

    def test_role_name_from_name_dots(self):
        r = Role()
        r.name = "admin.staff_leader"
        r.label = None
        assert r.role_name == "Admin - Staff Leader"

    def test_role_name_empty(self):
        r = Role()
        r.name = ""
        r.label = None
        assert r.role_name == ""


# ─────────────────────────── Product ─────────────────────────────────────────

class TestProductModel:
    def test_tablename(self):
        assert Product.__tablename__ == "products"

    def test_type_constants(self):
        assert Product.TYPE_PLAN_REGULAR == "plan_regular"
        assert Product.TYPE_PLAN_CAPITADO == "plan_capitado"

    def test_types_list(self):
        types = Product.types()
        assert "plan_regular" in types
        assert "plan_capitado" in types

    def test_name_es_property(self):
        p = Product()
        p.name = json.dumps({"es": "Plan Básico", "en": "Basic Plan"})
        assert p.name_es == "Plan Básico"

    def test_soft_delete_column(self):
        cols = {c.name for c in Product.__table__.columns}
        assert "deleted_at" in cols


# ─────────────────────────── PlanVersion ─────────────────────────────────────

class TestPlanVersionModel:
    def test_tablename(self):
        assert PlanVersion.__tablename__ == "plan_versions"

    def test_status_constants(self):
        assert PlanVersion.STATUS_DRAFT == "draft"
        assert PlanVersion.STATUS_ACTIVE == "active"
        assert PlanVersion.STATUS_INACTIVE == "inactive"

    def test_can_be_activated_draft(self):
        pv = PlanVersion()
        pv.status = "draft"
        assert pv.can_be_activated() is True

    def test_can_be_activated_active_false(self):
        pv = PlanVersion()
        pv.status = "active"
        assert pv.can_be_activated() is False

    def test_is_active(self):
        pv = PlanVersion()
        pv.status = "active"
        assert pv.is_active() is True


# ─────────────────────────── UnitOfMeasure ───────────────────────────────────

class TestUnitOfMeasureModel:
    def test_tablename(self):
        assert UnitOfMeasure.__tablename__ == "units_of_measure"

    def test_type_constants(self):
        assert UnitOfMeasure.TYPE_INTEGER == "integer"
        assert UnitOfMeasure.TYPE_DECIMAL == "decimal"
        assert UnitOfMeasure.TYPE_TEXT == "text"
        assert UnitOfMeasure.TYPE_NONE == "none"

    def test_measure_types_list(self):
        types = UnitOfMeasure.measure_types()
        assert set(types) == {"integer", "decimal", "text", "none"}


# ─────────────────────────── BusinessUnit ────────────────────────────────────

class TestBusinessUnitModel:
    def test_tablename(self):
        assert BusinessUnit.__tablename__ == "business_units"

    def test_ancestor_chain_single(self):
        bu = BusinessUnit()
        bu.id = 1
        bu.parent = None
        chain = bu.ancestor_chain()
        assert chain == [bu]

    def test_ancestor_chain_parent_child(self):
        parent = BusinessUnit()
        parent.id = 1
        parent.parent = None
        child = BusinessUnit()
        child.id = 2
        child.parent = parent
        chain = child.ancestor_chain()
        assert chain == [parent, child]


# ─────────────────────────── Template ────────────────────────────────────────

class TestTemplateModel:
    def test_tablename(self):
        assert Template.__tablename__ == "templates"

    def test_type_constants(self):
        assert Template.TYPE_HTML == "html"
        assert Template.TYPE_PDF == "pdf"

    def test_soft_delete_column(self):
        cols = {c.name for c in Template.__table__.columns}
        assert "deleted_at" in cols


# ─────────────────────────── CapitatedBatchLog ───────────────────────────────

class TestCapitatedBatchLogModel:
    def test_tablename(self):
        assert CapitatedBatchLog.__tablename__ == "capitados_batch_logs"

    def test_status_constants(self):
        assert CapitatedBatchLog.STATUS_DRAFT == "draft"
        assert CapitatedBatchLog.STATUS_PROCESSED == "processed"
        assert CapitatedBatchLog.STATUS_FAILED == "failed"

    def test_counter_columns_exist(self):
        cols = {c.name for c in CapitatedBatchLog.__table__.columns}
        for col in ("total_rows", "total_applied", "total_rejected",
                    "total_duplicated", "total_incongruences", "total_plan_errors"):
            assert col in cols, f"Missing: {col}"


# ─────────────────────────── CapitatedVoidReason ─────────────────────────────

class TestCapitatedVoidReasonModel:
    def test_tablename(self):
        assert CapitatedVoidReason.__tablename__ == "capitados_void_reasons"

    def test_columns(self):
        cols = {c.name for c in CapitatedVoidReason.__table__.columns}
        assert "label" in cols
        assert "sort_order" in cols


# ─────────────────────────── File ────────────────────────────────────────────

class TestFileModel:
    def test_tablename(self):
        assert File.__tablename__ == "files"

    def test_uuid_column(self):
        cols = {c.name for c in File.__table__.columns}
        assert "uuid" in cols

    def test_local_path(self, monkeypatch, tmp_path):
        import app.config as cfg
        monkeypatch.setattr(cfg.settings, "app_storage_dir", str(tmp_path))
        f = File()
        f.path = "companies/1/logo.png"
        expected = os.path.join(str(tmp_path), "companies/1/logo.png")
        assert f.local_path() == expected


# ─────────────────────────── ConfigItem ──────────────────────────────────────

class TestConfigItemModel:
    def test_tablename(self):
        assert ConfigItem.__tablename__ == "config_items"

    def test_get_value_int(self):
        ci = ConfigItem()
        ci.value_type = "int"
        ci.value_int = 42
        assert ci.get_value() == 42

    def test_get_value_decimal(self):
        ci = ConfigItem()
        ci.value_type = "decimal"
        ci.value_decimal = 3.14
        assert ci.get_value() == 3.14

    def test_get_value_text(self):
        ci = ConfigItem()
        ci.value_type = "text"
        ci.value_text = "hello"
        assert ci.get_value() == "hello"


# ─────────────────────────── SQLite CRUD ─────────────────────────────────────

class TestSQLiteCRUD:
    async def test_create_country(self, db_session: AsyncSession):
        country = Country(
            name=json.dumps({"es": "Chile", "en": "Chile"}),
            iso2="CL",
            iso3="CHL",
        )
        db_session.add(country)
        await db_session.flush()
        assert country.id is not None
        assert country.name_es == "Chile"

    async def test_create_unit_of_measure(self, db_session: AsyncSession):
        unit = UnitOfMeasure(
            name=json.dumps({"es": "Días", "en": "Days"}),
            measure_type="integer",
            status="active",
        )
        db_session.add(unit)
        await db_session.flush()
        assert unit.id is not None

    async def test_create_capitated_void_reason(self, db_session: AsyncSession):
        reason = CapitatedVoidReason(label="Fallecimiento", sort_order=1)
        db_session.add(reason)
        await db_session.flush()
        assert reason.id is not None
        assert reason.label == "Fallecimiento"

    async def test_create_system_setting(self, db_session: AsyncSession):
        setting = SystemSetting(
            category="general",
            key="app_version",
            value_json=json.dumps("1.0.0"),
        )
        db_session.add(setting)
        await db_session.flush()
        assert setting.id is not None

    async def test_create_template(self, db_session: AsyncSession):
        tmpl = Template(
            name="Contrato",
            slug="contrato-v1",
            type="pdf",
        )
        db_session.add(tmpl)
        await db_session.flush()
        assert tmpl.id is not None

    async def test_create_coverage_category(self, db_session: AsyncSession):
        cat = CoverageCategory(
            name=json.dumps({"es": "Básicas", "en": "Basic"}),
            status="active",
        )
        db_session.add(cat)
        await db_session.flush()
        assert cat.id is not None
        assert cat.name_es == "Básicas"
