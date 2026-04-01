from __future__ import annotations

import pytest

from app.core.external_dependency import ExternalCheckResult, ExternalDependencyService


pytestmark = pytest.mark.asyncio


async def _always_success(*_args, **_kwargs):
	return ExternalCheckResult(success=True, score=0.95, message="ok", latency_ms=10)


async def test_submit_valid_application_approval(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	response = await client.post(
		"/api/v1/workflow/submit",
		json={
			"workflow_id": "application_approval",
			"idempotency_key": "happy-app-1",
			"payload": sample_application_payload,
		},
	)
	assert response.status_code == 200
	body = response.json()
	assert body["status"] in ["APPROVED", "MANUAL_REVIEW"]
	assert body["decision_explanation"] is not None
	assert body["decision_explanation"]["rules_triggered"]
	assert body["decision_explanation"]["summary"]


async def test_submit_valid_claim_processing(client, sample_claim_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_document_verifier", _always_success)
	response = await client.post(
		"/api/v1/workflow/submit",
		json={
			"workflow_id": "claim_processing",
			"idempotency_key": "happy-claim-1",
			"payload": sample_claim_payload,
		},
	)
	assert response.status_code == 200
	body = response.json()
	assert body["status"] in ["APPROVED", "MANUAL_REVIEW"]
	assert body["decision_explanation"] is not None
	assert body["decision_explanation"]["rules_triggered"]
	assert body["decision_explanation"]["summary"]


async def test_submit_valid_employee_onboarding(client, sample_employee_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_background_check", _always_success)
	response = await client.post(
		"/api/v1/workflow/submit",
		json={
			"workflow_id": "employee_onboarding",
			"idempotency_key": "happy-emp-1",
			"payload": sample_employee_payload,
		},
	)
	assert response.status_code == 200
	body = response.json()
	assert body["status"] in ["APPROVED", "MANUAL_REVIEW"]
	assert body["decision_explanation"] is not None
	assert body["decision_explanation"]["rules_triggered"]
	assert body["decision_explanation"]["summary"]


async def test_get_workflow_details_after_submit(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	create = await client.post(
		"/api/v1/workflow/submit",
		json={
			"workflow_id": "application_approval",
			"idempotency_key": "happy-get-1",
			"payload": sample_application_payload,
		},
	)
	request_id = create.json()["request_id"]

	response = await client.get(f"/api/v1/workflow/{request_id}")
	assert response.status_code == 200
	assert response.json()["request_id"] == request_id


async def test_get_audit_trail_after_submit(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	create = await client.post(
		"/api/v1/workflow/submit",
		json={
			"workflow_id": "application_approval",
			"idempotency_key": "happy-audit-1",
			"payload": sample_application_payload,
		},
	)
	request_id = create.json()["request_id"]

	audit = await client.get(f"/api/v1/audit/{request_id}")
	assert audit.status_code == 200
	assert audit.json()["total_events"] > 0


async def test_get_history_after_submit(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	create = await client.post(
		"/api/v1/workflow/submit",
		json={
			"workflow_id": "application_approval",
			"idempotency_key": "happy-hist-1",
			"payload": sample_application_payload,
		},
	)
	request_id = create.json()["request_id"]

	history = await client.get(f"/api/v1/workflow/{request_id}/history")
	assert history.status_code == 200
	assert len(history.json()) >= 1
