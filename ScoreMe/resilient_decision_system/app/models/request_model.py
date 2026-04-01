from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
	from app.models.audit_model import AuditLog
	from app.models.state_model import StateHistory


class WorkflowRequest(Base):
	__tablename__ = "workflow_requests"

	id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
	idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
	workflow_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
	status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
	current_stage: Mapped[str] = mapped_column(String(100), default="", nullable=False)
	payload: Mapped[str] = mapped_column(Text, nullable=False)
	created_at: Mapped[datetime] = mapped_column(
		DateTime,
		default=lambda: datetime.now(timezone.utc),
		nullable=False,
	)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime,
		default=lambda: datetime.now(timezone.utc),
		onupdate=lambda: datetime.now(timezone.utc),
		nullable=False,
	)
	retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	workflow_version: Mapped[str] = mapped_column(String(50), nullable=False)

	audit_logs: Mapped[list["AuditLog"]] = relationship(
		back_populates="request",
		cascade="all, delete-orphan",
		passive_deletes=True,
	)
	state_history: Mapped[list["StateHistory"]] = relationship(
		back_populates="request",
		cascade="all, delete-orphan",
		passive_deletes=True,
	)
