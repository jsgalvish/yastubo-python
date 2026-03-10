"""
Tests de Step 6 — ACL Admin API (roles, permisos, matriz de asignación).

Estrategia:
- Actor = usuario admin con permiso system.roles asignado directamente.
- Fixtures de scope="module" con SQLite en memoria.
- seed_role_id / seed_permission_id: datos base reutilizados en múltiples tests.
- Cada test que crea datos usa nombres únicos para evitar colisiones.
"""
from __future__ import annotations

import bcrypt as _bcrypt_lib
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # registra todos los modelos en Base.metadata
from app.database import get_db
from app.main import app
from app.models import Base, Permission, User
from app.models.role import Role
from app.services.permission_service import PermissionService
from app.services.token_service import create_access_token


# ─────────────────────────── Fixtures ────────────────────────────────────────


@pytest_asyncio.fixture(scope="module")
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def actor_token(async_engine):
    """Crea un usuario actor con permiso system.roles y retorna su token."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        actor = User(
            realm="admin",
            email="acl_actor@admintest.com",
            password=_bcrypt_lib.hashpw(b"ActorPass1!", _bcrypt_lib.gensalt()).decode(),
            first_name="ACL",
            last_name="Actor",
            status="active",
            force_password_change=False,
        )
        session.add(actor)
        await session.flush()

        svc = PermissionService(session)
        perm = Permission(name="system.roles", guard_name="admin")
        session.add(perm)
        await session.flush()
        await svc.give_permission(actor, perm)

        await session.commit()
        return create_access_token(actor.id, "admin")


@pytest_asyncio.fixture(scope="module")
async def seed_role_id(async_engine):
    """Rol de prueba base reutilizado por varios tests (update, toggle)."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        role = Role(name="acl.seed.role", guard_name="admin")
        session.add(role)
        await session.commit()
        await session.refresh(role)
        return role.id


@pytest_asyncio.fixture(scope="module")
async def seed_permission_id(async_engine):
    """Permiso de prueba base reutilizado por varios tests (update, toggle)."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        perm = Permission(name="acl.seed.perm", guard_name="admin")
        session.add(perm)
        await session.commit()
        await session.refresh(perm)
        return perm.id


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


# ─────────────────────────── Helper ──────────────────────────────────────────


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─────────────── GET /admin/acl/roles/{guard}/matrix ─────────────────────────


class TestMatrixData:
    @pytest.mark.asyncio
    async def test_sin_auth_retorna_401(self, client: AsyncClient):
        r = await client.get("/admin/acl/roles/admin/matrix")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_guard_invalido_retorna_404(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.get(
            "/admin/acl/roles/invalid_guard/matrix",
            headers=_auth(actor_token),
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_retorna_estructura_correcta(
        self,
        client: AsyncClient,
        actor_token: str,
        seed_role_id: int,
        seed_permission_id: int,
    ):
        r = await client.get(
            "/admin/acl/roles/admin/matrix",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "roles" in data
        assert "permissions" in data
        assert "matrix" in data
        # El seed_role debe aparecer en la lista
        role_ids = [role["id"] for role in data["roles"]]
        assert seed_role_id in role_ids
        # matrix contiene clave para cada rol
        assert str(seed_role_id) in data["matrix"]

    @pytest.mark.asyncio
    async def test_customer_guard_retorna_solo_sus_datos(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.get(
            "/admin/acl/roles/customer/matrix",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        data = r.json()
        # Los roles del guard admin no deben aparecer en customer
        for role in data["roles"]:
            assert role["guard_name"] == "customer"


# ─────────────── POST /admin/acl/roles/{guard}/roles ─────────────────────────


class TestStoreRole:
    @pytest.mark.asyncio
    async def test_sin_auth_retorna_401(self, client: AsyncClient):
        r = await client.post("/admin/acl/roles/admin/roles", json={"name": "x"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_crea_rol(self, client: AsyncClient, actor_token: str):
        r = await client.post(
            "/admin/acl/roles/admin/roles",
            headers=_auth(actor_token),
            json={"name": "store.new.role"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "store.new.role"
        assert data["guard_name"] == "admin"
        assert data["id"] > 0

    @pytest.mark.asyncio
    async def test_crea_rol_con_label_y_scope(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.post(
            "/admin/acl/roles/admin/roles",
            headers=_auth(actor_token),
            json={
                "name": "store.role.with.label",
                "label": {"es": "Rol etiquetado", "en": "Labeled role"},
                "scope": "system",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["label"] == {"es": "Rol etiquetado", "en": "Labeled role"}
        assert data["scope"] == "system"

    @pytest.mark.asyncio
    async def test_nombre_duplicado_retorna_422(
        self, client: AsyncClient, actor_token: str, seed_role_id: int
    ):
        # Intentar crear un rol con el mismo nombre que el seed
        r = await client.post(
            "/admin/acl/roles/admin/roles",
            headers=_auth(actor_token),
            json={"name": "acl.seed.role"},  # ya existe
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_mismo_nombre_diferente_guard_es_valido(
        self, client: AsyncClient, actor_token: str
    ):
        # El mismo nombre en diferente guard no es duplicado
        r = await client.post(
            "/admin/acl/roles/customer/roles",
            headers=_auth(actor_token),
            json={"name": "acl.seed.role"},  # existe en admin, no en customer
        )
        assert r.status_code == 201

    @pytest.mark.asyncio
    async def test_guard_invalido_retorna_404(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.post(
            "/admin/acl/roles/superadmin/roles",
            headers=_auth(actor_token),
            json={"name": "role.name"},
        )
        assert r.status_code == 404


# ─────────────── PUT /admin/acl/roles/{guard}/roles/{role_id} ────────────────


class TestUpdateRole:
    @pytest.mark.asyncio
    async def test_sin_auth_retorna_401(
        self, client: AsyncClient, seed_role_id: int
    ):
        r = await client.put(
            f"/admin/acl/roles/admin/roles/{seed_role_id}",
            json={"name": "nuevo"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_actualiza_nombre(
        self, client: AsyncClient, actor_token: str, seed_role_id: int
    ):
        r = await client.put(
            f"/admin/acl/roles/admin/roles/{seed_role_id}",
            headers=_auth(actor_token),
            json={"name": "acl.seed.role.updated"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "acl.seed.role.updated"

    @pytest.mark.asyncio
    async def test_partial_update_solo_scope(
        self, client: AsyncClient, actor_token: str, seed_role_id: int
    ):
        # Solo enviamos scope, el nombre no debe cambiar
        r = await client.put(
            f"/admin/acl/roles/admin/roles/{seed_role_id}",
            headers=_auth(actor_token),
            json={"scope": "unit"},
        )
        assert r.status_code == 200
        assert r.json()["scope"] == "unit"

    @pytest.mark.asyncio
    async def test_rol_no_encontrado_retorna_404(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.put(
            "/admin/acl/roles/admin/roles/999999",
            headers=_auth(actor_token),
            json={"name": "fantasma"},
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_guard_mismatch_retorna_404(
        self, client: AsyncClient, actor_token: str, seed_role_id: int
    ):
        # El rol existe en admin, se intenta actualizar vía customer → 404
        r = await client.put(
            f"/admin/acl/roles/customer/roles/{seed_role_id}",
            headers=_auth(actor_token),
            json={"name": "cross.guard"},
        )
        assert r.status_code == 404


# ─────────────── POST /admin/acl/roles/{guard}/permissions ───────────────────


class TestStorePermission:
    @pytest.mark.asyncio
    async def test_sin_auth_retorna_401(self, client: AsyncClient):
        r = await client.post(
            "/admin/acl/roles/admin/permissions", json={"name": "x"}
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_crea_permiso(self, client: AsyncClient, actor_token: str):
        r = await client.post(
            "/admin/acl/roles/admin/permissions",
            headers=_auth(actor_token),
            json={"name": "store.new.perm", "description": "Permiso de prueba"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "store.new.perm"
        assert data["guard_name"] == "admin"
        assert data["description"] == "Permiso de prueba"

    @pytest.mark.asyncio
    async def test_nombre_duplicado_retorna_422(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.post(
            "/admin/acl/roles/admin/permissions",
            headers=_auth(actor_token),
            json={"name": "acl.seed.perm"},  # ya existe
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_guard_invalido_retorna_404(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.post(
            "/admin/acl/roles/invalidguard/permissions",
            headers=_auth(actor_token),
            json={"name": "perm.name"},
        )
        assert r.status_code == 404


# ─────────────── PUT /admin/acl/roles/{guard}/permissions/{perm_id} ──────────


class TestUpdatePermission:
    @pytest.mark.asyncio
    async def test_sin_auth_retorna_401(
        self, client: AsyncClient, seed_permission_id: int
    ):
        r = await client.put(
            f"/admin/acl/roles/admin/permissions/{seed_permission_id}",
            json={"name": "nuevo"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_actualiza_descripcion(
        self, client: AsyncClient, actor_token: str, seed_permission_id: int
    ):
        r = await client.put(
            f"/admin/acl/roles/admin/permissions/{seed_permission_id}",
            headers=_auth(actor_token),
            json={"description": "Descripción actualizada"},
        )
        assert r.status_code == 200
        assert r.json()["description"] == "Descripción actualizada"

    @pytest.mark.asyncio
    async def test_partial_update_solo_nombre(
        self, client: AsyncClient, actor_token: str, seed_permission_id: int
    ):
        r = await client.put(
            f"/admin/acl/roles/admin/permissions/{seed_permission_id}",
            headers=_auth(actor_token),
            json={"name": "acl.seed.perm.updated"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "acl.seed.perm.updated"

    @pytest.mark.asyncio
    async def test_permiso_no_encontrado_retorna_404(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.put(
            "/admin/acl/roles/admin/permissions/999999",
            headers=_auth(actor_token),
            json={"name": "fantasma"},
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_guard_mismatch_retorna_404(
        self, client: AsyncClient, actor_token: str, seed_permission_id: int
    ):
        r = await client.put(
            f"/admin/acl/roles/customer/permissions/{seed_permission_id}",
            headers=_auth(actor_token),
            json={"name": "cross.guard.perm"},
        )
        assert r.status_code == 404


# ─────────────── POST /admin/acl/roles/{guard}/toggle ────────────────────────


class TestToggleAssignment:
    @pytest.mark.asyncio
    async def test_sin_auth_retorna_401(
        self, client: AsyncClient, seed_role_id: int, seed_permission_id: int
    ):
        r = await client.post(
            "/admin/acl/roles/admin/toggle",
            json={
                "role_id": seed_role_id,
                "permission_id": seed_permission_id,
                "value": True,
            },
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_asigna_permiso_a_rol(
        self,
        client: AsyncClient,
        actor_token: str,
        seed_role_id: int,
        seed_permission_id: int,
    ):
        r = await client.post(
            "/admin/acl/roles/admin/toggle",
            headers=_auth(actor_token),
            json={
                "role_id": seed_role_id,
                "permission_id": seed_permission_id,
                "value": True,
            },
        )
        assert r.status_code == 200
        assert "message" in r.json()

    @pytest.mark.asyncio
    async def test_idempotente_asignar_ya_asignado(
        self,
        client: AsyncClient,
        actor_token: str,
        seed_role_id: int,
        seed_permission_id: int,
    ):
        # Asignar de nuevo no debe fallar
        r = await client.post(
            "/admin/acl/roles/admin/toggle",
            headers=_auth(actor_token),
            json={
                "role_id": seed_role_id,
                "permission_id": seed_permission_id,
                "value": True,
            },
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_matrix_refleja_asignacion(
        self,
        client: AsyncClient,
        actor_token: str,
        seed_role_id: int,
        seed_permission_id: int,
    ):
        r = await client.get(
            "/admin/acl/roles/admin/matrix",
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        matrix = r.json()["matrix"]
        assert seed_permission_id in matrix[str(seed_role_id)]

    @pytest.mark.asyncio
    async def test_revoca_permiso_de_rol(
        self,
        client: AsyncClient,
        actor_token: str,
        seed_role_id: int,
        seed_permission_id: int,
    ):
        r = await client.post(
            "/admin/acl/roles/admin/toggle",
            headers=_auth(actor_token),
            json={
                "role_id": seed_role_id,
                "permission_id": seed_permission_id,
                "value": False,
            },
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_idempotente_revocar_ya_revocado(
        self,
        client: AsyncClient,
        actor_token: str,
        seed_role_id: int,
        seed_permission_id: int,
    ):
        # Revocar de nuevo no debe fallar
        r = await client.post(
            "/admin/acl/roles/admin/toggle",
            headers=_auth(actor_token),
            json={
                "role_id": seed_role_id,
                "permission_id": seed_permission_id,
                "value": False,
            },
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_rol_no_encontrado_retorna_404(
        self, client: AsyncClient, actor_token: str, seed_permission_id: int
    ):
        r = await client.post(
            "/admin/acl/roles/admin/toggle",
            headers=_auth(actor_token),
            json={
                "role_id": 999999,
                "permission_id": seed_permission_id,
                "value": True,
            },
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_permiso_no_encontrado_retorna_404(
        self, client: AsyncClient, actor_token: str, seed_role_id: int
    ):
        r = await client.post(
            "/admin/acl/roles/admin/toggle",
            headers=_auth(actor_token),
            json={
                "role_id": seed_role_id,
                "permission_id": 999999,
                "value": True,
            },
        )
        assert r.status_code == 404
