from __future__ import annotations

import pytest

from app.core.external_dependency import ExternalCheckResult, ExternalDependencyService


pytestmark = pytest.mark.asyncio


async def _always_success(*_args, **_kwargs):
	return ExternalCheckResult(success=True, score=0.92, message="ok", latency_ms=10)


async def test_every_rule_appears_in_audit(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "audit-1", "payload": sample_application_payload},
	)
	request_id = response.json()["request_id"]

	audit = await client.get(f"/api/v1/audit/{request_id}")
	assert audit.status_code == 200
	assert audit.json()["total_events"] >= 6


async def test_audit_for_rejected_request_contains_fail_and_prior_passes(
	client, sample_application_payload, monkeypatch
):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	payload = dict(sample_application_payload)
	payload["applicant_age"] = 17

	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "audit-2", "payload": payload},
	)
	request_id = response.json()["request_id"]
	assert response.json()["status"] == "REJECTED"

	audit = await client.get(f"/api/v1/audit/{request_id}")
	trail = audit.json()["audit_trail"]
	assert any(e["result"] == "FAIL" and e["action_taken"] == "reject" for e in trail)
	assert any(e["result"] == "PASS" for e in trail)


async def test_audit_explanation_human_readable(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "audit-3", "payload": sample_application_payload},
	)
	request_id = response.json()["request_id"]

	explanation = await client.get(f"/api/v1/audit/{request_id}/explanation")
	assert explanation.status_code == 200
	body = explanation.json()
	assert body["summary"]
	assert body["rules_triggered"]


async def test_audit_trail_is_immutable_no_delete_endpoint(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "audit-4", "payload": sample_application_payload},
	)
	request_id = response.json()["request_id"]

	delete_resp = await client.delete(f"/api/v1/audit/{request_id}")
	assert delete_resp.status_code in {404, 405}
