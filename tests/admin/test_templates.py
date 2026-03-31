"""
Tests de Step 17 — Templates (Template + TemplateVersion).

Estrategia:
- SQLite en memoria (módulo-scoped).
- Permiso: admin.templates.edit.
- Template CRUD: store, show, updateBasic, updateTestData, destroy, clone.
- Version CRUD: store, show, updateBasic, updateTestData, activate, deactivate, clone, destroy.
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
            realm="admin", email="templates_actor@test.com",
            password=_hashed("Pass1!"), first_name="Tpl", last_name="Actor",
            status="active", force_password_change=False,
        )
        db.add(actor)
        await db.flush()

        perm = Permission(name="admin.templates.edit", guard_name="admin")
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


_BASE = "/admin/templates"


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATES
# ═════════════════════════════════════════════════════════════════════════════


class TestTemplateStore:
    async def test_sin_token_retorna_401(self, client):
        r = await client.post(_BASE, json={"name": "X", "slug": "x", "type": "html"})
        assert r.status_code == 401

    async def test_crea_template(self, client, actor_token):
        r = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Contrato PDF", "slug": "contrato-pdf", "type": "pdf"},
        )
        assert r.status_code == 201
        tpl = r.json()["data"]["template"]
        assert tpl["name"] == "Contrato PDF"
        assert tpl["slug"] == "contrato-pdf"
        assert tpl["type"] == "pdf"

    async def test_slug_duplicado_retorna_422(self, client, actor_token):
        await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Dup", "slug": "dup-slug", "type": "html"},
        )
        r = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Dup2", "slug": "dup-slug", "type": "html"},
        )
        assert r.status_code == 422


class TestTemplateShow:
    async def test_show_con_versiones(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Show Tpl", "slug": "show-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        r = await client.get(f"{_BASE}/{tid}", headers=_auth(actor_token))
        assert r.status_code == 200
        assert "template" in r.json()["data"]
        assert "versions" in r.json()["data"]

    async def test_404(self, client, actor_token):
        r = await client.get(f"{_BASE}/999999", headers=_auth(actor_token))
        assert r.status_code == 404


class TestTemplateUpdate:
    async def test_update_basic(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Upd Tpl", "slug": "upd-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        r = await client.patch(
            f"{_BASE}/{tid}/basic", headers=_auth(actor_token),
            json={"name": "Updated", "slug": "upd-tpl-new"},
        )
        assert r.status_code == 200

    async def test_update_test_data(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "TD Tpl", "slug": "td-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        r = await client.patch(
            f"{_BASE}/{tid}/test-data", headers=_auth(actor_token),
            json={"test_data_json": '{"key": "value"}'},
        )
        assert r.status_code == 200

    async def test_invalid_json_retorna_422(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Bad JSON", "slug": "bad-json", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        r = await client.patch(
            f"{_BASE}/{tid}/test-data", headers=_auth(actor_token),
            json={"test_data_json": "not valid json"},
        )
        assert r.status_code == 422


class TestTemplateDestroy:
    async def test_soft_delete(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Del Tpl", "slug": "del-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        r = await client.delete(f"{_BASE}/{tid}", headers=_auth(actor_token))
        assert r.status_code == 200

        r2 = await client.get(f"{_BASE}/{tid}", headers=_auth(actor_token))
        assert r2.status_code == 404


class TestTemplateClone:
    async def test_clone(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Clone Src", "slug": "clone-src", "type": "pdf"},
        )
        tid = cr.json()["data"]["template"]["id"]

        r = await client.post(f"{_BASE}/{tid}/clone", headers=_auth(actor_token))
        assert r.status_code == 201
        clone = r.json()["data"]["template"]
        assert "Copia" in clone["name"]
        assert clone["slug"] != "clone-src"
        assert clone["id"] != tid


class TestTemplateIndex:
    async def test_index(self, client, actor_token):
        r = await client.get(_BASE, headers=_auth(actor_token))
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)


# ═════════════════════════════════════════════════════════════════════════════
# VERSIONS
# ═════════════════════════════════════════════════════════════════════════════


class TestVersionCRUD:
    async def test_store_version(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "V Tpl", "slug": "v-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        r = await client.post(
            f"{_BASE}/{tid}/versions", headers=_auth(actor_token),
            json={"content": "<h1>Hello</h1>"},
        )
        assert r.status_code == 201
        v = r.json()["data"]["version"]
        assert v["content"] == "<h1>Hello</h1>"
        assert v["name"].startswith("Version #")

    async def test_show_version(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Show V Tpl", "slug": "show-v-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        vr = await client.post(
            f"{_BASE}/{tid}/versions", headers=_auth(actor_token),
            json={"content": "test"},
        )
        vid = vr.json()["data"]["version"]["id"]

        r = await client.get(f"{_BASE}/{tid}/versions/{vid}", headers=_auth(actor_token))
        assert r.status_code == 200
        assert r.json()["data"]["version"]["id"] == vid

    async def test_update_version_basic(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Upd V Tpl", "slug": "upd-v-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        vr = await client.post(f"{_BASE}/{tid}/versions", headers=_auth(actor_token), json={})
        vid = vr.json()["data"]["version"]["id"]

        r = await client.patch(
            f"{_BASE}/{tid}/versions/{vid}/basic", headers=_auth(actor_token),
            json={"name": "Renamed", "content": "<p>Updated</p>"},
        )
        assert r.status_code == 200


class TestVersionActivation:
    async def test_activate_and_deactivate(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Act Tpl", "slug": "act-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        vr = await client.post(f"{_BASE}/{tid}/versions", headers=_auth(actor_token), json={})
        vid = vr.json()["data"]["version"]["id"]

        # Activate
        r = await client.post(
            f"{_BASE}/{tid}/versions/{vid}/activate", headers=_auth(actor_token),
        )
        assert r.status_code == 200

        # Verify active
        sr = await client.get(f"{_BASE}/{tid}", headers=_auth(actor_token))
        assert sr.json()["data"]["template"]["active_template_version_id"] == vid

        # Deactivate
        r2 = await client.post(
            f"{_BASE}/{tid}/versions/{vid}/deactivate", headers=_auth(actor_token),
        )
        assert r2.status_code == 200

    async def test_deactivate_non_active_retorna_422(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Deact Tpl", "slug": "deact-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        vr = await client.post(f"{_BASE}/{tid}/versions", headers=_auth(actor_token), json={})
        vid = vr.json()["data"]["version"]["id"]

        r = await client.post(
            f"{_BASE}/{tid}/versions/{vid}/deactivate", headers=_auth(actor_token),
        )
        assert r.status_code == 422


class TestVersionDelete:
    async def test_delete_version(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Del V Tpl", "slug": "del-v-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        vr = await client.post(f"{_BASE}/{tid}/versions", headers=_auth(actor_token), json={})
        vid = vr.json()["data"]["version"]["id"]

        r = await client.delete(f"{_BASE}/{tid}/versions/{vid}", headers=_auth(actor_token))
        assert r.status_code == 200

    async def test_delete_active_retorna_422(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Del Act Tpl", "slug": "del-act-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        vr = await client.post(f"{_BASE}/{tid}/versions", headers=_auth(actor_token), json={})
        vid = vr.json()["data"]["version"]["id"]

        await client.post(f"{_BASE}/{tid}/versions/{vid}/activate", headers=_auth(actor_token))

        r = await client.delete(f"{_BASE}/{tid}/versions/{vid}", headers=_auth(actor_token))
        assert r.status_code == 422


class TestVersionClone:
    async def test_clone_version(self, client, actor_token):
        cr = await client.post(
            _BASE, headers=_auth(actor_token),
            json={"name": "Clone V Tpl", "slug": "clone-v-tpl", "type": "html"},
        )
        tid = cr.json()["data"]["template"]["id"]

        vr = await client.post(
            f"{_BASE}/{tid}/versions", headers=_auth(actor_token),
            json={"content": "<p>Original</p>"},
        )
        vid = vr.json()["data"]["version"]["id"]

        r = await client.post(
            f"{_BASE}/{tid}/versions/{vid}/clone", headers=_auth(actor_token),
        )
        assert r.status_code == 201
        clone = r.json()["data"]["version"]
        assert clone["id"] != vid
        assert clone["content"] == "<p>Original</p>"
