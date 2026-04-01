from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_service import AuditService
from app.core.idempotency import check_idempotency
from app.core.state_manager import StateManager
from app.core.workflow_engine import WorkflowEngine
from app.database import get_session
from app.models.request_model import WorkflowRequest
from app.schemas.request_schema import SubmitWorkflowRequest, WorkflowStatusResponse
from app.utils.exceptions import InvalidPayloadError, WorkflowNotFoundError
from config.loader import get_workflow


router = APIRouter(prefix="/workflow", tags=["workflow"])


def _coerce_type(value: Any, expected: str) -> bool:
	if expected == "str":
		return isinstance(value, str)
	if expected == "int":
		return isinstance(value, int) and not isinstance(value, bool)
	if expected == "float":
		return isinstance(value, (int, float)) and not isinstance(value, bool)
	if expected == "bool":
		return isinstance(value, bool)
	if expected == "dict":
		return isinstance(value, dict)
	if expected == "list":
		return isinstance(value, list)
	return value is not None


def _validate_payload(payload: Dict[str, Any], input_schema: Dict[str, str]) -> None:
	for field, expected_type in input_schema.items():
		if field not in payload:
			raise InvalidPayloadError(f"Missing required field '{field}'")
		if not _coerce_type(payload[field], expected_type):
			raise InvalidPayloadError(
				f"Invalid type for field '{field}': expected {expected_type}, got {type(payload[field]).__name__}"
			)


async def _build_status_response(
	session: AsyncSession,
	request: WorkflowRequest,
) -> WorkflowStatusResponse:
	audit_service = AuditService()
	state_manager = StateManager()
	audit_logs = await audit_service.get_full_audit(session, request.id)
	history = await state_manager.get_history(session, request.id)
	explanation = audit_service.build_decision_explanation(request, audit_logs, history)
	return WorkflowStatusResponse(
		request_id=request.id,
		idempotency_key=request.idempotency_key,
		workflow_id=request.workflow_id,
		status=request.status,
		current_stage=request.current_stage,
		retry_count=request.retry_count,
		created_at=request.created_at,
		updated_at=request.updated_at,
		decision_explanation=explanation,
	)


@router.post("/submit", response_model=WorkflowStatusResponse)
async def submit_workflow(
	body: SubmitWorkflowRequest,
	response: Response,
	session: AsyncSession = Depends(get_session),
) -> WorkflowStatusResponse:
	try:
		workflow = get_workflow(body.workflow_id)
	except WorkflowNotFoundError as exc:
		raise HTTPException(status_code=404, detail=str(exc)) from exc

	_validate_payload(body.payload, workflow.input_schema)

	existing = await check_idempotency(session, body.idempotency_key, body.workflow_id)
	if existing:
		response.headers["X-Idempotent-Replay"] = "true"
		return await _build_status_response(session, existing)

	request = WorkflowRequest(
		idempotency_key=body.idempotency_key,
		workflow_id=body.workflow_id,
		status="PENDING",
		current_stage=workflow.entry_stage,
		payload=json.dumps(body.payload, default=str),
		retry_count=0,
		workflow_version=workflow.version,
	)
	session.add(request)

	try:
		await session.commit()
	except IntegrityError as exc:
		await session.rollback()
		raise HTTPException(status_code=409, detail="Duplicate idempotency key") from exc

	engine = WorkflowEngine()
	execution = await engine.execute_workflow(request.id, workflow, body.payload, session)
	return await _build_status_response(session, execution.request)


@router.get("/{request_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(
	request_id: str,
	session: AsyncSession = Depends(get_session),
) -> WorkflowStatusResponse:
	stmt = select(WorkflowRequest).where(WorkflowRequest.id == request_id)
	result = await session.execute(stmt)
	request = result.scalar_one_or_none()
	if request is None:
		raise HTTPException(status_code=404, detail="Request not found")
	return await _build_status_response(session, request)


@router.get("/{request_id}/history")
async def get_workflow_history(
	request_id: str,
	session: AsyncSession = Depends(get_session),
) -> list[dict[str, Optional[str]]]:
	stmt = select(WorkflowRequest.id).where(WorkflowRequest.id == request_id)
	req = await session.execute(stmt)
	if req.scalar_one_or_none() is None:
		raise HTTPException(status_code=404, detail="Request not found")

	manager = StateManager()
	entries = await manager.get_history(session, request_id)
	return [
		{
			"from_status": e.from_status,
			"to_status": e.to_status,
			"reason": e.transition_reason,
			"triggered_by": e.triggered_by,
			"timestamp": e.timestamp.isoformat(),
		}
		for e in entries
	]


@router.post("/{request_id}/retry", response_model=WorkflowStatusResponse)
async def retry_workflow(
	request_id: str,
	session: AsyncSession = Depends(get_session),
) -> WorkflowStatusResponse:
	stmt = select(WorkflowRequest).where(WorkflowRequest.id == request_id)
	result = await session.execute(stmt)
	request = result.scalar_one_or_none()
	if request is None:
		raise HTTPException(status_code=404, detail="Request not found")

	if request.status in {"APPROVED", "REJECTED"}:
		raise HTTPException(status_code=400, detail="Cannot retry terminal request")
	if request.status not in {"FAILED", "MANUAL_REVIEW", "RETRY"}:
		raise HTTPException(status_code=400, detail="Retry allowed only for FAILED or MANUAL_REVIEW")

	workflow = get_workflow(request.workflow_id)
	payload = json.loads(request.payload)

	if request.status == "MANUAL_REVIEW":
		request.status = "IN_PROGRESS"
	elif request.status == "FAILED":
		request.status = "RETRY"

	await session.commit()

	engine = WorkflowEngine()
	execution = await engine.execute_workflow(request.id, workflow, payload, session)
	return await _build_status_response(session, execution.request)
