"""
Tests de Step 15 — Capitados Core (Persons + Contracts).

Estrategia:
- SQLite en memoria (módulo-scoped).
- Permiso: admin.companies.manage.
- Seed: empresa + producto capitado + persona + contrato.
- Endpoints read-only: persons index/show, contracts index/show.
"""

from __future__ import annotations

import json
from datetime import date

import bcrypt as _bcrypt_lib
import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models
from app.database import get_db
from app.main import app
from app.models import Base, Permission, User
from app.models.capitated_contract import CapitatedContract
from app.models.capitated_product_insured import CapitatedProductInsured
from app.models.company import Company
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
            email="capitated_actor@test.com",
            password=_hashed("Pass1!"),
            first_name="Cap",
            last_name="Actor",
            status="active",
            force_password_change=False,
        )
        db.add(actor)
        await db.flush()

        perm = Permission(name="admin.companies.manage", guard_name="admin")
        db.add(perm)
        await db.flush()

        svc = PermissionService(db)
        await svc.give_permission(actor, perm)
        await db.commit()
        return create_access_token(actor.id, "admin")


@pytest_asyncio.fixture(scope="module")
async def seed_data(async_engine):
    """Crea empresa + producto capitado + persona + contrato."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        company = Company(name="Empresa Capitados", short_code="CAP", status="active")
        db.add(company)
        await db.flush()

        product = Product(
            name=json.dumps({"es": "Plan Capitado Test"}),
            product_type=Product.TYPE_PLAN_CAPITADO,
            status="active",
            show_in_widget=False,
            company_id=company.id,
        )
        db.add(product)
        await db.flush()

        person = CapitatedProductInsured(
            company_id=company.id,
            product_id=product.id,
            document_number="12345678",
            full_name="Juan Pérez",
            sex="M",
            age_reported=45,
            status="active",
        )
        db.add(person)
        await db.flush()

        contract = CapitatedContract(
            company_id=company.id,
            product_id=product.id,
            person_id=person.id,
            status="active",
            entry_date=date(2025, 1, 1),
            valid_until=date(2025, 12, 31),
            entry_age=45,
        )
        db.add(contract)
        await db.commit()

        await db.refresh(company)
        await db.refresh(product)
        await db.refresh(person)
        await db.refresh(contract)

        return {
            "company_id": company.id,
            "product_id": product.id,
            "person_id": person.id,
            "contract_id": contract.id,
        }


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


def _url(cid: int, suffix: str) -> str:
    return f"/admin/companies/{cid}/capitados{suffix}"


# ─────────────────────── Persons ─────────────────────────────────────────────


class TestPersonsIndex:
    async def test_sin_token_retorna_401(self, client, seed_data):
        r = await client.get(_url(seed_data["company_id"], "/persons"))
        assert r.status_code == 401

    async def test_lista_personas(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], "/persons"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "meta" in data
        assert len(data["data"]) >= 1
        assert data["data"][0]["full_name"] == "Juan Pérez"

    async def test_filtra_por_producto(self, client, actor_token, seed_data):
        pid = seed_data["product_id"]
        r = await client.get(
            _url(seed_data["company_id"], f"/persons?product_id={pid}"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        for p in r.json()["data"]:
            assert p["product_id"] == pid

    async def test_empresa_inexistente_retorna_404(self, client, actor_token):
        r = await client.get(
            _url(999999, "/persons"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 404


class TestPersonsShow:
    async def test_detalle_persona_con_contratos(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], f"/persons/{seed_data['person_id']}"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["person"]["id"] == seed_data["person_id"]
        assert len(data["contracts"]) >= 1

    async def test_persona_no_existe_retorna_404(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], "/persons/999999"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 404


# ─────────────────────── Contracts ───────────────────────────────────────────


class TestContractsIndex:
    async def test_lista_contratos(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], "/contracts"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["data"]) >= 1
        assert data["data"][0]["status"] == "active"

    async def test_busqueda_por_nombre(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], "/contracts?q=Pérez&status=all"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 1

    async def test_busqueda_por_documento(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], "/contracts?q=12345678&status=all"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 1


class TestContractsShow:
    async def test_detalle_contrato(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], f"/contracts/{seed_data['contract_id']}"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["contract"]["id"] == seed_data["contract_id"]
        assert data["contract"]["status"] == "active"

    async def test_contrato_no_existe_retorna_404(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], "/contracts/999999"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 404
