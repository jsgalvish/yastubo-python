"""
Tests de Step 5 — Gestión de usuarios admin (CRUD + soft-delete + restore).

Estrategia:
- Actor = usuario admin con permisos users.* asignados directamente.
- Fixtures de scope="module" con SQLite en memoria.
- Commit en fixtures de setup (necesario para que el client vea los datos).
- Cada test que crea datos usa emails únicos para evitar colisiones.
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
from app.models.staff_profile import StaffProfile
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
    """Crea un usuario actor con todos los permisos users.* y retorna su token."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        actor = User(
            realm="admin",
            email="actor@admintest.com",
            password=_bcrypt_lib.hashpw(b"ActorPass1!", _bcrypt_lib.gensalt()).decode(),
            first_name="Actor",
            last_name="Test",
            status="active",
            force_password_change=False,
        )
        session.add(actor)
        await session.flush()

        svc = PermissionService(session)
        for perm_name in [
            "users.viewAny",
            "users.view",
            "users.create",
            "users.update",
            "users.delete",
            "users.restore",
        ]:
            perm = Permission(name=perm_name, guard_name="admin")
            session.add(perm)
            await session.flush()
            await svc.give_permission(actor, perm)

        await session.commit()
        return create_access_token(actor.id, "admin")


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


# ─────────────────────────── Helpers ─────────────────────────────────────────


def _make_user(**kwargs) -> User:
    defaults = {
        "realm": "admin",
        "email": "default@admintest.com",
        "password": _bcrypt_lib.hashpw(b"Pass1234!", _bcrypt_lib.gensalt()).decode(),
        "first_name": "Juan",
        "last_name": "Pérez",
        "status": "active",
        "force_password_change": False,
    }
    defaults.update(kwargs)
    return User(**defaults)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────── GET /admin/users ─────────────────────────────────


class TestUserIndex:
    @pytest.mark.asyncio
    async def test_sin_auth_retorna_401(self, client: AsyncClient):
        r = await client.get("/admin/users")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_lista_vacia_retorna_paginacion(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.get("/admin/users", headers=_auth(actor_token))
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "meta" in body
        assert "pagination" in body["meta"]

    @pytest.mark.asyncio
    async def test_lista_incluye_usuarios_admin(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        # Crear usuarios en DB (commit para que el client los vea)
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u1 = _make_user(email="index_u1@admintest.com", first_name="Alice")
            u2 = _make_user(email="index_u2@admintest.com", first_name="Bob")
            session.add_all([u1, u2])
            await session.commit()

        r = await client.get("/admin/users", headers=_auth(actor_token))
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()["data"]]
        assert "index_u1@admintest.com" in emails
        assert "index_u2@admintest.com" in emails

    @pytest.mark.asyncio
    async def test_excluye_realm_customer(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            cu = _make_user(email="customer_hidden@admintest.com", realm="customer")
            session.add(cu)
            await session.commit()

        r = await client.get("/admin/users", headers=_auth(actor_token))
        emails = [u["email"] for u in r.json()["data"]]
        assert "customer_hidden@admintest.com" not in emails

    @pytest.mark.asyncio
    async def test_excluye_soft_deleted(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        from datetime import datetime, timezone

        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            du = _make_user(email="deleted_hidden@admintest.com")
            du.deleted_at = datetime.now(timezone.utc)
            session.add(du)
            await session.commit()

        r = await client.get("/admin/users", headers=_auth(actor_token))
        emails = [u["email"] for u in r.json()["data"]]
        assert "deleted_hidden@admintest.com" not in emails

    @pytest.mark.asyncio
    async def test_filtro_status(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            active = _make_user(email="flt_active@admintest.com", status="active")
            suspended = _make_user(email="flt_suspended@admintest.com", status="suspended")
            session.add_all([active, suspended])
            await session.commit()

        r = await client.get(
            "/admin/users", params={"status": "suspended"}, headers=_auth(actor_token)
        )
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()["data"]]
        assert "flt_suspended@admintest.com" in emails
        assert "flt_active@admintest.com" not in emails

    @pytest.mark.asyncio
    async def test_filtro_q(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="buscar_xyz@admintest.com", first_name="Zorbaz")
            session.add(u)
            await session.commit()

        r = await client.get(
            "/admin/users", params={"q": "Zorba"}, headers=_auth(actor_token)
        )
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()["data"]]
        assert "buscar_xyz@admintest.com" in emails

    @pytest.mark.asyncio
    async def test_paginacion(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.get(
            "/admin/users", params={"per_page": 2, "page": 1}, headers=_auth(actor_token)
        )
        assert r.status_code == 200
        meta = r.json()["meta"]["pagination"]
        assert meta["per_page"] == 2
        assert meta["current_page"] == 1
        assert "total" in meta
        assert "last_page" in meta


# ─────────────────────────── GET /admin/users/search ─────────────────────────


class TestUserSearch:
    @pytest.mark.asyncio
    async def test_sin_auth_retorna_401(self, client: AsyncClient):
        r = await client.get("/admin/users/search")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_search_retorna_formato_correcto(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(
                email="srch_format@admintest.com",
                first_name="Busca",
                last_name="Me",
                display_name="Buscame Display",
            )
            session.add(u)
            await session.commit()

        r = await client.get(
            "/admin/users/search",
            params={"q": "Buscame"},
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "meta" in body
        item = next((x for x in body["data"] if x["email"] == "srch_format@admintest.com"), None)
        assert item is not None
        assert "id" in item
        assert "display_name" in item
        assert "email" in item
        assert "status" in item

    @pytest.mark.asyncio
    async def test_search_display_name_fallback(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        """Sin display_name, retorna first_name + last_name."""
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(
                email="srch_nodisplay@admintest.com",
                first_name="Carlos",
                last_name="López",
                display_name=None,
            )
            session.add(u)
            await session.commit()

        r = await client.get(
            "/admin/users/search",
            params={"q": "nodisplay"},
            headers=_auth(actor_token),
        )
        item = next(
            (x for x in r.json()["data"] if x["email"] == "srch_nodisplay@admintest.com"), None
        )
        assert item is not None
        assert item["display_name"] == "Carlos López"


# ─────────────────────────── POST /admin/users ───────────────────────────────


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_sin_auth_retorna_401(self, client: AsyncClient):
        r = await client.post("/admin/users", json={"email": "x@x.com", "first_name": "X"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_crear_usuario_minimo(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.post(
            "/admin/users",
            json={"first_name": "Maria", "email": "create_min@admintest.com"},
            headers=_auth(actor_token),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["email"] == "create_min@admintest.com"
        assert body["realm"] == "admin"
        assert body["force_password_change"] is True
        assert body["last_name"] == ""  # last_name NOT NULL: se guarda como ""
        assert body["roles"] == []
        assert body["staff_profile"] is None

    @pytest.mark.asyncio
    async def test_crear_con_todos_los_campos(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.post(
            "/admin/users",
            json={
                "first_name": "Pedro",
                "last_name": "Gómez",
                "display_name": "Pedro G.",
                "email": "create_full@admintest.com",
                "status": "suspended",
                "work_phone": "+56912345678",
            },
            headers=_auth(actor_token),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["last_name"] == "Gómez"
        assert body["display_name"] == "Pedro G."
        assert body["status"] == "suspended"
        assert body["staff_profile"]["work_phone"] == "+56912345678"

    @pytest.mark.asyncio
    async def test_email_duplicado_retorna_422(
        self, client: AsyncClient, actor_token: str
    ):
        payload = {"first_name": "Dup", "email": "create_dup@admintest.com"}
        r1 = await client.post("/admin/users", json=payload, headers=_auth(actor_token))
        assert r1.status_code == 201
        r2 = await client.post("/admin/users", json=payload, headers=_auth(actor_token))
        assert r2.status_code == 422

    @pytest.mark.asyncio
    async def test_email_se_almacena_en_minusculas(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.post(
            "/admin/users",
            json={"first_name": "Up", "email": "CREATE_UPPER@ADMINTEST.COM"},
            headers=_auth(actor_token),
        )
        assert r.status_code == 201
        assert r.json()["email"] == "create_upper@admintest.com"

    @pytest.mark.asyncio
    async def test_vendedor_regular_requiere_comisiones(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        """Si el rol es vendedor_regular, las comisiones son obligatorias."""
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.models.role import Role

        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            role = Role(name="vendedor_regular", guard_name="admin")
            session.add(role)
            await session.commit()

        r = await client.post(
            "/admin/users",
            json={
                "first_name": "Vendor",
                "email": "create_vendor@admintest.com",
                "roles": ["vendedor_regular"],
                # sin comisiones → debe fallar
            },
            headers=_auth(actor_token),
        )
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert "commission_regular_first_year_pct" in detail

    @pytest.mark.asyncio
    async def test_crear_con_rol(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        from app.models.role import Role

        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            role = Role(name="operador", guard_name="admin")
            session.add(role)
            await session.commit()

        r = await client.post(
            "/admin/users",
            json={
                "first_name": "Con",
                "last_name": "Rol",
                "email": "create_conrol@admintest.com",
                "roles": ["operador"],
            },
            headers=_auth(actor_token),
        )
        assert r.status_code == 201
        assert "operador" in r.json()["roles"]


# ─────────────────────────── GET /admin/users/{id} ───────────────────────────


class TestShowUser:
    @pytest.mark.asyncio
    async def test_sin_auth_retorna_401(self, client: AsyncClient):
        r = await client.get("/admin/users/999")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_show_usuario_existente(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="show_ok@admintest.com", first_name="Visible")
            profile = None
            session.add(u)
            await session.flush()
            profile = StaffProfile(user_id=u.id, work_phone="+56999999999")
            session.add(profile)
            await session.commit()
            uid = u.id

        r = await client.get(f"/admin/users/{uid}", headers=_auth(actor_token))
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "show_ok@admintest.com"
        assert body["staff_profile"]["work_phone"] == "+56999999999"

    @pytest.mark.asyncio
    async def test_show_no_encontrado_retorna_404(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.get("/admin/users/999999", headers=_auth(actor_token))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_show_deleted_retorna_404(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        from datetime import datetime, timezone

        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="show_deleted@admintest.com")
            u.deleted_at = datetime.now(timezone.utc)
            session.add(u)
            await session.commit()
            uid = u.id

        r = await client.get(f"/admin/users/{uid}", headers=_auth(actor_token))
        assert r.status_code == 404


# ─────────────────────────── PUT /admin/users/{id} ───────────────────────────


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_actualiza_campos_basicos(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="upd_basic@admintest.com", first_name="Original")
            session.add(u)
            await session.commit()
            uid = u.id

        r = await client.put(
            f"/admin/users/{uid}",
            json={
                "first_name": "Actualizado",
                "last_name": "Nuevo",
                "email": "upd_basic@admintest.com",
                "status": "suspended",
            },
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["first_name"] == "Actualizado"
        assert body["status"] == "suspended"

    @pytest.mark.asyncio
    async def test_email_duplicado_falla(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u1 = _make_user(email="upd_dup1@admintest.com")
            u2 = _make_user(email="upd_dup2@admintest.com")
            session.add_all([u1, u2])
            await session.commit()
            uid2 = u2.id

        # Intentar cambiar email de u2 al de u1
        r = await client.put(
            f"/admin/users/{uid2}",
            json={
                "first_name": "X",
                "last_name": "X",
                "email": "upd_dup1@admintest.com",
                "status": "active",
            },
            headers=_auth(actor_token),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_upsert_staff_profile(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="upd_profile@admintest.com")
            session.add(u)
            await session.commit()
            uid = u.id

        r = await client.put(
            f"/admin/users/{uid}",
            json={
                "first_name": "Con",
                "last_name": "Perfil",
                "email": "upd_profile@admintest.com",
                "status": "active",
                "work_phone": "+56911111111",
                "notes_admin": "Nota de prueba",
            },
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["staff_profile"]["work_phone"] == "+56911111111"
        assert body["staff_profile"]["notes_admin"] == "Nota de prueba"

    @pytest.mark.asyncio
    async def test_sync_roles(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        from app.models.role import Role

        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="upd_roles@admintest.com")
            r1 = Role(name="rol_a", guard_name="admin")
            r2 = Role(name="rol_b", guard_name="admin")
            session.add_all([u, r1, r2])
            await session.commit()
            uid = u.id

        # Asignar rol_a
        r = await client.put(
            f"/admin/users/{uid}",
            json={
                "first_name": "Sync",
                "last_name": "Roles",
                "email": "upd_roles@admintest.com",
                "status": "active",
                "roles": ["rol_a"],
            },
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "rol_a" in r.json()["roles"]
        assert "rol_b" not in r.json()["roles"]

        # Cambiar a rol_b → rol_a debe removerse
        r2_resp = await client.put(
            f"/admin/users/{uid}",
            json={
                "first_name": "Sync",
                "last_name": "Roles",
                "email": "upd_roles@admintest.com",
                "status": "active",
                "roles": ["rol_b"],
            },
            headers=_auth(actor_token),
        )
        assert "rol_b" in r2_resp.json()["roles"]
        assert "rol_a" not in r2_resp.json()["roles"]


# ─────────────────────────── DELETE /admin/users/{id} ────────────────────────


class TestDeleteUser:
    @pytest.mark.asyncio
    async def test_soft_delete_retorna_204(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="del_ok@admintest.com")
            session.add(u)
            await session.commit()
            uid = u.id

        r = await client.delete(f"/admin/users/{uid}", headers=_auth(actor_token))
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_usuario_eliminado_no_aparece_en_lista(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="del_list@admintest.com")
            session.add(u)
            await session.commit()
            uid = u.id

        await client.delete(f"/admin/users/{uid}", headers=_auth(actor_token))

        r = await client.get("/admin/users", headers=_auth(actor_token))
        emails = [x["email"] for x in r.json()["data"]]
        assert "del_list@admintest.com" not in emails

    @pytest.mark.asyncio
    async def test_delete_no_encontrado_retorna_404(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.delete("/admin/users/999999", headers=_auth(actor_token))
        assert r.status_code == 404


# ─────────────────────────── POST /admin/users/{id}/restore ──────────────────


class TestRestoreUser:
    @pytest.mark.asyncio
    async def test_restore_usuario_eliminado(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="restore_ok@admintest.com")
            session.add(u)
            await session.commit()
            uid = u.id

        # Eliminar
        await client.delete(f"/admin/users/{uid}", headers=_auth(actor_token))

        # Restaurar
        r = await client.post(f"/admin/users/{uid}/restore", headers=_auth(actor_token))
        assert r.status_code == 200
        assert r.json()["deleted_at"] is None

        # Debe aparecer en la lista de nuevo
        lista = await client.get("/admin/users", headers=_auth(actor_token))
        emails = [x["email"] for x in lista.json()["data"]]
        assert "restore_ok@admintest.com" in emails

    @pytest.mark.asyncio
    async def test_restore_usuario_no_eliminado_retorna_404(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="restore_nodeli@admintest.com")
            session.add(u)
            await session.commit()
            uid = u.id

        r = await client.post(f"/admin/users/{uid}/restore", headers=_auth(actor_token))
        assert r.status_code == 404


# ─────────────────────────── PUT /admin/users/{id}/status ────────────────────


class TestUpdateStatus:
    @pytest.mark.asyncio
    async def test_cambiar_status(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="status_ok@admintest.com", status="active")
            session.add(u)
            await session.commit()
            uid = u.id

        r = await client.put(
            f"/admin/users/{uid}/status",
            json={"status": "suspended"},
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "suspended"

    @pytest.mark.asyncio
    async def test_status_invalido_retorna_422(
        self, client: AsyncClient, actor_token: str, async_engine
    ):
        Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            u = _make_user(email="status_bad@admintest.com")
            session.add(u)
            await session.commit()
            uid = u.id

        r = await client.put(
            f"/admin/users/{uid}/status",
            json={"status": "invalido"},
            headers=_auth(actor_token),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_status_no_encontrado_retorna_404(
        self, client: AsyncClient, actor_token: str
    ):
        r = await client.put(
            "/admin/users/999999/status",
            json={"status": "active"},
            headers=_auth(actor_token),
        )
        assert r.status_code == 404
