"""
Tests de Step 16 — Capitados Lotes (Batches + Monthly Reports).

Estrategia:
- SQLite en memoria (módulo-scoped).
- Seed: empresa + producto + persona + contrato + batch + items + monthly records.
- Endpoints: batches index/show/items/monthly-records, rollback, report months.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime

import bcrypt as _bcrypt_lib
import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models
from app.database import get_db
from app.main import app
from app.models import Base, Permission, User
from app.models.capitated_batch_item_log import CapitatedBatchItemLog
from app.models.capitated_batch_log import CapitatedBatchLog
from app.models.capitated_contract import CapitatedContract
from app.models.capitated_monthly_record import CapitatedMonthlyRecord
from app.models.capitated_product_insured import CapitatedProductInsured
from app.models.company import Company
from app.models.plan_version import PlanVersion
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
            realm="admin", email="batch_actor@test.com",
            password=_hashed("Pass1!"), first_name="Batch", last_name="Actor",
            status="active", force_password_change=False,
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
    """Crea empresa + producto + persona + contrato + batch + item + monthly record."""
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        company = Company(name="Batch Co", short_code="BAT", status="active")
        db.add(company)
        await db.flush()

        product = Product(
            name=json.dumps({"es": "Plan Batch"}),
            product_type=Product.TYPE_PLAN_CAPITADO,
            status="active", show_in_widget=False, company_id=company.id,
        )
        db.add(product)
        await db.flush()

        pv = PlanVersion(
            product_id=product.id, name="V1 Batch", status="active",
        )
        db.add(pv)
        await db.flush()

        person = CapitatedProductInsured(
            company_id=company.id, product_id=product.id,
            document_number="BATCH001", full_name="Batch Person",
            sex="F", age_reported=30, status="active",
        )
        db.add(person)
        await db.flush()

        contract = CapitatedContract(
            company_id=company.id, product_id=product.id,
            person_id=person.id, status="active",
            entry_date=date(2025, 1, 1), entry_age=30,
        )
        db.add(contract)
        await db.flush()

        batch = CapitatedBatchLog(
            company_id=company.id,
            coverage_month=date(2025, 3, 1),
            source="excel",
            original_filename="test.xlsx",
            status=CapitatedBatchLog.STATUS_PROCESSED,
            total_rows=2, total_applied=1, total_rejected=1,
            total_duplicated=0, total_incongruences=0,
            total_plan_errors=0, total_rolled_back=0,
            processed_at=datetime.now(UTC),
        )
        db.add(batch)
        await db.flush()

        item = CapitatedBatchItemLog(
            batch_id=batch.id, sheet_name="(1) Plan Batch",
            row_number=2, product_id=product.id,
            document_number="BATCH001", full_name="Batch Person",
            sex="F", age_reported=30, result="applied",
            person_id=person.id, contract_id=contract.id,
        )
        db.add(item)
        await db.flush()

        mr = CapitatedMonthlyRecord(
            company_id=company.id, product_id=product.id,
            person_id=person.id, contract_id=contract.id,
            coverage_month=date(2025, 3, 1),
            plan_version_id=pv.id, load_batch_id=batch.id,
            full_name="Batch Person", sex="F", age_reported=30,
            price_base=100.00, price_final=110.00,
            status="active",
        )
        db.add(mr)
        await db.commit()

        await db.refresh(company)
        await db.refresh(batch)
        await db.refresh(mr)

        return {
            "company_id": company.id,
            "batch_id": batch.id,
            "monthly_record_id": mr.id,
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


# ─────────────────────── Batches ─────────────────────────────────────────────


class TestBatchIndex:
    async def test_lista_lotes(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], "/batches"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 1
        assert "meta" in r.json()

    async def test_filtra_por_status(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], "/batches?status=processed"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        for b in r.json()["data"]:
            assert b["status"] == "processed"


class TestBatchShow:
    async def test_detalle_lote(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], f"/batches/{seed_data['batch_id']}"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["id"] == seed_data["batch_id"]

    async def test_lote_no_existe_retorna_404(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], "/batches/999999"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 404


class TestBatchItems:
    async def test_lista_items(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], f"/batches/{seed_data['batch_id']}/items"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 1

    async def test_filtra_por_result(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], f"/batches/{seed_data['batch_id']}/items?result=applied"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        for item in r.json()["data"]:
            assert item["result"] == "applied"


class TestBatchMonthlyRecords:
    async def test_lista_monthly_records(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], f"/batches/{seed_data['batch_id']}/monthly-records"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) >= 1


# ─────────────────────── Rollback ────────────────────────────────────────────


class TestRollbackMonthlyRecord:
    async def test_rollback_single_record(self, client, actor_token, seed_data):
        rid = seed_data["monthly_record_id"]
        bid = seed_data["batch_id"]
        cid = seed_data["company_id"]

        r = await client.post(
            _url(cid, f"/batches/{bid}/monthly-records/{rid}/rollback"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "revertido" in r.json()["message"].lower()

    async def test_rollback_ya_revertido_retorna_422(self, client, actor_token, seed_data):
        rid = seed_data["monthly_record_id"]
        bid = seed_data["batch_id"]
        cid = seed_data["company_id"]

        r = await client.post(
            _url(cid, f"/batches/{bid}/monthly-records/{rid}/rollback"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 422


class TestRollbackBatch:
    async def test_rollback_lote(self, client, actor_token, seed_data):
        bid = seed_data["batch_id"]
        cid = seed_data["company_id"]

        r = await client.post(
            _url(cid, f"/batches/{bid}/rollback"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "revertido" in r.json()["message"].lower()

    async def test_rollback_lote_ya_revertido_retorna_422(self, client, actor_token, seed_data):
        bid = seed_data["batch_id"]
        cid = seed_data["company_id"]

        r = await client.post(
            _url(cid, f"/batches/{bid}/rollback"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 422


# ─────────────────────── Monthly Reports ─────────────────────────────────────


class TestMonthlyReports:
    async def test_months(self, client, actor_token, seed_data):
        r = await client.get(
            _url(seed_data["company_id"], "/reportes/mensuales"),
            headers=_auth(actor_token),
        )
        assert r.status_code == 200
        assert "months" in r.json()
