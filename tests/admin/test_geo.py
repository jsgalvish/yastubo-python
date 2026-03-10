"""
Tests de Step 7 — Catálogos geográficos (Countries + Zones).

Estrategia:
- SQLite en memoria (módulo-scoped) para aislamiento.
- Fixture 'client' por función → override de get_db con la misma engine.
- actor_token_countries: usuario admin con permiso admin.countries.manage.
- actor_token_admin: usuario admin sin permiso específico (para zones).
"""
from __future__ import annotations

import json

import bcrypt as _bcrypt_lib
import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # registra todos los modelos en Base.metadata
from app.database import get_db
from app.main import app
from app.models import Base, Permission, User
from app.models.country import Country
from app.models.zone import Zone
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
async def actor_token_countries(async_engine):
    """Usuario admin con permiso admin.countries.manage."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        user = User(
            realm="admin",
            email="geo_countries@admintest.com",
            password=_hashed("GeoPass1!"),
            first_name="Geo",
            last_name="Countries",
            status="active",
            force_password_change=False,
        )
        db.add(user)
        await db.flush()

        perm = Permission(name="admin.countries.manage", guard_name="admin")
        db.add(perm)
        await db.flush()

        svc = PermissionService(db)
        await svc.give_permission(user, perm)
        await db.commit()

        return create_access_token(user.id, "admin")


@pytest_asyncio.fixture(scope="module")
async def actor_token_admin(async_engine):
    """Usuario admin sin permiso específico (para zonas)."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        user = User(
            realm="admin",
            email="geo_zones@admintest.com",
            password=_hashed("GeoPass2!"),
            first_name="Geo",
            last_name="Zones",
            status="active",
            force_password_change=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return create_access_token(user.id, "admin")


@pytest_asyncio.fixture(scope="module")
async def seed_country_id(async_engine):
    """País inicial reutilizado por tests de update/show/toggle."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        country = Country(
            name=json.dumps({"es": "Argentina", "en": "Argentina"}),
            iso2="AR",
            iso3="ARG",
            continent_code="SA",
            phone_code="54",
            is_active=True,
        )
        db.add(country)
        await db.commit()
        await db.refresh(country)
        return country.id


@pytest_asyncio.fixture(scope="module")
async def seed_zone_id(async_engine):
    """Zona inicial reutilizada por tests de update/show/toggle."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        zone = Zone(name="Cono Sur", description="Países del cono sur", is_active=True)
        db.add(zone)
        await db.commit()
        await db.refresh(zone)
        return zone.id


@pytest_asyncio.fixture
async def client(async_engine):
    """Cliente httpx con override de get_db apuntando a SQLite."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ─────────────────────── Countries: index ────────────────────────────────────

class TestCountryIndex:
    async def test_sin_token_retorna_401(self, client):
        r = await client.get("/admin/countries")
        assert r.status_code == 401

    async def test_lista_paises(self, client, actor_token_countries, seed_country_id):
        r = await client.get(
            "/admin/countries",
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert any(c["id"] == seed_country_id for c in data)

    async def test_respuesta_tiene_continent_label(
        self, client, actor_token_countries, seed_country_id
    ):
        r = await client.get(
            "/admin/countries",
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        country = next(c for c in r.json() if c["id"] == seed_country_id)
        assert country["continent_label"] == "Sudamérica"

    async def test_sin_permiso_retorna_403(self, client, actor_token_admin):
        """Token de admin sin admin.countries.manage → 403."""
        r = await client.get(
            "/admin/countries",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 403


# ─────────────────────── Countries: store ────────────────────────────────────

class TestCountryStore:
    async def test_crea_pais(self, client, actor_token_countries):
        payload = {
            "name": {"es": "Brasil", "en": "Brazil"},
            "iso2": "BR",
            "iso3": "BRA",
            "continent_code": "SA",
            "phone_code": "55",
        }
        r = await client.post(
            "/admin/countries",
            json=payload,
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["iso2"] == "BR"
        assert data["continent_label"] == "Sudamérica"
        assert data["is_active"] is True

    async def test_iso2_duplicado_retorna_422(self, client, actor_token_countries):
        payload = {
            "name": {"es": "Brasil duplicado"},
            "iso2": "BR",
            "iso3": "BR2",
            "continent_code": "SA",
        }
        r = await client.post(
            "/admin/countries",
            json=payload,
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 422

    async def test_iso3_duplicado_retorna_422(self, client, actor_token_countries):
        payload = {
            "name": {"es": "Brasil dup iso3"},
            "iso2": "BX",
            "iso3": "BRA",
            "continent_code": "SA",
        }
        r = await client.post(
            "/admin/countries",
            json=payload,
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 422

    async def test_continent_code_invalido_retorna_422(self, client, actor_token_countries):
        payload = {
            "name": {"es": "País Inventado"},
            "iso2": "XX",
            "iso3": "XXX",
            "continent_code": "ZZ",
        }
        r = await client.post(
            "/admin/countries",
            json=payload,
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 422

    async def test_iso_se_guarda_en_mayusculas(self, client, actor_token_countries):
        payload = {
            "name": {"es": "Uruguay", "en": "Uruguay"},
            "iso2": "uy",
            "iso3": "ury",
            "continent_code": "SA",
        }
        r = await client.post(
            "/admin/countries",
            json=payload,
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["iso2"] == "UY"
        assert data["iso3"] == "URY"


# ─────────────────────── Countries: show ─────────────────────────────────────

class TestCountryShow:
    async def test_show_existente(self, client, actor_token_countries, seed_country_id):
        r = await client.get(
            f"/admin/countries/{seed_country_id}",
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 200
        assert r.json()["id"] == seed_country_id

    async def test_show_no_existente_retorna_404(self, client, actor_token_countries):
        r = await client.get(
            "/admin/countries/99999",
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 404


# ─────────────────────── Countries: update ───────────────────────────────────

class TestCountryUpdate:
    async def test_actualiza_phone_code(self, client, actor_token_countries, seed_country_id):
        r = await client.put(
            f"/admin/countries/{seed_country_id}",
            json={"phone_code": "549"},
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 200
        assert r.json()["phone_code"] == "549"

    async def test_actualiza_nombre(self, client, actor_token_countries, seed_country_id):
        r = await client.put(
            f"/admin/countries/{seed_country_id}",
            json={"name": {"es": "Argentina (upd)", "en": "Argentina (upd)"}},
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 200
        assert r.json()["name"]["es"] == "Argentina (upd)"

    async def test_update_no_existente_retorna_404(self, client, actor_token_countries):
        r = await client.put(
            "/admin/countries/99999",
            json={"phone_code": "0"},
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 404


# ─────────────────────── Countries: toggle-active ────────────────────────────

class TestCountryToggleActive:
    async def test_toggle_activa_desactiva(self, client, actor_token_countries, seed_country_id):
        r1 = await client.put(
            f"/admin/countries/{seed_country_id}/toggle-active",
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r1.status_code == 200
        assert r1.json()["is_active"] is False

        r2 = await client.put(
            f"/admin/countries/{seed_country_id}/toggle-active",
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r2.status_code == 200
        assert r2.json()["is_active"] is True

    async def test_toggle_no_existente_retorna_404(self, client, actor_token_countries):
        r = await client.put(
            "/admin/countries/99999/toggle-active",
            headers={"Authorization": f"Bearer {actor_token_countries}"},
        )
        assert r.status_code == 404


# ─────────────────────── Zones: index ────────────────────────────────────────

class TestZoneIndex:
    async def test_sin_token_retorna_401(self, client):
        r = await client.get("/admin/zones")
        assert r.status_code == 401

    async def test_lista_zonas(self, client, actor_token_admin, seed_zone_id):
        r = await client.get(
            "/admin/zones",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert any(z["id"] == seed_zone_id for z in data)

    async def test_zona_tiene_countries_count(self, client, actor_token_admin, seed_zone_id):
        r = await client.get(
            "/admin/zones",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        zone = next(z for z in r.json() if z["id"] == seed_zone_id)
        assert "countries_count" in zone


# ─────────────────────── Zones: store ────────────────────────────────────────

class TestZoneStore:
    async def test_crea_zona(self, client, actor_token_admin):
        r = await client.post(
            "/admin/zones",
            json={"name": "Europa del Norte", "description": "Países nórdicos"},
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Europa del Norte"
        assert data["is_active"] is True
        assert data["countries"] == []

    async def test_crea_zona_sin_descripcion(self, client, actor_token_admin):
        r = await client.post(
            "/admin/zones",
            json={"name": "Zona Sin Descripción"},
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 201
        assert r.json()["description"] is None


# ─────────────────────── Zones: show ─────────────────────────────────────────

class TestZoneShow:
    async def test_show_existente(self, client, actor_token_admin, seed_zone_id):
        r = await client.get(
            f"/admin/zones/{seed_zone_id}",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 200
        assert r.json()["id"] == seed_zone_id

    async def test_show_no_existente_retorna_404(self, client, actor_token_admin):
        r = await client.get(
            "/admin/zones/99999",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 404


# ─────────────────────── Zones: update ───────────────────────────────────────

class TestZoneUpdate:
    async def test_actualiza_nombre(self, client, actor_token_admin, seed_zone_id):
        r = await client.put(
            f"/admin/zones/{seed_zone_id}",
            json={"name": "Cono Sur Actualizado"},
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Cono Sur Actualizado"

    async def test_update_no_existente_retorna_404(self, client, actor_token_admin):
        r = await client.put(
            "/admin/zones/99999",
            json={"name": "Nada"},
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 404


# ─────────────────────── Zones: toggle-active ────────────────────────────────

class TestZoneToggleActive:
    async def test_toggle_activa_desactiva(self, client, actor_token_admin, seed_zone_id):
        r1 = await client.put(
            f"/admin/zones/{seed_zone_id}/toggle-active",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r1.status_code == 200
        assert r1.json()["is_active"] is False

        r2 = await client.put(
            f"/admin/zones/{seed_zone_id}/toggle-active",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r2.status_code == 200
        assert r2.json()["is_active"] is True


# ─────────────────────── Zones: manejo de países ─────────────────────────────

class TestZoneCountries:
    async def test_attach_country(
        self, client, actor_token_admin, seed_zone_id, async_engine
    ):
        """Asociar un país a una zona."""
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            country = Country(
                name=json.dumps({"es": "Chile", "en": "Chile"}),
                iso2="CL",
                iso3="CHL",
                continent_code="SA",
                is_active=True,
            )
            db.add(country)
            await db.commit()
            await db.refresh(country)
            country_id = country.id

        r = await client.post(
            f"/admin/zones/{seed_zone_id}/countries/{country_id}",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 200
        assert "asociado" in r.json()["message"]

        # Verificar que aparece en la zona
        r2 = await client.get(
            f"/admin/zones/{seed_zone_id}/countries",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r2.status_code == 200
        assert any(c["id"] == country_id for c in r2.json())

    async def test_attach_idempotente(
        self, client, actor_token_admin, seed_zone_id, async_engine
    ):
        """Asociar el mismo país dos veces no genera error."""
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            country = Country(
                name=json.dumps({"es": "Bolivia", "en": "Bolivia"}),
                iso2="BO",
                iso3="BOL",
                continent_code="SA",
                is_active=True,
            )
            db.add(country)
            await db.commit()
            await db.refresh(country)
            country_id = country.id

        r1 = await client.post(
            f"/admin/zones/{seed_zone_id}/countries/{country_id}",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r1.status_code == 200

        r2 = await client.post(
            f"/admin/zones/{seed_zone_id}/countries/{country_id}",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r2.status_code == 200  # idempotente

    async def test_attach_pais_no_existente_retorna_404(
        self, client, actor_token_admin, seed_zone_id
    ):
        r = await client.post(
            f"/admin/zones/{seed_zone_id}/countries/99999",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 404

    async def test_detach_country(
        self, client, actor_token_admin, seed_zone_id, async_engine
    ):
        """Desasociar un país de una zona."""
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            country = Country(
                name=json.dumps({"es": "Paraguay", "en": "Paraguay"}),
                iso2="PY",
                iso3="PRY",
                continent_code="SA",
                is_active=True,
            )
            db.add(country)
            await db.commit()
            await db.refresh(country)
            country_id = country.id

        # Asociar primero
        await client.post(
            f"/admin/zones/{seed_zone_id}/countries/{country_id}",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )

        # Desasociar
        r = await client.delete(
            f"/admin/zones/{seed_zone_id}/countries/{country_id}",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 200
        assert "desasociado" in r.json()["message"]

        # Verificar que ya no aparece
        r2 = await client.get(
            f"/admin/zones/{seed_zone_id}/countries",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert not any(c["id"] == country_id for c in r2.json())

    async def test_available_countries_tiene_attached(
        self, client, actor_token_admin, seed_zone_id
    ):
        """El endpoint available incluye la bandera 'attached'."""
        r = await client.get(
            f"/admin/zones/{seed_zone_id}/countries/available",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert all("attached" in c for c in data)
        assert all("continent_label" in c for c in data)

    async def test_zone_no_existente_retorna_404_en_countries(
        self, client, actor_token_admin
    ):
        r = await client.get(
            "/admin/zones/99999/countries",
            headers={"Authorization": f"Bearer {actor_token_admin}"},
        )
        assert r.status_code == 404
