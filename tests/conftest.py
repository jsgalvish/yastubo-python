"""
Fixtures compartidos para todos los tests del proyecto.

Centraliza la infraestructura de testing (engine, client, helpers)
para evitar duplicación entre archivos de test.

Referencia skill: python-testing → conftest.py for shared fixtures.
"""

from __future__ import annotations

import bcrypt as _bcrypt_lib
import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app
from app.models import Base, Permission, User
from app.services.permission_service import PermissionService
from app.services.token_service import create_access_token

# ─────────────────────── Helpers ─────────────────────────────────────────────


def hashed(pw: str) -> str:
    """Hashea un password con bcrypt (helper para fixtures de test)."""
    return _bcrypt_lib.hashpw(pw.encode(), _bcrypt_lib.gensalt()).decode()


# ─────────────────────── Engine (module-scoped) ──────────────────────────────


@pytest_asyncio.fixture(scope="module")
async def async_engine():
    """SQLite en memoria, scoped por módulo de test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


# ─────────────────────── Client (function-scoped) ────────────────────────────


@pytest_asyncio.fixture
async def client(async_engine):
    """AsyncClient HTTP apuntando al app FastAPI con DB override."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ─────────────────────── Token factory ───────────────────────────────────────


async def create_actor_token(
    async_engine,
    *,
    email: str,
    permission: str,
    first_name: str = "Test",
    last_name: str = "Actor",
) -> str:
    """
    Crea un usuario admin con un permiso específico y retorna su JWT.
    Helper reutilizable para cualquier test que necesite auth.
    """
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        actor = User(
            realm="admin",
            email=email,
            password=hashed("ActorPass1!"),
            first_name=first_name,
            last_name=last_name,
            status="active",
            force_password_change=False,
        )
        db.add(actor)
        await db.flush()

        perm = Permission(name=permission, guard_name="admin")
        db.add(perm)
        await db.flush()

        svc = PermissionService(db)
        await svc.give_permission(actor, perm)
        await db.commit()

        return create_access_token(actor.id, "admin")
