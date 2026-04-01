from __future__ import annotations

import pytest

from app.core.external_dependency import ExternalCheckResult, ExternalDependencyService


pytestmark = pytest.mark.asyncio


async def _always_success(*_args, **_kwargs):
	return ExternalCheckResult(success=True, score=0.91, message="ok", latency_ms=5)


async def test_claim_document_retry_until_failed(client, sample_claim_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_document_verifier", _always_success)
	payload = dict(sample_claim_payload)
	payload["document_count"] = 0

	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "claim_processing", "idempotency_key": "retry-1", "payload": payload},
	)
	assert response.status_code == 200
	body = response.json()
	assert body["status"] == "FAILED"
	assert body["retry_count"] == 3

	history = await client.get(f"/api/v1/workflow/{body['request_id']}/history")
	retry_transitions = [h for h in history.json() if h["to_status"] == "RETRY"]
	assert len(retry_transitions) >= 1


async def test_manual_retry_for_failed_request(client, sample_claim_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_document_verifier", _always_success)
	payload = dict(sample_claim_payload)
	payload["document_count"] = 0

	create = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "claim_processing", "idempotency_key": "retry-2", "payload": payload},
	)
	request_id = create.json()["request_id"]

	retry_resp = await client.post(f"/api/v1/workflow/{request_id}/retry")
	assert retry_resp.status_code == 200
	assert retry_resp.json()["retry_count"] >= 3


async def test_retry_on_approved_request_returns_400(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	create = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "retry-3", "payload": sample_application_payload},
	)
	request_id = create.json()["request_id"]
	assert create.json()["status"] == "APPROVED"

	retry_resp = await client.post(f"/api/v1/workflow/{request_id}/retry")
	assert retry_resp.status_code == 400
