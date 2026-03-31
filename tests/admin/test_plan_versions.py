"""
Tests de Step 11 — Planes (PlanVersion + AgeSurcharge).

Estrategia:
- SQLite en memoria (módulo-scoped).
- actor_token: usuario admin con permiso admin.products.manage.
- seed_product_id: producto base para asociar versiones.
- CRUD completo: index, store, show, update, destroy, clone.
- Terms HTML: show, update por locale.
- AgeSurcharges: index, store, update, destroy.
- Reglas de negocio: activación desactiva otros, delete solo si deletable.
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
from app.models.product import Product
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
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        actor = User(
            realm="admin",
            email="plans_actor@admintest.com",
            password=_hashed("ActorPass1!"),
            first_name="Plans",
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
async def seed_product_id(async_engine):
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        product = Product(
            name=json.dumps({"es": "Producto Plan Test"}, ensure_ascii=False),
            product_type=Product.TYPE_PLAN_REGULAR,
            status="active",
            show_in_widget=False,
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product.id


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


def _url(product_id: int, suffix: str = "") -> str:
    return f"/admin/products/{product_id}/plans{suffix}"


# ─────────────────────── PlanVersion: store ──────────────────────────────────


class TestPlanVersionStore:
    async def test_sin_token_retorna_401(self, client, seed_product_id):
        r = await client.post(_url(seed_product_id), json={"name": "V1"})
        assert r.status_code == 401

    async def test_crea_version(self, client, actor_token, seed_product_id):
        r = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Versión 1"},
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["name"] == "Versión 1"
        assert data["status"] == "inactive"
        assert data["product_id"] == seed_product_id

    async def test_producto_inexistente_retorna_404(self, client, actor_token):
        r = await client.post(
            _url(999999),
            headers=_auth(actor_token),
            json={"name": "Nope"},
        )
        assert r.status_code == 404


# ─────────────────────── PlanVersion: index ──────────────────────────────────


class TestPlanVersionIndex:
    async def test_lista_versiones(self, client, actor_token, seed_product_id):
        r = await client.get(_url(seed_product_id), headers=_auth(actor_token))
        assert r.status_code == 200
        data = r.json()["data"]
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_orden_desc_por_id(self, client, actor_token, seed_product_id):
        # Crear segunda versión
        await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Versión 2"},
        )
        r = await client.get(_url(seed_product_id), headers=_auth(actor_token))
        ids = [v["id"] for v in r.json()["data"]]
        assert ids == sorted(ids, reverse=True)


# ─────────────────────── PlanVersion: show ───────────────────────────────────


class TestPlanVersionShow:
    async def test_muestra_version(self, client, actor_token, seed_product_id):
        # Crear para obtener ID
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Show Test"},
        )
        vid = cr.json()["data"]["id"]

        r = await client.get(_url(seed_product_id, f"/{vid}"), headers=_auth(actor_token))
        assert r.status_code == 200
        assert r.json()["data"]["id"] == vid

    async def test_version_no_existe_retorna_404(self, client, actor_token, seed_product_id):
        r = await client.get(_url(seed_product_id, "/999999"), headers=_auth(actor_token))
        assert r.status_code == 404


# ─────────────────────── PlanVersion: update ─────────────────────────────────


class TestPlanVersionUpdate:
    async def test_actualiza_nombre(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Update Test"},
        )
        vid = cr.json()["data"]["id"]

        r = await client.put(
            _url(seed_product_id, f"/{vid}"),
            headers=_auth(actor_token),
            json={"name": "Updated"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "Updated"
        assert "toast" in r.json()

    async def test_actualiza_precios(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Precios Test"},
        )
        vid = cr.json()["data"]["id"]

        r = await client.put(
            _url(seed_product_id, f"/{vid}"),
            headers=_auth(actor_token),
            json={"price_1": 100.50, "price_2": 200.00},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["price_1"] == 100.50
        assert data["price_2"] == 200.00

    async def test_activar_desactiva_otros(self, client, actor_token, seed_product_id):
        # Crear dos versiones
        cr1 = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Activar A"},
        )
        vid1 = cr1.json()["data"]["id"]

        cr2 = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Activar B"},
        )
        vid2 = cr2.json()["data"]["id"]

        # Activar primera
        await client.put(
            _url(seed_product_id, f"/{vid1}"),
            headers=_auth(actor_token),
            json={"status": "active"},
        )

        # Activar segunda → primera debe quedar inactive
        await client.put(
            _url(seed_product_id, f"/{vid2}"),
            headers=_auth(actor_token),
            json={"status": "active"},
        )

        r1 = await client.get(_url(seed_product_id, f"/{vid1}"), headers=_auth(actor_token))
        r2 = await client.get(_url(seed_product_id, f"/{vid2}"), headers=_auth(actor_token))

        assert r1.json()["data"]["status"] == "inactive"
        assert r2.json()["data"]["status"] == "active"

    async def test_status_invalido_retorna_422(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Bad Status"},
        )
        vid = cr.json()["data"]["id"]

        r = await client.put(
            _url(seed_product_id, f"/{vid}"),
            headers=_auth(actor_token),
            json={"status": "unknown"},
        )
        assert r.status_code == 422


# ─────────────────────── PlanVersion: destroy ────────────────────────────────


class TestPlanVersionDestroy:
    async def test_elimina_version(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Destroy Test"},
        )
        vid = cr.json()["data"]["id"]

        r = await client.delete(_url(seed_product_id, f"/{vid}"), headers=_auth(actor_token))
        assert r.status_code == 200
        assert "eliminada" in r.json()["message"].lower()

        # Verificar que ya no existe
        r2 = await client.get(_url(seed_product_id, f"/{vid}"), headers=_auth(actor_token))
        assert r2.status_code == 404


# ─────────────────────── PlanVersion: clone ──────────────────────────────────


class TestPlanVersionClone:
    async def test_clona_version(self, client, actor_token, seed_product_id):
        # Crear original con datos
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Original"},
        )
        vid = cr.json()["data"]["id"]

        # Actualizar con precios y edades
        await client.put(
            _url(seed_product_id, f"/{vid}"),
            headers=_auth(actor_token),
            json={"price_1": 50.00, "max_entry_age": 75},
        )

        # Clonar
        r = await client.post(
            _url(seed_product_id, f"/{vid}/clone"),
            headers=_auth(actor_token),
            json={"name": "Clonado"},
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["name"] == "Clonado"
        assert data["status"] == "inactive"
        assert data["price_1"] == 50.00
        assert data["max_entry_age"] == 75
        assert data["id"] != vid


# ─────────────────────── Terms HTML ──────────────────────────────────────────


class TestTermsHtml:
    async def test_show_terms_html_vacio(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Terms Test"},
        )
        vid = cr.json()["data"]["id"]

        r = await client.get(
            _url(seed_product_id, f"/{vid}/terms-html"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        terms = r.json()["data"]["terms_html"]
        assert terms["es"] is None
        assert terms["en"] is None

    async def test_update_terms_html_es(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Terms ES"},
        )
        vid = cr.json()["data"]["id"]

        r = await client.patch(
            _url(seed_product_id, f"/{vid}/terms-html"),
            headers=_auth(actor_token),
            json={"locale": "es", "html": "<p>Términos ES</p>"},
        )
        assert r.status_code == 200
        terms = r.json()["data"]["terms_html"]
        assert terms["es"] == "<p>Términos ES</p>"
        assert terms["en"] is None

    async def test_update_terms_html_en_preserva_es(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Terms Both"},
        )
        vid = cr.json()["data"]["id"]

        # Primero ES
        await client.patch(
            _url(seed_product_id, f"/{vid}/terms-html"),
            headers=_auth(actor_token),
            json={"locale": "es", "html": "<p>ES</p>"},
        )

        # Luego EN
        r = await client.patch(
            _url(seed_product_id, f"/{vid}/terms-html"),
            headers=_auth(actor_token),
            json={"locale": "en", "html": "<p>EN</p>"},
        )
        terms = r.json()["data"]["terms_html"]
        assert terms["es"] == "<p>ES</p>"
        assert terms["en"] == "<p>EN</p>"

    async def test_locale_invalido_retorna_422(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Terms Bad Locale"},
        )
        vid = cr.json()["data"]["id"]

        r = await client.patch(
            _url(seed_product_id, f"/{vid}/terms-html"),
            headers=_auth(actor_token),
            json={"locale": "fr", "html": "nope"},
        )
        assert r.status_code == 422


# ─────────────────────── AgeSurcharge ────────────────────────────────────────


class TestAgeSurcharge:
    async def test_crea_surcharge(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Surcharge Test"},
        )
        vid = cr.json()["data"]["id"]

        r = await client.post(
            _url(seed_product_id, f"/{vid}/age-surcharges"),
            headers=_auth(actor_token),
            json={"age_from": 60, "age_to": 70, "surcharge_percent": 15.5},
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["age_from"] == 60
        assert data["age_to"] == 70
        assert data["surcharge_percent"] == 15.5
        assert "toast" in r.json()

    async def test_lista_surcharges(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Surcharge Index"},
        )
        vid = cr.json()["data"]["id"]

        # Crear dos
        await client.post(
            _url(seed_product_id, f"/{vid}/age-surcharges"),
            headers=_auth(actor_token),
            json={"age_from": 70, "age_to": 80, "surcharge_percent": 20},
        )
        await client.post(
            _url(seed_product_id, f"/{vid}/age-surcharges"),
            headers=_auth(actor_token),
            json={"age_from": 80, "age_to": 90, "surcharge_percent": 30},
        )

        r = await client.get(
            _url(seed_product_id, f"/{vid}/age-surcharges"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 2

    async def test_actualiza_surcharge(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Surcharge Update"},
        )
        vid = cr.json()["data"]["id"]

        sr = await client.post(
            _url(seed_product_id, f"/{vid}/age-surcharges"),
            headers=_auth(actor_token),
            json={"age_from": 50, "age_to": 60, "surcharge_percent": 10},
        )
        sid = sr.json()["data"]["id"]

        r = await client.patch(
            _url(seed_product_id, f"/{vid}/age-surcharges/{sid}"),
            headers=_auth(actor_token),
            json={"surcharge_percent": 25.0},
        )
        assert r.status_code == 200
        assert r.json()["data"]["surcharge_percent"] == 25.0

    async def test_elimina_surcharge(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Surcharge Delete"},
        )
        vid = cr.json()["data"]["id"]

        sr = await client.post(
            _url(seed_product_id, f"/{vid}/age-surcharges"),
            headers=_auth(actor_token),
            json={"age_from": 40, "age_to": 50, "surcharge_percent": 5},
        )
        sid = sr.json()["data"]["id"]

        r = await client.delete(
            _url(seed_product_id, f"/{vid}/age-surcharges/{sid}"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "eliminado" in r.json()["message"].lower()

    async def test_surcharge_no_existe_retorna_404(self, client, actor_token, seed_product_id):
        cr = await client.post(
            _url(seed_product_id),
            headers=_auth(actor_token),
            json={"name": "Surcharge 404"},
        )
        vid = cr.json()["data"]["id"]

        r = await client.patch(
            _url(seed_product_id, f"/{vid}/age-surcharges/999999"),
            headers=_auth(actor_token),
            json={"surcharge_percent": 10},
        )
        assert r.status_code == 404
