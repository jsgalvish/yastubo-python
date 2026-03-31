"""
Tests de Step 18 — Dashboard & Config.

Estrategia:
- SQLite en memoria (módulo-scoped).
- Permisos: admin.config.read/create/edit/fill/delete.
- Dashboard: placeholder GET.
- Config CRUD: store, show, updateDefinition, updateValue, destroy.
- Validación de token único por categoría.
"""

from __future__ import annotations

import bcrypt as _bcrypt_lib
import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models
from app.database import get_db
from app.main import app
from app.models import Base, Permission, User
from app.services.permission_service import PermissionService
from app.services.token_service import create_access_token


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
            email="config_actor@test.com",
            password=_hashed("Pass1!"),
            first_name="Config",
            last_name="Actor",
            status="active",
            force_password_change=False,
        )
        db.add(actor)
        await db.flush()

        for pname in (
            "admin.config.read",
            "admin.config.create",
            "admin.config.edit",
            "admin.config.fill",
            "admin.config.delete",
        ):
            perm = Permission(name=pname, guard_name="admin")
            db.add(perm)
            await db.flush()
            svc = PermissionService(db)
            await svc.give_permission(actor, perm)

        await db.commit()
        return create_access_token(actor.id, "admin")


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


# ─────────────────────── Dashboard ───────────────────────────────────────────


class TestDashboard:
    async def test_sin_token_retorna_401(self, client):
        r = await client.get("/admin/dashboard")
        assert r.status_code == 401

    async def test_dashboard_ok(self, client, actor_token):
        r = await client.get("/admin/dashboard", headers=_auth(actor_token))
        assert r.status_code == 200
        data = r.json()
        assert "beneficiarios" in data
        assert "mrr_capitado" in data


# ─────────────────────── Config Store ────────────────────────────────────────


class TestConfigStore:
    async def test_sin_token_retorna_401(self, client):
        r = await client.post(
            "/admin/config",
            json={
                "category": "general",
                "name": "X",
                "token": "x",
                "type": "integer",
            },
        )
        assert r.status_code == 401

    async def test_crea_item(self, client, actor_token):
        r = await client.post(
            "/admin/config",
            headers=_auth(actor_token),
            json={
                "category": "general",
                "name": "Nombre Empresa",
                "token": "company_name",
                "type": "input_text_plain",
            },
        )
        assert r.status_code == 201
        item = r.json()["item"]
        assert item["token"] == "company_name"
        assert item["type"] == "input_text_plain"
        assert r.json()["message"] == "Item creado correctamente."

    async def test_token_duplicado_retorna_422(self, client, actor_token):
        await client.post(
            "/admin/config",
            headers=_auth(actor_token),
            json={"category": "dup", "name": "Dup", "token": "dup_token", "type": "integer"},
        )
        r = await client.post(
            "/admin/config",
            headers=_auth(actor_token),
            json={"category": "dup", "name": "Dup2", "token": "dup_token", "type": "integer"},
        )
        assert r.status_code == 422


# ─────────────────────── Config Show ─────────────────────────────────────────


class TestConfigShow:
    async def test_show_item(self, client, actor_token):
        cr = await client.post(
            "/admin/config",
            headers=_auth(actor_token),
            json={"category": "show", "name": "Show Item", "token": "show_item", "type": "integer"},
        )
        iid = cr.json()["item"]["id"]

        r = await client.get(f"/admin/config/{iid}", headers=_auth(actor_token))
        assert r.status_code == 200
        assert r.json()["item"]["id"] == iid

    async def test_404(self, client, actor_token):
        r = await client.get("/admin/config/999999", headers=_auth(actor_token))
        assert r.status_code == 404


# ─────────────────────── Config Index ────────────────────────────────────────


class TestConfigIndex:
    async def test_index(self, client, actor_token):
        r = await client.get("/admin/config", headers=_auth(actor_token))
        assert r.status_code == 200
        assert "items" in r.json()
        assert "permissions" in r.json()


# ─────────────────────── Config UpdateDefinition ─────────────────────────────


class TestConfigUpdateDefinition:
    async def test_update_definition(self, client, actor_token):
        cr = await client.post(
            "/admin/config",
            headers=_auth(actor_token),
            json={"category": "def", "name": "Def Item", "token": "def_item", "type": "integer"},
        )
        iid = cr.json()["item"]["id"]

        r = await client.put(
            f"/admin/config/{iid}/definition",
            headers=_auth(actor_token),
            json={"name": "Renamed", "type": "decimal"},
        )
        assert r.status_code == 200
        assert r.json()["item"]["name"] == "Renamed"
        assert r.json()["item"]["type"] == "decimal"


# ─────────────────────── Config UpdateValue ──────────────────────────────────


class TestConfigUpdateValue:
    async def test_update_integer_value(self, client, actor_token):
        cr = await client.post(
            "/admin/config",
            headers=_auth(actor_token),
            json={"category": "val", "name": "Int Item", "token": "int_item", "type": "integer"},
        )
        iid = cr.json()["item"]["id"]

        r = await client.put(
            f"/admin/config/{iid}/value",
            headers=_auth(actor_token),
            json={"value": 42},
        )
        assert r.status_code == 200
        assert r.json()["item"]["value_int"] == 42

    async def test_update_text_value(self, client, actor_token):
        cr = await client.post(
            "/admin/config",
            headers=_auth(actor_token),
            json={
                "category": "val",
                "name": "Text Item",
                "token": "text_item",
                "type": "input_text_plain",
            },
        )
        iid = cr.json()["item"]["id"]

        r = await client.put(
            f"/admin/config/{iid}/value",
            headers=_auth(actor_token),
            json={"value": "Hello World"},
        )
        assert r.status_code == 200
        assert r.json()["item"]["value_text"] == "Hello World"

    async def test_update_translated_value(self, client, actor_token):
        cr = await client.post(
            "/admin/config",
            headers=_auth(actor_token),
            json={
                "category": "val",
                "name": "Trans Item",
                "token": "trans_item",
                "type": "input_text_translated",
            },
        )
        iid = cr.json()["item"]["id"]

        r = await client.put(
            f"/admin/config/{iid}/value",
            headers=_auth(actor_token),
            json={"value": {"es": "Hola", "en": "Hello"}},
        )
        assert r.status_code == 200
        assert r.json()["item"]["value_trans"] is not None

    async def test_update_null_value(self, client, actor_token):
        cr = await client.post(
            "/admin/config",
            headers=_auth(actor_token),
            json={"category": "val", "name": "Null Item", "token": "null_item", "type": "integer"},
        )
        iid = cr.json()["item"]["id"]

        r = await client.put(
            f"/admin/config/{iid}/value",
            headers=_auth(actor_token),
            json={"value": None},
        )
        assert r.status_code == 200
        assert r.json()["item"]["value_int"] is None


# ─────────────────────── Config Destroy ──────────────────────────────────────


class TestConfigDestroy:
    async def test_destroy(self, client, actor_token):
        cr = await client.post(
            "/admin/config",
            headers=_auth(actor_token),
            json={"category": "del", "name": "Del Item", "token": "del_item", "type": "integer"},
        )
        iid = cr.json()["item"]["id"]

        r = await client.delete(f"/admin/config/{iid}", headers=_auth(actor_token))
        assert r.status_code == 200

        r2 = await client.get(f"/admin/config/{iid}", headers=_auth(actor_token))
        assert r2.status_code == 404
