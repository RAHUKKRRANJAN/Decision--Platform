from __future__ import annotations

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
	AsyncEngine,
	AsyncSession,
	async_sessionmaker,
	create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./decision_system.db")


class Base(DeclarativeBase):
	pass


engine: AsyncEngine = create_async_engine(DATABASE_URL, future=True, echo=False)
AsyncSessionLocal = async_sessionmaker(
	bind=engine,
	class_=AsyncSession,
	expire_on_commit=False,
	autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
	async with AsyncSessionLocal() as session:
		yield session


async def init_db() -> None:
	from app.models import audit_model, request_model, state_model  # noqa: F401

	async with engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)
