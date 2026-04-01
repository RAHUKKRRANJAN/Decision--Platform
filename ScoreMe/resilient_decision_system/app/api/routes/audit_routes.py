from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_service import AuditService
from app.core.state_manager import StateManager
from app.database import get_session
from app.models.request_model import WorkflowRequest
from app.schemas.audit_schema import AuditEntry, AuditResponse


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/{request_id}", response_model=AuditResponse)
async def get_audit(
	request_id: str,
	session: AsyncSession = Depends(get_session),
) -> AuditResponse:
	stmt = select(WorkflowRequest).where(WorkflowRequest.id == request_id)
	result = await session.execute(stmt)
	request = result.scalar_one_or_none()
	if request is None:
		raise HTTPException(status_code=404, detail="Request not found")

	service = AuditService()
	logs = await service.get_full_audit(session, request_id)
	trail = [
		AuditEntry(
			stage_id=log.stage_id,
			rule_id=log.rule_id,
			rule_description=log.rule_description,
			field_evaluated=log.field_evaluated,
			field_value=json.loads(log.field_value),
			operator=log.operator,
			expected_value=json.loads(log.expected_value),
			result=log.result,
			action_taken=log.action_taken,
			timestamp=log.timestamp,
			error_message=log.error_message,
		)
		for log in logs
	]

	return AuditResponse(request_id=request_id, total_events=len(trail), audit_trail=trail)


@router.get("/{request_id}/explanation")
async def get_explanation(
	request_id: str,
	session: AsyncSession = Depends(get_session),
):
	stmt = select(WorkflowRequest).where(WorkflowRequest.id == request_id)
	result = await session.execute(stmt)
	request = result.scalar_one_or_none()
	if request is None:
		raise HTTPException(status_code=404, detail="Request not found")

	service = AuditService()
	manager = StateManager()
	logs = await service.get_full_audit(session, request_id)
	history = await manager.get_history(session, request_id)
	return service.build_decision_explanation(request, logs, history)
