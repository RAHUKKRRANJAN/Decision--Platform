from __future__ import annotations

import pytest

from app.core.external_dependency import ExternalCheckResult, ExternalDependencyService


pytestmark = pytest.mark.asyncio


async def _always_success(*_args, **_kwargs):
	return ExternalCheckResult(success=True, score=0.95, message="ok", latency_ms=5)


async def test_missing_required_field(client, sample_application_payload):
	payload = dict(sample_application_payload)
	payload.pop("applicant_age")
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "invalid-1", "payload": payload},
	)
	assert response.status_code == 400
	assert "Missing required field" in response.json()["detail"]


async def test_invalid_workflow_id(client, sample_application_payload):
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "unknown_workflow", "idempotency_key": "invalid-2", "payload": sample_application_payload},
	)
	assert response.status_code == 404


async def test_wrong_type_for_credit_score(client, sample_application_payload):
	payload = dict(sample_application_payload)
	payload["credit_score"] = "bad"
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "invalid-3", "payload": payload},
	)
	assert response.status_code == 400
	assert "Invalid type" in response.json()["detail"]


async def test_empty_payload(client):
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "invalid-4", "payload": {}},
	)
	assert response.status_code == 400


async def test_age_below_18_rejected(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	payload = dict(sample_application_payload)
	payload["applicant_age"] = 17
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "invalid-5", "payload": payload},
	)
	assert response.status_code == 200
	assert response.json()["status"] == "REJECTED"

	request_id = response.json()["request_id"]
	audit = await client.get(f"/api/v1/audit/{request_id}")
	failed = [entry for entry in audit.json()["audit_trail"] if entry["rule_id"] == "rule_age_check"]
	assert failed
	assert failed[0]["result"] == "FAIL"


async def test_credit_score_below_threshold_manual_review(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	payload = dict(sample_application_payload)
	payload["credit_score"] = 620
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "invalid-6", "payload": payload},
	)
	assert response.status_code == 200
	assert response.json()["status"] == "MANUAL_REVIEW"
