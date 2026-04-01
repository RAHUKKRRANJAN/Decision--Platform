from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
	from app.models.request_model import WorkflowRequest


class StateHistory(Base):
	__tablename__ = "state_history"

	id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
	request_id: Mapped[str] = mapped_column(
		String(36),
		ForeignKey("workflow_requests.id", ondelete="CASCADE"),
		index=True,
		nullable=False,
	)
	from_status: Mapped[str] = mapped_column(String(30), nullable=False)
	to_status: Mapped[str] = mapped_column(String(30), nullable=False)
	from_stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
	to_stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
	transition_reason: Mapped[str] = mapped_column(String(500), nullable=False)
	triggered_by: Mapped[str] = mapped_column(String(50), nullable=False)
	timestamp: Mapped[datetime] = mapped_column(
		DateTime,
		default=lambda: datetime.now(timezone.utc),
		nullable=False,
	)
	metadata_json: Mapped[Optional[str]] = mapped_column("metadata", Text, nullable=True)

	request: Mapped["WorkflowRequest"] = relationship(back_populates="state_history")
