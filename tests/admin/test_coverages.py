"""
Tests de Step 12 — Coberturas (CoverageCatalog + PlanVersionCoverage).

Estrategia:
- SQLite en memoria (módulo-scoped).
- Dos permisos: admin.coverages.manage y admin.products.manage.
- Catálogo: categorías CRUD + archive/restore, coberturas CRUD + archive/restore/delete.
- PlanVersionCoverage: available, store (idempotente), updateValue, reorder, destroy.
"""
from __future__ import annotations

import json

import bcrypt as _bcrypt_lib
import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models
from app.database import get_db
from app.main import app
from app.models import Base, Permission, User
from app.models.plan_version import PlanVersion
from app.models.product import Product
from app.models.unit_of_measure import UnitOfMeasure
from app.services.permission_service import PermissionService
from app.services.token_service import create_access_token

# ─────────────────────── Fixtures ────────────────────────────────────────────


@pytest_asyncio.fixture(scope="module")
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


def _hashed(pw: str) -> str:
    return _bcrypt_lib.hashpw(pw.encode(), _bcrypt_lib.gensalt()).decode()


@pytest_asyncio.fixture(scope="module")
async def actor_token(async_engine):
    """Usuario admin con ambos permisos."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        actor = User(
            realm="admin",
            email="coverages_actor@admintest.com",
            password=_hashed("ActorPass1!"),
            first_name="Coverages",
            last_name="Actor",
            status="active",
            force_password_change=False,
        )
        db.add(actor)
        await db.flush()

        for pname in ("admin.coverages.manage", "admin.products.manage"):
            perm = Permission(name=pname, guard_name="admin")
            db.add(perm)
            await db.flush()
            svc = PermissionService(db)
            await svc.give_permission(actor, perm)

        await db.commit()
        return create_access_token(actor.id, "admin")


@pytest_asyncio.fixture(scope="module")
async def seed_unit_id(async_engine):
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        unit = UnitOfMeasure(
            name=json.dumps({"es": "Días", "en": "Days"}),
            description=json.dumps({"es": "Unidad de días"}),
            measure_type="integer",
            status="active",
        )
        db.add(unit)
        await db.commit()
        await db.refresh(unit)
        return unit.id


@pytest_asyncio.fixture(scope="module")
async def seed_product_and_version(async_engine):
    """Producto + versión de plan para tests de PlanVersionCoverage."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        product = Product(
            name=json.dumps({"es": "Producto Cobertura"}),
            product_type=Product.TYPE_PLAN_REGULAR,
            status="active",
            show_in_widget=False,
        )
        db.add(product)
        await db.flush()

        version = PlanVersion(
            product_id=product.id,
            name="Versión Cobertura",
            status="inactive",
        )
        db.add(version)
        await db.commit()
        await db.refresh(product)
        await db.refresh(version)
        return product.id, version.id


@pytest_asyncio.fixture
async def client(async_engine):
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ═════════════════════════════════════════════════════════════════════════════
# CATÁLOGO: Categorías
# ═════════════════════════════════════════════════════════════════════════════


class TestCategoryStore:
    async def test_crea_categoria(self, client, actor_token):
        r = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "Médica", "en": "Medical"}},
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["name"]["es"] == "Médica"
        assert data["status"] == "active"
        assert data["sort_order"] is not None

    async def test_sin_token_retorna_401(self, client):
        r = await client.post(
            "/admin/coverages/categories",
            json={"name": {"es": "Nope"}},
        )
        assert r.status_code == 401


class TestCategoryUpdate:
    async def test_actualiza_categoria(self, client, actor_token):
        cr = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "Original"}},
        )
        cid = cr.json()["data"]["id"]

        r = await client.put(
            f"/admin/coverages/categories/{cid}",
            headers=_auth(actor_token),
            json={"name": {"es": "Actualizada", "en": "Updated"}},
        )
        assert r.status_code == 200
        assert r.json()["data"]["name"]["es"] == "Actualizada"


class TestCategoryArchiveRestore:
    async def test_archiva_y_restaura(self, client, actor_token):
        cr = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "Archivable"}},
        )
        cid = cr.json()["data"]["id"]

        # Archivar
        r = await client.post(
            f"/admin/coverages/categories/{cid}/archive",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200

        # Verificar en archivadas
        r2 = await client.get(
            "/admin/coverages/categories/archived",
            headers=_auth(actor_token),
        )
        assert any(c["id"] == cid for c in r2.json()["data"])

        # Restaurar
        r3 = await client.post(
            f"/admin/coverages/categories/{cid}/restore",
            headers=_auth(actor_token),
        )
        assert r3.status_code == 200
        assert r3.json()["data"]["status"] == "active"


# ═════════════════════════════════════════════════════════════════════════════
# CATÁLOGO: Coberturas
# ═════════════════════════════════════════════════════════════════════════════


class TestCoverageStore:
    async def test_crea_cobertura(self, client, actor_token, seed_unit_id):
        # Crear categoría
        cat_r = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "Cat para Coverage"}},
        )
        cat_id = cat_r.json()["data"]["id"]

        r = await client.post(
            "/admin/coverages/items",
            headers=_auth(actor_token),
            json={
                "category_id": cat_id,
                "unit_id": seed_unit_id,
                "name": {"es": "Hospitalización", "en": "Hospitalization"},
            },
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["name"]["es"] == "Hospitalización"
        assert data["unit"]["measure_type"] == "integer"


class TestCoverageUpdate:
    async def test_actualiza_cobertura(self, client, actor_token, seed_unit_id):
        cat_r = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "Cat Update"}},
        )
        cat_id = cat_r.json()["data"]["id"]

        cr = await client.post(
            "/admin/coverages/items",
            headers=_auth(actor_token),
            json={"category_id": cat_id, "unit_id": seed_unit_id, "name": {"es": "Original"}},
        )
        cov_id = cr.json()["data"]["id"]

        r = await client.put(
            f"/admin/coverages/items/{cov_id}",
            headers=_auth(actor_token),
            json={"name": {"es": "Modificada"}},
        )
        assert r.status_code == 200
        assert r.json()["data"]["name"]["es"] == "Modificada"


class TestCoverageArchiveDelete:
    async def test_archiva_y_restaura_cobertura(self, client, actor_token, seed_unit_id):
        cat_r = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "Cat Archive"}},
        )
        cat_id = cat_r.json()["data"]["id"]

        cr = await client.post(
            "/admin/coverages/items",
            headers=_auth(actor_token),
            json={"category_id": cat_id, "unit_id": seed_unit_id, "name": {"es": "Archivable"}},
        )
        cov_id = cr.json()["data"]["id"]

        # Archivar
        r = await client.post(
            f"/admin/coverages/items/{cov_id}/archive",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200

        # Restaurar
        r2 = await client.post(
            f"/admin/coverages/items/{cov_id}/restore",
            headers=_auth(actor_token),
        )
        assert r2.status_code == 200
        assert r2.json()["data"]["status"] == "active"

    async def test_elimina_cobertura_sin_uso(self, client, actor_token, seed_unit_id):
        cat_r = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "Cat Delete"}},
        )
        cat_id = cat_r.json()["data"]["id"]

        cr = await client.post(
            "/admin/coverages/items",
            headers=_auth(actor_token),
            json={"category_id": cat_id, "unit_id": seed_unit_id, "name": {"es": "Borrable"}},
        )
        cov_id = cr.json()["data"]["id"]

        r = await client.delete(
            f"/admin/coverages/items/{cov_id}",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "eliminada" in r.json()["message"].lower()


class TestCatalogIndex:
    async def test_index_retorna_categorias_y_unidades(self, client, actor_token):
        r = await client.get("/admin/coverages", headers=_auth(actor_token))
        assert r.status_code == 200
        data = r.json()
        assert "categories" in data
        assert "units" in data


class TestReorderCoverages:
    async def test_reorder(self, client, actor_token, seed_unit_id):
        cat_r = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "Cat Reorder"}},
        )
        cat_id = cat_r.json()["data"]["id"]

        # Crear dos coberturas
        c1 = await client.post(
            "/admin/coverages/items",
            headers=_auth(actor_token),
            json={"category_id": cat_id, "unit_id": seed_unit_id, "name": {"es": "Cov1"}},
        )
        c2 = await client.post(
            "/admin/coverages/items",
            headers=_auth(actor_token),
            json={"category_id": cat_id, "unit_id": seed_unit_id, "name": {"es": "Cov2"}},
        )
        id1 = c1.json()["data"]["id"]
        id2 = c2.json()["data"]["id"]

        r = await client.post(
            f"/admin/coverages/categories/{cat_id}/reorder",
            headers=_auth(actor_token),
            json={"items": [{"id": id2, "sort_order": 1}, {"id": id1, "sort_order": 2}]},
        )
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# PLAN VERSION COVERAGES
# ═════════════════════════════════════════════════════════════════════════════


class TestPVCoverageAvailable:
    async def test_available(self, client, actor_token, seed_product_and_version):
        pid, vid = seed_product_and_version
        r = await client.get(
            f"/admin/products/{pid}/plans/{vid}/coverages/available",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "data" in r.json()


class TestPVCoverageStore:
    async def test_agrega_cobertura_a_version(self, client, actor_token, seed_unit_id, seed_product_and_version):
        pid, vid = seed_product_and_version

        # Crear categoría + cobertura
        cat_r = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "PV Cat"}},
        )
        cat_id = cat_r.json()["data"]["id"]

        cov_r = await client.post(
            "/admin/coverages/items",
            headers=_auth(actor_token),
            json={"category_id": cat_id, "unit_id": seed_unit_id, "name": {"es": "PV Cov"}},
        )
        cov_id = cov_r.json()["data"]["id"]

        r = await client.post(
            f"/admin/products/{pid}/plans/{vid}/coverages",
            headers=_auth(actor_token),
            json={"coverage_id": cov_id},
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["coverage_id"] == cov_id
        assert data["plan_version_id"] == vid

    async def test_idempotente(self, client, actor_token, seed_unit_id, seed_product_and_version):
        pid, vid = seed_product_and_version

        cat_r = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "Idemp Cat"}},
        )
        cov_r = await client.post(
            "/admin/coverages/items",
            headers=_auth(actor_token),
            json={"category_id": cat_r.json()["data"]["id"], "unit_id": seed_unit_id, "name": {"es": "Idemp Cov"}},
        )
        cov_id = cov_r.json()["data"]["id"]

        r1 = await client.post(
            f"/admin/products/{pid}/plans/{vid}/coverages",
            headers=_auth(actor_token),
            json={"coverage_id": cov_id},
        )
        r2 = await client.post(
            f"/admin/products/{pid}/plans/{vid}/coverages",
            headers=_auth(actor_token),
            json={"coverage_id": cov_id},
        )
        # Mismo ID retornado (idempotente)
        assert r1.json()["data"]["id"] == r2.json()["data"]["id"]


class TestPVCoverageUpdateValue:
    async def test_actualiza_valor(self, client, actor_token, seed_unit_id, seed_product_and_version):
        pid, vid = seed_product_and_version

        cat_r = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "Value Cat"}},
        )
        cov_r = await client.post(
            "/admin/coverages/items",
            headers=_auth(actor_token),
            json={"category_id": cat_r.json()["data"]["id"], "unit_id": seed_unit_id, "name": {"es": "Value Cov"}},
        )
        pvc_r = await client.post(
            f"/admin/products/{pid}/plans/{vid}/coverages",
            headers=_auth(actor_token),
            json={"coverage_id": cov_r.json()["data"]["id"]},
        )
        pvc_id = pvc_r.json()["data"]["id"]

        r = await client.patch(
            f"/admin/products/{pid}/plans/{vid}/coverages/{pvc_id}",
            headers=_auth(actor_token),
            json={"value_int": 30, "notes": {"es": "30 días", "en": "30 days"}},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["value_int"] == 30
        assert data["notes"]["es"] == "30 días"


class TestPVCoverageDestroy:
    async def test_elimina_cobertura_de_version(self, client, actor_token, seed_unit_id, seed_product_and_version):
        pid, vid = seed_product_and_version

        cat_r = await client.post(
            "/admin/coverages/categories",
            headers=_auth(actor_token),
            json={"name": {"es": "Del Cat"}},
        )
        cov_r = await client.post(
            "/admin/coverages/items",
            headers=_auth(actor_token),
            json={"category_id": cat_r.json()["data"]["id"], "unit_id": seed_unit_id, "name": {"es": "Del Cov"}},
        )
        pvc_r = await client.post(
            f"/admin/products/{pid}/plans/{vid}/coverages",
            headers=_auth(actor_token),
            json={"coverage_id": cov_r.json()["data"]["id"]},
        )
        pvc_id = pvc_r.json()["data"]["id"]

        r = await client.delete(
            f"/admin/products/{pid}/plans/{vid}/coverages/{pvc_id}",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "eliminada" in r.json()["message"].lower()
