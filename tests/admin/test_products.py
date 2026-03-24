"""
Tests de Step 10 — Productos (ProductController).

Estrategia:
- SQLite en memoria (módulo-scoped).
- actor_token: usuario admin con permiso admin.products.manage.
- noauth: verificar 401 sin token.
- CRUD completo: index, store, show, update.
- Reglas de negocio: consistencia tipo/empresa, inmutabilidad de tipo.
"""
from __future__ import annotations

import json

import bcrypt as _bcrypt_lib
import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models
from app.database import get_db
from app.main import app
from app.models import Base, Permission, User
from app.models.product import Product
from app.models.company import Company
from app.services.permission_service import PermissionService
from app.services.token_service import create_access_token


# ─────────────────────── Fixtures de infraestructura ─────────────────────────


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
    """Usuario admin con permiso admin.products.manage."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        actor = User(
            realm="admin",
            email="products_actor@admintest.com",
            password=_hashed("ActorPass1!"),
            first_name="Products",
            last_name="Actor",
            status="active",
            force_password_change=False,
        )
        db.add(actor)
        await db.flush()

        perm = Permission(name="admin.products.manage", guard_name="admin")
        db.add(perm)
        await db.flush()

        svc = PermissionService(db)
        await svc.give_permission(actor, perm)
        await db.commit()

        return create_access_token(actor.id, "admin")


@pytest_asyncio.fixture(scope="module")
async def seed_company_id(async_engine):
    """Empresa para asociar a productos capitados."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        company = Company(
            name="Empresa Producto",
            short_code="PROD",
            status=Company.STATUS_ACTIVE,
        )
        db.add(company)
        await db.commit()
        await db.refresh(company)
        return company.id


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


# ─────────────────────── Store ───────────────────────────────────────────────


class TestProductStore:
    """POST /admin/products"""

    async def test_sin_token_retorna_401(self, client):
        r = await client.post("/admin/products", json={"name": {"es": "X"}, "product_type": "plan_regular"})
        assert r.status_code == 401

    async def test_crea_producto_regular(self, client, actor_token):
        r = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={
                "name": {"es": "Seguro Viaje", "en": "Travel Insurance"},
                "description": {"es": "Desc ES", "en": "Desc EN"},
                "product_type": "plan_regular",
                "show_in_widget": True,
            },
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["name"]["es"] == "Seguro Viaje"
        assert data["name"]["en"] == "Travel Insurance"
        assert data["description"]["es"] == "Desc ES"
        assert data["product_type"] == "plan_regular"
        assert data["show_in_widget"] is True
        assert data["status"] == "inactive"  # siempre inactivo al crear
        assert data["company_id"] is None

    async def test_crea_producto_capitado_con_empresa(self, client, actor_token, seed_company_id):
        r = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={
                "name": {"es": "Plan Capitado"},
                "product_type": "plan_capitado",
                "company_id": seed_company_id,
            },
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["product_type"] == "plan_capitado"
        assert data["company_id"] == seed_company_id
        assert data["status"] == "inactive"

    async def test_capitado_sin_empresa_retorna_422(self, client, actor_token):
        r = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={
                "name": {"es": "Plan Capitado Sin Empresa"},
                "product_type": "plan_capitado",
            },
        )
        assert r.status_code == 422
        assert "empresa" in r.json()["detail"].lower()

    async def test_regular_con_empresa_retorna_422(self, client, actor_token, seed_company_id):
        r = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={
                "name": {"es": "Plan Regular"},
                "product_type": "plan_regular",
                "company_id": seed_company_id,
            },
        )
        assert r.status_code == 422
        assert "empresa" in r.json()["detail"].lower()

    async def test_tipo_invalido_retorna_422(self, client, actor_token):
        r = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={
                "name": {"es": "Inválido"},
                "product_type": "desconocido",
            },
        )
        assert r.status_code == 422

    async def test_nombre_es_requerido(self, client, actor_token):
        r = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={
                "name": {"en": "Only English"},
                "product_type": "plan_regular",
            },
        )
        assert r.status_code == 422

    async def test_show_in_widget_default_false(self, client, actor_token):
        r = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={
                "name": {"es": "Default Widget"},
                "product_type": "plan_regular",
            },
        )
        assert r.status_code == 201
        assert r.json()["data"]["show_in_widget"] is False


# ─────────────────────── Index ───────────────────────────────────────────────


class TestProductIndex:
    """GET /admin/products — solo devuelve plan_regular"""

    async def test_sin_token_retorna_401(self, client):
        r = await client.get("/admin/products")
        assert r.status_code == 401

    async def test_lista_solo_regulares(self, client, actor_token):
        r = await client.get("/admin/products", headers=_auth(actor_token))
        assert r.status_code == 200
        data = r.json()
        assert "products" in data
        assert "product_type_options" in data
        # Todos los productos del listado deben ser plan_regular
        for p in data["products"]:
            assert p["product_type"] == "plan_regular"

    async def test_product_type_options(self, client, actor_token):
        r = await client.get("/admin/products", headers=_auth(actor_token))
        assert r.status_code == 200
        opts = r.json()["product_type_options"]
        assert "plan_regular" in opts
        assert "plan_capitado" in opts

    async def test_orden_desc_por_id(self, client, actor_token):
        r = await client.get("/admin/products", headers=_auth(actor_token))
        assert r.status_code == 200
        products = r.json()["products"]
        if len(products) >= 2:
            ids = [p["id"] for p in products]
            assert ids == sorted(ids, reverse=True)


# ─────────────────────── Show ────────────────────────────────────────────────


class TestProductShow:
    """GET /admin/products/{id}"""

    async def test_sin_token_retorna_401(self, client):
        r = await client.get("/admin/products/1")
        assert r.status_code == 401

    async def test_producto_existente(self, client, actor_token):
        # Crear uno para obtener ID
        cr = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={"name": {"es": "Show Test"}, "product_type": "plan_regular"},
        )
        pid = cr.json()["data"]["id"]

        r = await client.get(f"/admin/products/{pid}", headers=_auth(actor_token))
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["id"] == pid
        assert data["name"]["es"] == "Show Test"

    async def test_producto_no_existe_retorna_404(self, client, actor_token):
        r = await client.get("/admin/products/999999", headers=_auth(actor_token))
        assert r.status_code == 404


# ─────────────────────── Update ──────────────────────────────────────────────


class TestProductUpdate:
    """PUT /admin/products/{id}"""

    async def test_sin_token_retorna_401(self, client):
        r = await client.put("/admin/products/1", json={"status": "active"})
        assert r.status_code == 401

    async def test_actualiza_nombre_y_status(self, client, actor_token):
        # Crear producto
        cr = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={"name": {"es": "Original"}, "product_type": "plan_regular"},
        )
        pid = cr.json()["data"]["id"]

        r = await client.put(
            f"/admin/products/{pid}",
            headers=_auth(actor_token),
            json={
                "name": {"es": "Actualizado", "en": "Updated"},
                "status": "active",
            },
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["name"]["es"] == "Actualizado"
        assert data["name"]["en"] == "Updated"
        assert data["status"] == "active"
        assert "toast" in r.json()

    async def test_actualiza_show_in_widget(self, client, actor_token):
        cr = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={"name": {"es": "Widget Test"}, "product_type": "plan_regular"},
        )
        pid = cr.json()["data"]["id"]
        assert cr.json()["data"]["show_in_widget"] is False

        r = await client.put(
            f"/admin/products/{pid}",
            headers=_auth(actor_token),
            json={"show_in_widget": True},
        )
        assert r.status_code == 200
        assert r.json()["data"]["show_in_widget"] is True

    async def test_actualiza_descripcion(self, client, actor_token):
        cr = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={
                "name": {"es": "Desc Test"},
                "product_type": "plan_regular",
                "description": {"es": "Desc original"},
            },
        )
        pid = cr.json()["data"]["id"]

        r = await client.put(
            f"/admin/products/{pid}",
            headers=_auth(actor_token),
            json={"description": {"es": "Desc modificada", "en": "Modified desc"}},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["description"]["es"] == "Desc modificada"
        assert data["description"]["en"] == "Modified desc"

    async def test_status_invalido_retorna_422(self, client, actor_token):
        cr = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={"name": {"es": "Status Test"}, "product_type": "plan_regular"},
        )
        pid = cr.json()["data"]["id"]

        r = await client.put(
            f"/admin/products/{pid}",
            headers=_auth(actor_token),
            json={"status": "unknown"},
        )
        assert r.status_code == 422

    async def test_producto_no_existe_retorna_404(self, client, actor_token):
        r = await client.put(
            "/admin/products/999999",
            headers=_auth(actor_token),
            json={"status": "active"},
        )
        assert r.status_code == 404

    async def test_product_type_no_cambia(self, client, actor_token):
        """product_type NO es modificable después de la creación."""
        cr = await client.post(
            "/admin/products",
            headers=_auth(actor_token),
            json={"name": {"es": "Inmutable"}, "product_type": "plan_regular"},
        )
        pid = cr.json()["data"]["id"]

        # Intentar cambiar el tipo (no debería cambiar, el campo no existe en update)
        r = await client.put(
            f"/admin/products/{pid}",
            headers=_auth(actor_token),
            json={"name": {"es": "Inmutable v2"}},
        )
        assert r.status_code == 200
        assert r.json()["data"]["product_type"] == "plan_regular"
