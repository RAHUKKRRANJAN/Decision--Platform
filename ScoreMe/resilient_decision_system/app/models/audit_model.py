from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
	from app.models.request_model import WorkflowRequest


class AuditLog(Base):
	__tablename__ = "audit_logs"

	id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
	request_id: Mapped[str] = mapped_column(
		String(36),
		ForeignKey("workflow_requests.id", ondelete="CASCADE"),
		index=True,
		nullable=False,
	)
	stage_id: Mapped[str] = mapped_column(String(100), nullable=False)
	rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
	rule_description: Mapped[str] = mapped_column(String(500), nullable=False)
	rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
	field_evaluated: Mapped[str] = mapped_column(String(100), nullable=False)
	field_value: Mapped[str] = mapped_column(Text, nullable=False)
	operator: Mapped[str] = mapped_column(String(30), nullable=False)
	expected_value: Mapped[str] = mapped_column(Text, nullable=False)
	result: Mapped[str] = mapped_column(String(10), nullable=False)
	action_taken: Mapped[str] = mapped_column(String(30), nullable=False)
	timestamp: Mapped[datetime] = mapped_column(
		DateTime,
		default=lambda: datetime.now(timezone.utc),
		nullable=False,
	)
	error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

	request: Mapped["WorkflowRequest"] = relationship(back_populates="audit_logs")
