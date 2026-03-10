"""
Tests de Step 3 — Auth (TokenService, AuthService, endpoints JWT).

Estrategia:
- TestTokenService: funciones puras, sin DB.
- TestAuthService: servicio con SQLite en memoria.
- TestLoginEndpoints / TestPasswordEndpoints: endpoints vía httpx + SQLite.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt_lib
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import JWTError, jwt as jose_jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # asegura que Base.metadata tenga todos los modelos
from app.database import get_db
from app.main import app
from app.models import Base, User
from app.services.auth_service import AuthService
from app.services.token_service import ALGORITHM, create_access_token, decode_token
from app.config import settings


def _hash(plain: str) -> str:
    """Hash bcrypt para fixtures de test."""
    return _bcrypt_lib.hashpw(plain.encode(), _bcrypt_lib.gensalt()).decode()


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
    """Cliente HTTP con override de DB a SQLite en memoria."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


# ─────────────────────────── Helper ─────────────────────────────────────────


def _make_user(**kwargs) -> User:
    defaults = {
        "realm": "admin",
        "email": "default@test.com",
        "password": _hash("TestPass123!"),
        "first_name": "Test",
        "last_name": "User",
        "status": "active",
        "force_password_change": False,
    }
    defaults.update(kwargs)
    return User(**defaults)


# ─────────────────────────── TokenService ────────────────────────────────────


class TestTokenService:
    def test_token_tiene_claims_correctos(self):
        token = create_access_token(user_id=42, realm="admin", force_password_change=True)
        payload = jose_jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        assert payload["sub"] == "42"
        assert payload["realm"] == "admin"
        assert payload["force_password_change"] is True

    def test_decode_roundtrip(self):
        token = create_access_token(user_id=7, realm="customer")
        payload = decode_token(token)
        assert payload["sub"] == "7"
        assert payload["realm"] == "customer"
        assert payload["force_password_change"] is False

    def test_decode_token_invalido_lanza_error(self):
        with pytest.raises(JWTError):
            decode_token("no.es.un.token.valido")

    def test_decode_token_expirado_lanza_error(self):
        payload = {
            "sub": "1",
            "realm": "admin",
            "force_password_change": False,
            "exp": datetime.now(timezone.utc) - timedelta(seconds=10),
        }
        token = jose_jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
        with pytest.raises(JWTError):
            decode_token(token)

    def test_force_password_change_default_false(self):
        token = create_access_token(user_id=1, realm="admin")
        payload = decode_token(token)
        assert payload["force_password_change"] is False


# ─────────────────────────── AuthService ─────────────────────────────────────


class TestAuthService:
    def test_hash_y_verify_password(self):
        h = AuthService.hash_password("miPassword1!")
        assert h != "miPassword1!"
        assert AuthService.verify_password("miPassword1!", h) is True
        assert AuthService.verify_password("otro", h) is False

    def test_hash_distinto_cada_vez(self):
        h1 = AuthService.hash_password("igual")
        h2 = AuthService.hash_password("igual")
        assert h1 != h2  # bcrypt tiene salt aleatorio

    @pytest.mark.asyncio
    async def test_attempt_exitoso(self, db_session: AsyncSession):
        user = _make_user(email="attempt_ok@test.com", realm="admin")
        db_session.add(user)
        await db_session.flush()

        svc = AuthService(db_session)
        result = await svc.attempt("attempt_ok@test.com", "TestPass123!", "admin")
        assert result.id == user.id
        assert result.last_login_at is not None

    @pytest.mark.asyncio
    async def test_attempt_password_incorrecto(self, db_session: AsyncSession):
        user = _make_user(email="attempt_wrong@test.com", realm="admin")
        db_session.add(user)
        await db_session.flush()

        svc = AuthService(db_session)
        with pytest.raises(ValueError, match="Credenciales"):
            await svc.attempt("attempt_wrong@test.com", "Incorrecto1!", "admin")

    @pytest.mark.asyncio
    async def test_attempt_usuario_inactivo(self, db_session: AsyncSession):
        user = _make_user(email="attempt_inactive@test.com", realm="admin", status="suspended")
        db_session.add(user)
        await db_session.flush()

        svc = AuthService(db_session)
        with pytest.raises(ValueError, match="Credenciales"):
            await svc.attempt("attempt_inactive@test.com", "TestPass123!", "admin")

    @pytest.mark.asyncio
    async def test_attempt_realm_equivocado(self, db_session: AsyncSession):
        user = _make_user(email="attempt_realm@test.com", realm="admin")
        db_session.add(user)
        await db_session.flush()

        svc = AuthService(db_session)
        with pytest.raises(ValueError, match="Credenciales"):
            await svc.attempt("attempt_realm@test.com", "TestPass123!", "customer")

    @pytest.mark.asyncio
    async def test_attempt_normaliza_email(self, db_session: AsyncSession):
        user = _make_user(email="upper@test.com", realm="admin")
        db_session.add(user)
        await db_session.flush()

        svc = AuthService(db_session)
        result = await svc.attempt("UPPER@TEST.COM", "TestPass123!", "admin")
        assert result.id == user.id


# ─────────────────────────── Login endpoints ─────────────────────────────────


class TestLoginEndpoints:
    @pytest.mark.asyncio
    async def test_admin_login_exitoso(self, client: AsyncClient, db_session: AsyncSession):
        user = _make_user(email="login_admin@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        r = await client.post(
            "/admin/login",
            json={"email": "login_admin@test.com", "password": "TestPass123!"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["force_password_change"] is False

    @pytest.mark.asyncio
    async def test_admin_login_password_incorrecto(self, client: AsyncClient, db_session: AsyncSession):
        user = _make_user(email="login_wrongpwd@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        r = await client.post(
            "/admin/login",
            json={"email": "login_wrongpwd@test.com", "password": "Incorrecto1!"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_customer_login_exitoso(self, client: AsyncClient, db_session: AsyncSession):
        user = _make_user(email="login_cust@test.com", realm="customer")
        db_session.add(user)
        await db_session.commit()

        r = await client.post(
            "/customer/login",
            json={"email": "login_cust@test.com", "password": "TestPass123!"},
        )
        assert r.status_code == 200
        assert "access_token" in r.json()

    @pytest.mark.asyncio
    async def test_login_realm_cruzado_falla(self, client: AsyncClient, db_session: AsyncSession):
        """Usuario admin no puede autenticarse en /customer/login."""
        user = _make_user(email="login_cross@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        r = await client.post(
            "/customer/login",
            json={"email": "login_cross@test.com", "password": "TestPass123!"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_logout_exitoso(self, client: AsyncClient, db_session: AsyncSession):
        user = _make_user(email="logout_admin@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, "admin")
        r = await client.post(
            "/admin/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_logout_sin_token_retorna_401(self, client: AsyncClient):
        r = await client.post("/admin/logout")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_login_force_password_change_en_token(self, client: AsyncClient, db_session: AsyncSession):
        user = _make_user(
            email="login_fpc@test.com",
            realm="admin",
            force_password_change=True,
        )
        db_session.add(user)
        await db_session.commit()

        r = await client.post(
            "/admin/login",
            json={"email": "login_fpc@test.com", "password": "TestPass123!"},
        )
        assert r.status_code == 200
        assert r.json()["force_password_change"] is True


# ─────────────────────────── Password endpoints ───────────────────────────────


class TestPasswordEndpoints:
    @pytest.mark.asyncio
    async def test_policy_es_publico(self, client: AsyncClient):
        r = await client.get("/password/policy")
        assert r.status_code == 200
        data = r.json()
        assert "min" in data
        assert "require" in data
        assert "messages" in data

    @pytest.mark.asyncio
    async def test_check_password_valida(self, client: AsyncClient):
        r = await client.post("/password/check", json={"password": "ValidPass123!"})
        assert r.status_code == 200
        assert r.json()["valid"] is True
        assert r.json()["errors"] == []

    @pytest.mark.asyncio
    async def test_check_password_muy_corta(self, client: AsyncClient):
        r = await client.post("/password/check", json={"password": "Abc1!"})
        assert r.status_code == 200
        assert r.json()["valid"] is False
        assert len(r.json()["errors"]) > 0

    @pytest.mark.asyncio
    async def test_check_sin_mayuscula(self, client: AsyncClient):
        r = await client.post("/password/check", json={"password": "lowercase123!"})
        assert r.status_code == 200
        assert r.json()["valid"] is False

    @pytest.mark.asyncio
    async def test_cambio_password_exitoso(self, client: AsyncClient, db_session: AsyncSession):
        user = _make_user(email="chpwd_ok@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, "admin")
        r = await client.post(
            "/admin/password/change",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "TestPass123!",
                "password": "NewPass456@",
                "password_confirmation": "NewPass456@",
            },
        )
        assert r.status_code == 200
        assert "Contraseña" in r.json()["status"]

    @pytest.mark.asyncio
    async def test_cambio_password_actual_incorrecto(self, client: AsyncClient, db_session: AsyncSession):
        user = _make_user(email="chpwd_wrong@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, "admin")
        r = await client.post(
            "/admin/password/change",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "PasswordIncorrecto1!",
                "password": "NewPass456@",
                "password_confirmation": "NewPass456@",
            },
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_cambio_password_no_coinciden(self, client: AsyncClient, db_session: AsyncSession):
        """password != password_confirmation debe fallar en validación de request."""
        user = _make_user(email="chpwd_mismatch@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, "admin")
        r = await client.post(
            "/admin/password/change",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "TestPass123!",
                "password": "NewPass456@",
                "password_confirmation": "Diferente789#",
            },
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_cambio_password_sin_autenticar(self, client: AsyncClient):
        r = await client.post(
            "/admin/password/change",
            json={
                "current_password": "TestPass123!",
                "password": "NewPass456@",
                "password_confirmation": "NewPass456@",
            },
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_forzar_password_exitoso(self, client: AsyncClient, db_session: AsyncSession):
        user = _make_user(
            email="forcepwd_ok@test.com",
            realm="admin",
            force_password_change=True,
        )
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, "admin", force_password_change=True)
        r = await client.post(
            "/admin/password/force",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "TestPass123!",
                "password": "ForcedPass789@",
                "password_confirmation": "ForcedPass789@",
            },
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_customer_cambio_password(self, client: AsyncClient, db_session: AsyncSession):
        user = _make_user(email="cust_chpwd@test.com", realm="customer")
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, "customer")
        r = await client.post(
            "/customer/password/change",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "TestPass123!",
                "password": "CustNew456@",
                "password_confirmation": "CustNew456@",
            },
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_token_realm_cruzado_retorna_403(self, client: AsyncClient, db_session: AsyncSession):
        """Token de admin no puede acceder a endpoints de customer y viceversa."""
        admin = _make_user(email="cross_admin@test.com", realm="admin")
        customer = _make_user(email="cross_cust@test.com", realm="customer")
        db_session.add(admin)
        db_session.add(customer)
        await db_session.commit()

        admin_token = create_access_token(admin.id, "admin")
        cust_token = create_access_token(customer.id, "customer")

        # Token admin → endpoint customer: 403
        r = await client.post(
            "/customer/password/change",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "current_password": "TestPass123!",
                "password": "NewPass456@",
                "password_confirmation": "NewPass456@",
            },
        )
        assert r.status_code == 403

        # Token customer → endpoint admin: 403
        r = await client.post(
            "/admin/password/change",
            headers={"Authorization": f"Bearer {cust_token}"},
            json={
                "current_password": "TestPass123!",
                "password": "NewPass456@",
                "password_confirmation": "NewPass456@",
            },
        )
        assert r.status_code == 403


# ─────────────────────────── Historial de passwords ──────────────────────────


class TestPasswordHistory:
    @pytest.mark.asyncio
    async def test_no_puede_reutilizar_password_actual(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Cambiar contraseña a la misma actual debe rechazarse (historial)."""
        user = _make_user(email="hist_current@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, "admin")
        r = await client.post(
            "/admin/password/change",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "TestPass123!",
                "password": "TestPass123!",   # misma contraseña
                "password_confirmation": "TestPass123!",
            },
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_no_puede_reutilizar_password_reciente(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Contraseña usada antes (guardada en historial) debe rechazarse."""
        user = _make_user(email="hist_reuse@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, "admin")

        # Primer cambio: TestPass123! → NewPass456@
        r = await client.post(
            "/admin/password/change",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "TestPass123!",
                "password": "NewPass456@",
                "password_confirmation": "NewPass456@",
            },
        )
        assert r.status_code == 200

        # Segundo cambio: NewPass456@ → TestPass123! (contraseña anterior)
        r = await client.post(
            "/admin/password/change",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "NewPass456@",
                "password": "TestPass123!",   # fue usada antes → rechazar
                "password_confirmation": "TestPass123!",
            },
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_puede_usar_password_nueva(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Contraseña completamente nueva debe aceptarse."""
        user = _make_user(email="hist_new@test.com", realm="admin")
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, "admin")
        r = await client.post(
            "/admin/password/change",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "TestPass123!",
                "password": "BrandNew789#",
                "password_confirmation": "BrandNew789#",
            },
        )
        assert r.status_code == 200
