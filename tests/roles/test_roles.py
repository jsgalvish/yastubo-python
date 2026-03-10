"""
Tests de Step 4 — Roles y permisos (Spatie-like).

Estrategia:
- TestPermissionModel: constantes y columnas del modelo Permission.
- TestRoleModel: relación Role ↔ Permission.
- TestPermissionService: assign/revoke roles y permisos, user_can, user_has_role.
- TestPermissionMiddleware: endpoints protegidos con require_permission / require_role.
- TestUserHelpers: métodos has_role() y can() sobre caches.
"""
from __future__ import annotations

import bcrypt as _bcrypt_lib
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # asegura que Base.metadata tenga todos los modelos
from app.database import get_db
from app.main import app
from app.models import Base, Permission, Role, User
from app.models.permission import USER_MODEL_TYPE
from app.services.permission_service import PermissionService
from app.services.token_service import create_access_token


# ─────────────────────────── Fixtures SQLite ────────────────────────────────


@pytest_asyncio.fixture(scope="module")
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine):
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(async_engine):
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


# ─────────────────────────── Helpers ────────────────────────────────────────


def _make_user(**kwargs) -> User:
    defaults = {
        "realm": "admin",
        "email": "default@roles.test",
        "password": _bcrypt_lib.hashpw(b"TestPass123!", _bcrypt_lib.gensalt()).decode(),
        "first_name": "Test",
        "last_name": "User",
        "status": "active",
        "force_password_change": False,
    }
    defaults.update(kwargs)
    return User(**defaults)


def _make_role(**kwargs) -> Role:
    defaults = {"name": "test.role", "guard_name": "admin"}
    defaults.update(kwargs)
    return Role(**defaults)


def _make_permission(**kwargs) -> Permission:
    defaults = {"name": "test.permission", "guard_name": "admin"}
    defaults.update(kwargs)
    return Permission(**defaults)


# ─────────────────────────── Modelo Permission ───────────────────────────────


class TestPermissionModel:
    def test_tablename(self):
        assert Permission.__tablename__ == "permissions"

    def test_columnas_requeridas(self):
        cols = {c.name for c in Permission.__table__.columns}
        assert {"id", "name", "guard_name", "description", "created_at", "updated_at"} <= cols

    def test_user_model_type_constante(self):
        assert USER_MODEL_TYPE == "App\\Models\\User"

    def test_tablas_asociacion_existen(self):
        from app.models.permission import (
            model_has_permissions,
            model_has_roles,
            role_has_permissions,
        )
        assert model_has_roles.name == "model_has_roles"
        assert model_has_permissions.name == "model_has_permissions"
        assert role_has_permissions.name == "role_has_permissions"


# ─────────────────────────── PermissionService ───────────────────────────────


class TestPermissionService:
    @pytest.mark.asyncio
    async def test_assign_role_y_get_roles(self, db_session: AsyncSession):
        user = _make_user(email="svc_assignrole@test.com")
        role = _make_role(name="editor", guard_name="admin")
        db_session.add(user)
        db_session.add(role)
        await db_session.flush()

        svc = PermissionService(db_session)
        await svc.assign_role(user, role)
        await db_session.flush()

        roles = await svc.get_roles(user)
        assert any(r.name == "editor" for r in roles)

    @pytest.mark.asyncio
    async def test_assign_role_idempotente(self, db_session: AsyncSession):
        """Asignar el mismo rol dos veces no debe lanzar error."""
        user = _make_user(email="svc_idem@test.com")
        role = _make_role(name="viewer", guard_name="admin")
        db_session.add(user)
        db_session.add(role)
        await db_session.flush()

        svc = PermissionService(db_session)
        await svc.assign_role(user, role)
        await svc.assign_role(user, role)  # segunda vez: debe ser no-op
        await db_session.flush()

        roles = await svc.get_roles(user)
        assert sum(1 for r in roles if r.name == "viewer") == 1

    @pytest.mark.asyncio
    async def test_remove_role(self, db_session: AsyncSession):
        user = _make_user(email="svc_remrole@test.com")
        role = _make_role(name="to_remove", guard_name="admin")
        db_session.add(user)
        db_session.add(role)
        await db_session.flush()

        svc = PermissionService(db_session)
        await svc.assign_role(user, role)
        await db_session.flush()

        await svc.remove_role(user, role)
        await db_session.flush()

        roles = await svc.get_roles(user)
        assert not any(r.name == "to_remove" for r in roles)

    @pytest.mark.asyncio
    async def test_user_has_role(self, db_session: AsyncSession):
        user = _make_user(email="svc_hasrole@test.com")
        role = _make_role(name="manager", guard_name="admin")
        db_session.add(user)
        db_session.add(role)
        await db_session.flush()

        svc = PermissionService(db_session)
        assert not await svc.user_has_role(user, "manager")

        await svc.assign_role(user, role)
        await db_session.flush()

        assert await svc.user_has_role(user, "manager")
        assert await svc.user_has_role(user, "manager", guard_name="admin")
        assert not await svc.user_has_role(user, "manager", guard_name="customer")

    @pytest.mark.asyncio
    async def test_give_permission_to_role_y_user_can(self, db_session: AsyncSession):
        user = _make_user(email="svc_canviarole@test.com")
        role = _make_role(name="analyst", guard_name="admin")
        perm = _make_permission(name="reports.view", guard_name="admin")
        db_session.add(user)
        db_session.add(role)
        db_session.add(perm)
        await db_session.flush()

        svc = PermissionService(db_session)

        # Sin rol → no tiene permiso
        assert not await svc.user_can(user, "reports.view")

        # Asignar permiso al rol, asignar rol al usuario
        await svc.give_permission_to_role(role, perm)
        await svc.assign_role(user, role)
        await db_session.flush()

        assert await svc.user_can(user, "reports.view")

    @pytest.mark.asyncio
    async def test_give_permission_directo(self, db_session: AsyncSession):
        user = _make_user(email="svc_directperm@test.com")
        perm = _make_permission(name="direct.perm", guard_name="admin")
        db_session.add(user)
        db_session.add(perm)
        await db_session.flush()

        svc = PermissionService(db_session)
        assert not await svc.user_can(user, "direct.perm")

        await svc.give_permission(user, perm)
        await db_session.flush()

        assert await svc.user_can(user, "direct.perm")

    @pytest.mark.asyncio
    async def test_revoke_permission_from_role(self, db_session: AsyncSession):
        user = _make_user(email="svc_revoke@test.com")
        role = _make_role(name="revoke_role", guard_name="admin")
        perm = _make_permission(name="revoke.perm", guard_name="admin")
        db_session.add(user)
        db_session.add(role)
        db_session.add(perm)
        await db_session.flush()

        svc = PermissionService(db_session)
        await svc.give_permission_to_role(role, perm)
        await svc.assign_role(user, role)
        await db_session.flush()

        assert await svc.user_can(user, "revoke.perm")

        await svc.revoke_permission_from_role(role, perm)
        await db_session.flush()

        assert not await svc.user_can(user, "revoke.perm")

    @pytest.mark.asyncio
    async def test_load_roles_cache(self, db_session: AsyncSession):
        user = _make_user(email="svc_cache@test.com")
        role = _make_role(name="cached_role", guard_name="admin")
        db_session.add(user)
        db_session.add(role)
        await db_session.flush()

        svc = PermissionService(db_session)
        await svc.assign_role(user, role)
        await db_session.flush()

        await svc.load_roles(user)
        assert user.has_role("cached_role")
        assert not user.has_role("nonexistent")

    @pytest.mark.asyncio
    async def test_load_permissions_cache(self, db_session: AsyncSession):
        user = _make_user(email="svc_permcache@test.com")
        perm = _make_permission(name="cached.perm", guard_name="admin")
        db_session.add(user)
        db_session.add(perm)
        await db_session.flush()

        svc = PermissionService(db_session)
        await svc.give_permission(user, perm)
        await db_session.flush()

        await svc.load_permissions(user)
        assert user.can("cached.perm")
        assert not user.can("other.perm")


# ─────────────────────────── Helpers en User ─────────────────────────────────


class TestUserHelpers:
    def test_has_role_sin_cache_retorna_false(self):
        u = User()
        assert u.has_role("any") is False

    def test_can_sin_cache_retorna_false(self):
        u = User()
        assert u.can("any.perm") is False

    def test_has_role_con_cache(self):
        u = User()
        r = Role(name="admin_role", guard_name="admin")
        u._roles_cache = [r]  # type: ignore[attr-defined]
        assert u.has_role("admin_role") is True
        assert u.has_role("admin_role", guard_name="admin") is True
        assert u.has_role("admin_role", guard_name="customer") is False

    def test_can_con_cache(self):
        u = User()
        u._permissions_cache = {"reports.view", "users.edit"}  # type: ignore[attr-defined]
        assert u.can("reports.view") is True
        assert u.can("users.edit") is True
        assert u.can("users.delete") is False


# ─────────────────────────── Middleware endpoints ────────────────────────────


class TestPermissionMiddleware:
    @pytest.mark.asyncio
    async def test_require_permission_con_permiso(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Usuario con el permiso requerido accede al endpoint."""
        from fastapi import Depends
        from app.http.middleware.permission import require_permission

        # Registrar endpoint temporal
        @app.get("/test-perm-ok")
        async def _ep(u: User = Depends(require_permission("dash.view"))):
            return {"ok": True}

        user = _make_user(email="mw_ok@test.com", realm="admin")
        perm = _make_permission(name="dash.view", guard_name="admin")
        db_session.add(user)
        db_session.add(perm)
        await db_session.commit()

        svc = PermissionService(db_session)
        await svc.give_permission(user, perm)
        await db_session.commit()

        token = create_access_token(user.id, "admin")
        r = await client.get(
            "/test-perm-ok", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200

        app.routes[:] = [rt for rt in app.routes if getattr(rt, "path", "") != "/test-perm-ok"]

    @pytest.mark.asyncio
    async def test_require_permission_sin_permiso_retorna_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Usuario sin el permiso requerido recibe 403."""
        from app.http.middleware.permission import require_permission
        from fastapi import Depends

        @app.get("/test-perm-403")
        async def _ep(u: User = Depends(require_permission("secret.action"))):
            return {"ok": True}

        user = _make_user(email="mw_403@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, "admin")
        r = await client.get(
            "/test-perm-403", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 403

        app.routes[:] = [rt for rt in app.routes if getattr(rt, "path", "") != "/test-perm-403"]

    @pytest.mark.asyncio
    async def test_require_role_con_rol(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Usuario con el rol requerido accede al endpoint."""
        from app.http.middleware.permission import require_role
        from fastapi import Depends

        @app.get("/test-role-ok")
        async def _ep(u: User = Depends(require_role("superadmin"))):
            return {"ok": True}

        user = _make_user(email="mw_role_ok@test.com", realm="admin")
        role = _make_role(name="superadmin", guard_name="admin")
        db_session.add(user)
        db_session.add(role)
        await db_session.commit()

        svc = PermissionService(db_session)
        await svc.assign_role(user, role)
        await db_session.commit()

        token = create_access_token(user.id, "admin")
        r = await client.get(
            "/test-role-ok", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200

        app.routes[:] = [rt for rt in app.routes if getattr(rt, "path", "") != "/test-role-ok"]

    @pytest.mark.asyncio
    async def test_require_role_sin_rol_retorna_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Usuario sin el rol requerido recibe 403."""
        from app.http.middleware.permission import require_role
        from fastapi import Depends

        @app.get("/test-role-403")
        async def _ep(u: User = Depends(require_role("superadmin_exclusive"))):
            return {"ok": True}

        user = _make_user(email="mw_role_403@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, "admin")
        r = await client.get(
            "/test-role-403", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 403

        app.routes[:] = [rt for rt in app.routes if getattr(rt, "path", "") != "/test-role-403"]
