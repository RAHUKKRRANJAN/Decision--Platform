from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request_model import WorkflowRequest
from app.models.state_model import StateHistory
from app.utils.exceptions import InvalidStateTransitionError
from app.utils.logger import get_logger, log_state_transition


class StateManager:
	VALID_TRANSITIONS = {
		"PENDING": {"IN_PROGRESS"},
		"IN_PROGRESS": {"APPROVED", "REJECTED", "MANUAL_REVIEW", "RETRY", "FAILED"},
		"RETRY": {"IN_PROGRESS", "FAILED"},
		"APPROVED": set(),
		"REJECTED": set(),
		"MANUAL_REVIEW": set(),
		"FAILED": set(),
	}

	def __init__(self) -> None:
		self.logger = get_logger(__name__)

	async def transition(
		self,
		session: AsyncSession,
		request: WorkflowRequest,
		to_status: str,
		to_stage: Optional[str],
		reason: str,
		triggered_by: str,
		metadata: Optional[dict],
	) -> None:
		from_status = request.status
		from_stage = request.current_stage

		allowed = self.VALID_TRANSITIONS.get(from_status, set())
		if to_status not in allowed:
			raise InvalidStateTransitionError(
				f"Illegal transition {from_status} -> {to_status} for request {request.id}"
			)

		history = StateHistory(
			request_id=request.id,
			from_status=from_status,
			to_status=to_status,
			from_stage=from_stage,
			to_stage=to_stage,
			transition_reason=reason,
			triggered_by=triggered_by,
			timestamp=datetime.now(timezone.utc),
			metadata_json=json.dumps(metadata) if metadata is not None else None,
		)
		session.add(history)

		request.status = to_status
		request.current_stage = to_stage or request.current_stage
		request.updated_at = datetime.now(timezone.utc)
		await session.flush()

		log_state_transition(self.logger, request.id, from_status, to_status, reason)

	async def get_history(self, session: AsyncSession, request_id: str) -> list[StateHistory]:
		stmt = (
			select(StateHistory)
			.where(StateHistory.request_id == request_id)
			.order_by(StateHistory.timestamp.asc())
		)
		result = await session.execute(stmt)
		return list(result.scalars().all())

	async def get_current_status(self, session: AsyncSession, request_id: str) -> str:
		stmt = select(WorkflowRequest.status).where(WorkflowRequest.id == request_id)
		result = await session.execute(stmt)
		status = result.scalar_one_or_none()
		if status is None:
			raise InvalidStateTransitionError(f"Request not found: {request_id}")
		return status
