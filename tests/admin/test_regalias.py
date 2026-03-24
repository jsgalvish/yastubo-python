"""
Tests de Step 13 — Regalías.

Estrategia:
- SQLite en memoria (módulo-scoped).
- Dos permisos: regalia.users.read y regalia.users.edit.
- CRUD: store, update (commission), destroy.
- beneficiariesIndex: agrupado por beneficiario.
- availableOriginsUsers / availableOriginsUnits: paginado con is_assigned.
"""
from __future__ import annotations

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
from app.models.business_unit import BusinessUnit
from app.models.regalia import Regalia
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
            email="regalias_actor@test.com",
            password=_hashed("Pass1!"),
            first_name="Regalias",
            last_name="Actor",
            status="active",
            force_password_change=False,
        )
        db.add(actor)
        await db.flush()

        for pname in ("regalia.users.read", "regalia.users.edit"):
            perm = Permission(name=pname, guard_name="admin")
            db.add(perm)
            await db.flush()
            svc = PermissionService(db)
            await svc.give_permission(actor, perm)

        await db.commit()
        return create_access_token(actor.id, "admin")


@pytest_asyncio.fixture(scope="module")
async def seed_users(async_engine):
    """Crea beneficiario + usuario origen para tests."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        beneficiary = User(
            realm="admin",
            email="beneficiario@test.com",
            password=_hashed("Pass1!"),
            first_name="Bene",
            last_name="Ficiario",
            status="active",
            force_password_change=False,
        )
        origin_user = User(
            realm="admin",
            email="origin_user@test.com",
            password=_hashed("Pass1!"),
            first_name="Origin",
            last_name="User",
            status="active",
            force_password_change=False,
        )
        db.add_all([beneficiary, origin_user])
        await db.commit()
        await db.refresh(beneficiary)
        await db.refresh(origin_user)
        return beneficiary.id, origin_user.id


@pytest_asyncio.fixture(scope="module")
async def seed_unit_id(async_engine):
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        bu = BusinessUnit(name="Unidad Test", status="active")
        db.add(bu)
        await db.commit()
        await db.refresh(bu)
        return bu.id


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


class TestRegaliaStore:
    async def test_sin_token_retorna_401(self, client):
        r = await client.post(
            "/admin/regalias/api/regalias",
            json={"beneficiary_user_id": 1, "source_type": "user", "source_id": 1},
        )
        assert r.status_code == 401

    async def test_crea_regalia_user(self, client, actor_token, seed_users):
        ben_id, origin_id = seed_users
        r = await client.post(
            "/admin/regalias/api/regalias",
            headers=_auth(actor_token),
            json={
                "beneficiary_user_id": ben_id,
                "source_type": "user",
                "source_id": origin_id,
            },
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["beneficiary_user_id"] == ben_id
        assert data["source_type"] == "user"
        assert data["source_id"] == origin_id
        assert data["commission"] == 0
        assert r.json()["message"] == "Regalía creada."

    async def test_crea_regalia_unit(self, client, actor_token, seed_users, seed_unit_id):
        ben_id, _ = seed_users
        r = await client.post(
            "/admin/regalias/api/regalias",
            headers=_auth(actor_token),
            json={
                "beneficiary_user_id": ben_id,
                "source_type": "unit",
                "source_id": seed_unit_id,
            },
        )
        assert r.status_code == 201
        assert r.json()["data"]["source_type"] == "unit"

    async def test_duplicado_retorna_422(self, client, actor_token, seed_users):
        ben_id, origin_id = seed_users
        # Ya creada en test anterior
        r = await client.post(
            "/admin/regalias/api/regalias",
            headers=_auth(actor_token),
            json={
                "beneficiary_user_id": ben_id,
                "source_type": "user",
                "source_id": origin_id,
            },
        )
        assert r.status_code == 422
        assert "ya existe" in r.json()["detail"].lower()

    async def test_source_type_invalido_retorna_422(self, client, actor_token, seed_users):
        ben_id, _ = seed_users
        r = await client.post(
            "/admin/regalias/api/regalias",
            headers=_auth(actor_token),
            json={
                "beneficiary_user_id": ben_id,
                "source_type": "invalid",
                "source_id": 1,
            },
        )
        assert r.status_code == 422


# ─────────────────────── Update ──────────────────────────────────────────────


class TestRegaliaUpdate:
    async def test_actualiza_comision(self, client, actor_token, seed_users):
        ben_id, origin_id = seed_users
        # Buscar la regalía existente via beneficiaries
        ben_r = await client.get(
            "/admin/regalias/api/beneficiaries",
            headers=_auth(actor_token),
        )
        regalias = ben_r.json()["data"][0]["regalias"]
        reg_id = regalias[0]["id"]

        r = await client.patch(
            f"/admin/regalias/api/regalias/{reg_id}",
            headers=_auth(actor_token),
            json={"commission": 15.5},
        )
        assert r.status_code == 200
        assert r.json()["data"]["commission"] == 15.5
        assert r.json()["message"] == "Regalía actualizada."

    async def test_regalia_no_existe_retorna_404(self, client, actor_token):
        r = await client.patch(
            "/admin/regalias/api/regalias/999999",
            headers=_auth(actor_token),
            json={"commission": 10},
        )
        assert r.status_code == 404


# ─────────────────────── Destroy ─────────────────────────────────────────────


class TestRegaliaDestroy:
    async def test_elimina_regalia(self, client, actor_token, seed_users, seed_unit_id):
        ben_id, _ = seed_users
        # Crear una nueva para eliminar
        cr = await client.post(
            "/admin/regalias/api/regalias",
            headers=_auth(actor_token),
            json={
                "beneficiary_user_id": ben_id,
                "source_type": "unit",
                "source_id": seed_unit_id,
            },
        )
        # Si ya existe (del test anterior), buscarla
        if cr.status_code == 422:
            ben_r = await client.get(
                "/admin/regalias/api/beneficiaries",
                headers=_auth(actor_token),
            )
            for group in ben_r.json()["data"]:
                for reg in group["regalias"]:
                    if reg["source_type"] == "unit" and reg["source_id"] == seed_unit_id:
                        reg_id = reg["id"]
                        break
        else:
            reg_id = cr.json()["data"]["id"]

        r = await client.delete(
            f"/admin/regalias/api/regalias/{reg_id}",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert r.json()["message"] == "Regalía eliminada."


# ─────────────────────── BeneficiariesIndex ──────────────────────────────────


class TestBeneficiariesIndex:
    async def test_lista_beneficiarios(self, client, actor_token):
        r = await client.get(
            "/admin/regalias/api/beneficiaries",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "meta" in data
        if data["data"]:
            group = data["data"][0]
            assert "beneficiary" in group
            assert "regalias" in group


# ─────────────────────── Available Origins ───────────────────────────────────


class TestAvailableOrigins:
    async def test_available_users(self, client, actor_token, seed_users):
        ben_id, _ = seed_users
        r = await client.get(
            f"/admin/regalias/api/beneficiaries/{ben_id}/origins/users/available",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "data" in r.json()
        assert "meta" in r.json()

    async def test_available_units(self, client, actor_token, seed_users):
        ben_id, _ = seed_users
        r = await client.get(
            f"/admin/regalias/api/beneficiaries/{ben_id}/origins/units/available",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "data" in r.json()
        assert "meta" in r.json()
