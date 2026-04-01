from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request_model import WorkflowRequest


TERMINAL_STATUSES = {"APPROVED", "REJECTED", "MANUAL_REVIEW", "FAILED"}
ACTIVE_STATUSES = {"IN_PROGRESS", "PENDING", "RETRY"}


async def check_idempotency(
	session: AsyncSession,
	idempotency_key: str,
	workflow_id: str,
) -> Optional[WorkflowRequest]:
	"""
	Check if a request with this idempotency_key already exists.
	- If exists AND status is terminal (APPROVED/REJECTED/MANUAL_REVIEW):
		return existing record immediately (idempotent response)
	- If exists AND status is IN_PROGRESS/PENDING:
		return existing record with current status (do not re-process)
	- If not exists: return None (proceed with new request)
	"""
	stmt = select(WorkflowRequest).where(WorkflowRequest.idempotency_key == idempotency_key)
	result = await session.execute(stmt)
	existing = result.scalar_one_or_none()
	if not existing:
		return None

	if existing.status in TERMINAL_STATUSES or existing.status in ACTIVE_STATUSES:
		return existing

	return existing
