from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.main import app
from config.loader import load_all_workflows


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
	TEST_DATABASE_URL,
	connect_args={"check_same_thread": False},
	poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def reset_db() -> AsyncGenerator[None, None]:
	async with test_engine.begin() as conn:
		await conn.run_sync(Base.metadata.drop_all)
		await conn.run_sync(Base.metadata.create_all)
	yield


@pytest_asyncio.fixture(autouse=True)
async def setup_configs() -> AsyncGenerator[None, None]:
	load_all_workflows("config/workflows")
	yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
	async with TestSessionLocal() as session:
		yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
	async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
		yield db_session

	app.dependency_overrides[get_session] = override_get_session
	transport = ASGITransport(app=app, raise_app_exceptions=False)
	async with AsyncClient(transport=transport, base_url="http://test") as ac:
		yield ac
	app.dependency_overrides.clear()


@pytest.fixture
def sample_application_payload() -> dict:
	return {
		"applicant_id": "app-1001",
		"applicant_age": 30,
		"credit_score": 720,
		"requested_amount": 150000.0,
		"income": 85000.0,
		"employment_status": "employed",
		"debt_to_income_ratio": 0.31,
	}


@pytest.fixture
def sample_claim_payload() -> dict:
	return {
		"claim_id": "clm-1001",
		"policy_active": True,
		"claim_amount": 250000.0,
		"days_since_incident": 10,
		"document_count": 3,
		"claimant_id": "cust-42",
	}


@pytest.fixture
def sample_employee_payload() -> dict:
	return {
		"employee_id": "emp-1001",
		"employee_email": "dev@example.com",
		"department": "engineering",
		"start_date": "2026-04-10",
		"salary": 90000.0,
	}
