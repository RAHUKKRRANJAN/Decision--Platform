from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.external_dependency import ExternalCheckResult, ExternalDependencyService
from app.models.request_model import WorkflowRequest


pytestmark = pytest.mark.asyncio


async def _always_success(*_args, **_kwargs):
	return ExternalCheckResult(success=True, score=0.94, message="ok", latency_ms=10)


async def test_same_idempotency_key_twice_returns_same_response(
	client, db_session, sample_application_payload, monkeypatch
):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)

	first = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "dup-1", "payload": sample_application_payload},
	)
	second = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "dup-1", "payload": sample_application_payload},
	)

	assert first.status_code == 200
	assert second.status_code == 200
	assert first.json()["request_id"] == second.json()["request_id"]
	assert second.headers.get("X-Idempotent-Replay") == "true"

	result = await db_session.execute(
		select(WorkflowRequest).where(WorkflowRequest.idempotency_key == "dup-1")
	)
	records = result.scalars().all()
	assert len(records) == 1


async def test_same_idempotency_key_different_workflow_returns_existing(
	client, sample_application_payload, sample_claim_payload, monkeypatch
):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	monkeypatch.setattr(ExternalDependencyService, "call_document_verifier", _always_success)

	first = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "dup-2", "payload": sample_application_payload},
	)
	second = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "claim_processing", "idempotency_key": "dup-2", "payload": sample_claim_payload},
	)

	assert second.status_code == 200
	assert first.json()["request_id"] == second.json()["request_id"]
	assert second.headers.get("X-Idempotent-Replay") == "true"


async def test_different_idempotency_keys_same_payload_create_two_records(
	client, sample_application_payload, monkeypatch
):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)

	first = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "dup-3a", "payload": sample_application_payload},
	)
	second = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "dup-3b", "payload": sample_application_payload},
	)

	assert first.status_code == 200
	assert second.status_code == 200
	assert first.json()["request_id"] != second.json()["request_id"]
