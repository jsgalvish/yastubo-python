"""
Tests de Step 8 — Empresas (Company + CompanyCommissionUser).

Estrategia:
- SQLite en memoria (módulo-scoped).
- actor_token: usuario admin con permiso admin.companies.manage.
- seed_company_id: empresa base para tests de update/show/actions.
- seed_user_id / seed_user2_id: usuarios para attach/detach.
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
    """Usuario admin con permiso admin.companies.manage."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        actor = User(
            realm="admin",
            email="companies_actor@admintest.com",
            password=_hashed("ActorPass1!"),
            first_name="Companies",
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
async def seed_company_id(async_engine):
    """Empresa base para tests de update/show/acciones."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        company = Company(
            name="Empresa Seed",
            short_code="SEED",
            status=Company.STATUS_ACTIVE,
            email="seed@empresa.com",
            phone="123456789",
        )
        db.add(company)
        await db.commit()
        await db.refresh(company)
        return company.id


@pytest_asyncio.fixture(scope="module")
async def seed_user_id(async_engine):
    """Usuario para attach/detach y commission tests."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        user = User(
            realm="admin",
            email="seed_user@admintest.com",
            password=_hashed("Pass1!"),
            first_name="Seed",
            last_name="User",
            status="active",
            force_password_change=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


@pytest_asyncio.fixture(scope="module")
async def seed_user2_id(async_engine):
    """Segundo usuario para tests de commission."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        user = User(
            realm="admin",
            email="seed_user2@admintest.com",
            password=_hashed("Pass2!"),
            first_name="Seed2",
            last_name="User",
            status="active",
            force_password_change=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


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


# ─────────────────────── Company: index ──────────────────────────────────────

class TestCompanyIndex:
    async def test_sin_token_retorna_401(self, client):
        r = await client.get("/admin/companies")
        assert r.status_code == 401

    async def test_lista_empresas(self, client, actor_token, seed_company_id):
        r = await client.get(
            "/admin/companies",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "companies" in data
        assert "filters" in data
        assert any(c["id"] == seed_company_id for c in data["companies"])

    async def test_filtro_status_inactive(self, client, actor_token, async_engine):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            company = Company(name="Empresa Inactiva", short_code="INAC", status="inactive")
            db.add(company)
            await db.commit()

        r = await client.get(
            "/admin/companies?status=inactive",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        companies = r.json()["companies"]
        assert all(c["status"] == "inactive" for c in companies)

    async def test_filtro_search(self, client, actor_token, seed_company_id):
        r = await client.get(
            "/admin/companies?status=all&search=Seed",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        companies = r.json()["companies"]
        assert any(c["id"] == seed_company_id for c in companies)


# ─────────────────────── Company: check-short-code ───────────────────────────

class TestCheckShortCode:
    async def test_codigo_disponible(self, client, actor_token):
        r = await client.get(
            "/admin/companies/check-short-code?short_code=NUEVO",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["is_available"] is True
        assert data["reason"] is None

    async def test_codigo_ocupado(self, client, actor_token):
        r = await client.get(
            "/admin/companies/check-short-code?short_code=SEED",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["is_available"] is False
        assert data["reason"] == "taken"

    async def test_codigo_vacio(self, client, actor_token):
        r = await client.get(
            "/admin/companies/check-short-code?short_code=",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        assert r.json()["reason"] == "empty"

    async def test_codigo_case_insensitive(self, client, actor_token):
        # "seed" en minúsculas debe detectar conflicto con "SEED"
        r = await client.get(
            "/admin/companies/check-short-code?short_code=seed",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        assert r.json()["is_available"] is False


# ─────────────────────── Company: store ──────────────────────────────────────

class TestCompanyStore:
    async def test_crea_empresa(self, client, actor_token):
        r = await client.post(
            "/admin/companies",
            json={"name": "Nueva Empresa", "short_code": "NVE"},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["name"] == "Nueva Empresa"
        assert data["short_code"] == "NVE"
        assert data["status"] == "active"

    async def test_short_code_se_guarda_en_mayusculas(self, client, actor_token):
        r = await client.post(
            "/admin/companies",
            json={"name": "Empresa Lowercase", "short_code": "low"},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 201
        assert r.json()["data"]["short_code"] == "LOW"

    async def test_short_code_duplicado_retorna_422(self, client, actor_token):
        r = await client.post(
            "/admin/companies",
            json={"name": "Duplicada", "short_code": "SEED"},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 422


# ─────────────────────── Company: show ───────────────────────────────────────

class TestCompanyShow:
    async def test_show_con_detalle(self, client, actor_token, seed_company_id):
        r = await client.get(
            f"/admin/companies/{seed_company_id}",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "assigned_users" in data
        assert "beneficiary_users" in data
        assert "branding_defaults" in data
        assert "pdf_templates" in data
        assert data["data"]["id"] == seed_company_id

    async def test_show_no_existente_retorna_404(self, client, actor_token):
        r = await client.get(
            "/admin/companies/99999",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 404


# ─────────────────────── Company: update ─────────────────────────────────────

class TestCompanyUpdate:
    async def test_actualiza_nombre(self, client, actor_token, seed_company_id):
        r = await client.put(
            f"/admin/companies/{seed_company_id}",
            json={"name": "Empresa Seed Actualizada"},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "Empresa Seed Actualizada"

    async def test_actualiza_branding_color(self, client, actor_token, seed_company_id):
        r = await client.put(
            f"/admin/companies/{seed_company_id}",
            json={"branding_text_dark": "#1A2B3C"},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        # El color debe aparecer con '#' en la respuesta
        branding = r.json()["data"]["branding"]
        assert branding["text_dark"] == "#1A2B3C"

    async def test_short_code_duplicado_retorna_422(self, client, actor_token, seed_company_id, async_engine):
        # Crear otra empresa con short_code distinto
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            other = Company(name="Otra Empresa", short_code="OTRO", status="active")
            db.add(other)
            await db.commit()

        # Intentar cambiar seed a "OTRO"
        r = await client.put(
            f"/admin/companies/{seed_company_id}",
            json={"short_code": "OTRO"},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 422

    async def test_update_no_existente_retorna_404(self, client, actor_token):
        r = await client.put(
            "/admin/companies/99999",
            json={"name": "Nada"},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 404


# ─────────────────────── Company: acciones de estado ─────────────────────────

class TestCompanyStatusActions:
    async def test_suspend_archive_activate(self, client, actor_token, async_engine):
        """Ciclo completo: suspend → archive → activate."""
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            company = Company(name="Empresa Ciclo", short_code="CICL", status="active")
            db.add(company)
            await db.commit()
            await db.refresh(company)
            cid = company.id

        r1 = await client.put(
            f"/admin/companies/{cid}/suspend",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r1.status_code == 200
        assert r1.json()["data"]["status"] == "inactive"

        r2 = await client.put(
            f"/admin/companies/{cid}/archive",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["data"]["status"] == "archived"

        r3 = await client.put(
            f"/admin/companies/{cid}/activate",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r3.status_code == 200
        assert r3.json()["data"]["status"] == "active"

    async def test_suspend_no_afecta_archivada(self, client, actor_token, async_engine):
        """Una empresa archivada no cambia a inactive al suspender."""
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            company = Company(name="Empresa Archivada", short_code="ARCH", status="archived")
            db.add(company)
            await db.commit()
            await db.refresh(company)
            cid = company.id

        r = await client.put(
            f"/admin/companies/{cid}/suspend",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "archived"  # no cambia


# ─────────────────────── Company: usuarios asignados ─────────────────────────

class TestCompanyUsers:
    async def test_attach_user(self, client, actor_token, seed_company_id, seed_user_id):
        r = await client.post(
            f"/admin/companies/{seed_company_id}/users/{seed_user_id}",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        assert seed_user_id in r.json()["data"]["users_ids"]

    async def test_attach_idempotente(self, client, actor_token, seed_company_id, seed_user_id):
        r = await client.post(
            f"/admin/companies/{seed_company_id}/users/{seed_user_id}",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200  # no error al repetir

    async def test_attach_usuario_no_existente_retorna_404(self, client, actor_token, seed_company_id):
        r = await client.post(
            f"/admin/companies/{seed_company_id}/users/99999",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 404

    async def test_search_users(self, client, actor_token, seed_company_id, seed_user_id):
        r = await client.get(
            f"/admin/companies/{seed_company_id}/users/search",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "meta" in data
        # El seed_user debe aparecer como attached
        attached = [u for u in data["data"] if u["id"] == seed_user_id]
        assert len(attached) == 1
        assert attached[0]["is_attached"] is True

    async def test_detach_user(self, client, actor_token, seed_company_id, seed_user_id):
        r = await client.delete(
            f"/admin/companies/{seed_company_id}/users/{seed_user_id}",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        assert seed_user_id not in r.json()["data"]["users_ids"]

    async def test_detach_limpia_beneficiario(self, client, actor_token, async_engine, seed_user_id):
        """Si el usuario era beneficiario de comisiones, se limpia al desasociar."""
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            company = Company(
                name="Empresa Beneficiario",
                short_code="BENE",
                status="active",
                commission_beneficiary_user_id=seed_user_id,
            )
            db.add(company)
            await db.commit()
            await db.refresh(company)
            cid = company.id

        # Primero adjuntar
        await client.post(
            f"/admin/companies/{cid}/users/{seed_user_id}",
            headers={"Authorization": f"Bearer {actor_token}"},
        )

        # Luego desasociar
        r = await client.delete(
            f"/admin/companies/{cid}/users/{seed_user_id}",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["commission_beneficiary_user_id"] is None


# ─────────────────────── Commission Users ────────────────────────────────────

class TestCommissionUsers:
    async def test_index_vacio(self, client, actor_token, seed_company_id):
        r = await client.get(
            f"/admin/companies/{seed_company_id}/commission-users",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        assert "data" in r.json()

    async def test_store_commission_user(self, client, actor_token, seed_company_id, seed_user_id):
        r = await client.post(
            f"/admin/companies/{seed_company_id}/commission-users",
            json={"user_id": seed_user_id},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["user_id"] == seed_user_id
        assert data["commission"] == "0.00"

    async def test_store_duplicado_retorna_422(self, client, actor_token, seed_company_id, seed_user_id):
        r = await client.post(
            f"/admin/companies/{seed_company_id}/commission-users",
            json={"user_id": seed_user_id},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 422

    async def test_update_commission(self, client, actor_token, seed_company_id, seed_user_id):
        # Obtener id del ccu
        index_r = await client.get(
            f"/admin/companies/{seed_company_id}/commission-users",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        ccu = next(c for c in index_r.json()["data"] if c["user_id"] == seed_user_id)
        ccu_id = ccu["id"]

        r = await client.patch(
            f"/admin/companies/{seed_company_id}/commission-users/{ccu_id}",
            json={"commission": 15.5},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["commission"] == "15.50"

    async def test_available_tiene_attached(self, client, actor_token, seed_company_id, seed_user_id):
        r = await client.get(
            f"/admin/companies/{seed_company_id}/commission-users/available",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "meta" in data
        user_entry = next((u for u in data["data"] if u["id"] == seed_user_id), None)
        assert user_entry is not None
        assert user_entry["attached"] is True

    async def test_destroy_commission_user(self, client, actor_token, seed_company_id, seed_user2_id):
        # Crear un ccu para seed_user2
        store_r = await client.post(
            f"/admin/companies/{seed_company_id}/commission-users",
            json={"user_id": seed_user2_id},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert store_r.status_code == 201
        ccu_id = store_r.json()["data"]["id"]

        # Eliminar
        r = await client.delete(
            f"/admin/companies/{seed_company_id}/commission-users/{ccu_id}",
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 200
        assert "toast" in r.json()

    async def test_commission_user_no_existente_retorna_404(self, client, actor_token, seed_company_id):
        r = await client.patch(
            f"/admin/companies/{seed_company_id}/commission-users/99999",
            json={"commission": 5.0},
            headers={"Authorization": f"Bearer {actor_token}"},
        )
        assert r.status_code == 404
