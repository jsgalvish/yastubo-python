"""
Tests de Step 14 — Business Units (CRUD + Members + GSA Commissions).

Estrategia:
- SQLite en memoria (módulo-scoped).
- Permiso: admin.business_units.manage.
- Unit CRUD: list, store, show, children, updateBasic, updateStatus.
- Members: link, updateRole, updateStatus, remove.
- GSA Commissions: store, update, destroy, available.
- Reglas: jerarquía padre, duplicados, validación de status.
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
from app.models.role import Role
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
            email="bu_actor@test.com",
            password=_hashed("Pass1!"),
            first_name="BU",
            last_name="Actor",
            status="active",
            force_password_change=False,
        )
        db.add(actor)
        await db.flush()

        perm = Permission(name="admin.business_units.manage", guard_name="admin")
        db.add(perm)
        await db.flush()

        svc = PermissionService(db)
        await svc.give_permission(actor, perm)
        await db.commit()
        return create_access_token(actor.id, "admin")


@pytest_asyncio.fixture(scope="module")
async def seed_member_user_id(async_engine):
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        user = User(
            realm="admin",
            email="member@test.com",
            password=_hashed("Pass1!"),
            first_name="Member",
            last_name="User",
            status="active",
            force_password_change=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


@pytest_asyncio.fixture(scope="module")
async def seed_role_id(async_engine):
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        role = Role(name="unit.member", guard_name="admin")
        db.add(role)
        await db.commit()
        await db.refresh(role)
        return role.id


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


_BASE = "/admin/business-units/api"


# ═════════════════════════════════════════════════════════════════════════════
# UNITS CRUD
# ═════════════════════════════════════════════════════════════════════════════


class TestUnitStore:
    async def test_sin_token_retorna_401(self, client):
        r = await client.post(f"{_BASE}/units", json={"type": "consolidator", "name": "X"})
        assert r.status_code == 401

    async def test_crea_consolidador(self, client, actor_token):
        r = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "Consolidador A"},
        )
        assert r.status_code == 201
        assert r.json()["data"]["type"] == "consolidator"
        assert r.json()["data"]["status"] == "active"

    async def test_crea_office_con_padre(self, client, actor_token):
        # Crear consolidador
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "Parent"},
        )
        parent_id = cr.json()["data"]["id"]

        r = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "office", "name": "Office B", "parent_id": parent_id},
        )
        assert r.status_code == 201
        assert r.json()["data"]["parent_id"] == parent_id

    async def test_consolidador_con_padre_retorna_422(self, client, actor_token):
        r = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "Bad", "parent_id": 1},
        )
        assert r.status_code == 422

    async def test_counter_sin_padre_retorna_422(self, client, actor_token):
        r = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "counter", "name": "Bad Counter"},
        )
        assert r.status_code == 422


class TestUnitList:
    async def test_lista_por_tipo(self, client, actor_token):
        r = await client.get(
            f"{_BASE}/units?type=consolidator",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "data" in r.json()
        assert "meta" in r.json()
        for u in r.json()["data"]:
            assert u["type"] == "consolidator"


class TestUnitShow:
    async def test_show(self, client, actor_token):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "Show Unit"},
        )
        uid = cr.json()["data"]["id"]
        r = await client.get(f"{_BASE}/units/{uid}", headers=_auth(actor_token))
        assert r.status_code == 200
        assert r.json()["data"]["id"] == uid

    async def test_show_404(self, client, actor_token):
        r = await client.get(f"{_BASE}/units/999999", headers=_auth(actor_token))
        assert r.status_code == 404


class TestUnitChildren:
    async def test_children(self, client, actor_token):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "Parent Children"},
        )
        pid = cr.json()["data"]["id"]

        await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "office", "name": "Child 1", "parent_id": pid},
        )

        r = await client.get(f"{_BASE}/units/{pid}/children", headers=_auth(actor_token))
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 1


class TestUnitUpdateBasic:
    async def test_update_name(self, client, actor_token):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "freelance", "name": "Old Name"},
        )
        uid = cr.json()["data"]["id"]

        r = await client.patch(
            f"{_BASE}/units/{uid}/basic",
            headers=_auth(actor_token),
            json={"name": "New Name"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "New Name"


class TestUnitUpdateStatus:
    async def test_toggle_status(self, client, actor_token):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "Status Unit"},
        )
        uid = cr.json()["data"]["id"]
        assert cr.json()["data"]["status"] == "active"

        r = await client.patch(
            f"{_BASE}/units/{uid}/status",
            headers=_auth(actor_token),
            json={"status": "inactive"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "inactive"


# ═════════════════════════════════════════════════════════════════════════════
# MEMBERS
# ═════════════════════════════════════════════════════════════════════════════


class TestMembers:
    async def test_link_member(self, client, actor_token, seed_member_user_id, seed_role_id):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "Members Unit"},
        )
        uid = cr.json()["data"]["id"]

        r = await client.post(
            f"{_BASE}/units/{uid}/members",
            headers=_auth(actor_token),
            json={"user_id": seed_member_user_id, "role_id": seed_role_id},
        )
        assert r.status_code == 201
        assert r.json()["data"]["user_id"] == seed_member_user_id
        assert "toast" in r.json()

    async def test_list_members(self, client, actor_token, seed_member_user_id):
        # Buscar una unidad con miembro
        units_r = await client.get(
            f"{_BASE}/units?type=consolidator",
            headers=_auth(actor_token),
        )
        uid = None
        for u in units_r.json()["data"]:
            if u["members_count"] > 0:
                uid = u["id"]
                break

        if uid:
            r = await client.get(f"{_BASE}/units/{uid}/members", headers=_auth(actor_token))
            assert r.status_code == 200
            assert len(r.json()["data"]) >= 1

    async def test_duplicate_member_retorna_422(self, client, actor_token, seed_member_user_id):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "Dup Member Unit"},
        )
        uid = cr.json()["data"]["id"]

        await client.post(
            f"{_BASE}/units/{uid}/members",
            headers=_auth(actor_token),
            json={"user_id": seed_member_user_id},
        )
        r2 = await client.post(
            f"{_BASE}/units/{uid}/members",
            headers=_auth(actor_token),
            json={"user_id": seed_member_user_id},
        )
        assert r2.status_code == 422

    async def test_remove_member(self, client, actor_token, seed_member_user_id):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "Remove Member"},
        )
        uid = cr.json()["data"]["id"]

        mr = await client.post(
            f"{_BASE}/units/{uid}/members",
            headers=_auth(actor_token),
            json={"user_id": seed_member_user_id},
        )
        mid = mr.json()["data"]["id"]

        r = await client.delete(
            f"{_BASE}/units/{uid}/members/{mid}",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# GSA COMMISSIONS
# ═════════════════════════════════════════════════════════════════════════════


class TestGSACommissions:
    async def test_store_commission(self, client, actor_token, seed_member_user_id):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "GSA Unit"},
        )
        uid = cr.json()["data"]["id"]

        r = await client.post(
            f"{_BASE}/units/{uid}/gsa-commissions",
            headers=_auth(actor_token),
            json={"user_id": seed_member_user_id},
        )
        assert r.status_code == 201
        assert r.json()["data"]["commission"] == 0
        assert "toast" in r.json()

    async def test_update_commission(self, client, actor_token, seed_member_user_id):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "GSA Update Unit"},
        )
        uid = cr.json()["data"]["id"]

        sr = await client.post(
            f"{_BASE}/units/{uid}/gsa-commissions",
            headers=_auth(actor_token),
            json={"user_id": seed_member_user_id},
        )
        rid = sr.json()["data"]["id"]

        r = await client.patch(
            f"{_BASE}/units/{uid}/gsa-commissions/{rid}",
            headers=_auth(actor_token),
            json={"commission": 12.5},
        )
        assert r.status_code == 200
        assert r.json()["data"]["commission"] == 12.5

    async def test_destroy_commission(self, client, actor_token, seed_member_user_id):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "GSA Del Unit"},
        )
        uid = cr.json()["data"]["id"]

        sr = await client.post(
            f"{_BASE}/units/{uid}/gsa-commissions",
            headers=_auth(actor_token),
            json={"user_id": seed_member_user_id},
        )
        rid = sr.json()["data"]["id"]

        r = await client.delete(
            f"{_BASE}/units/{uid}/gsa-commissions/{rid}",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200

    async def test_available_gsa_users(self, client, actor_token):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "GSA Avail Unit"},
        )
        uid = cr.json()["data"]["id"]

        r = await client.get(
            f"{_BASE}/units/{uid}/gsa-commissions/available",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "data" in r.json()
        assert "meta" in r.json()

    async def test_list_commissions(self, client, actor_token):
        cr = await client.post(
            f"{_BASE}/units",
            headers=_auth(actor_token),
            json={"type": "consolidator", "name": "GSA List Unit"},
        )
        uid = cr.json()["data"]["id"]

        r = await client.get(
            f"{_BASE}/units/{uid}/gsa-commissions",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)
