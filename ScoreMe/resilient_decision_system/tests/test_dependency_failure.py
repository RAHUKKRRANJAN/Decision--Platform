from __future__ import annotations

import pytest

from app.core.audit_service import AuditService
from app.core.external_dependency import ExternalDependencyService
from app.utils.exceptions import ExternalServiceTimeoutError, ExternalServiceUnavailableError


pytestmark = pytest.mark.asyncio


async def _always_timeout(*_args, **_kwargs):
	raise ExternalServiceTimeoutError("timeout")


async def _always_unavailable(*_args, **_kwargs):
	raise ExternalServiceUnavailableError("down")


async def test_external_timeout_retries_then_failed(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_timeout)
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "dep-fail-1", "payload": sample_application_payload},
	)
	assert response.status_code == 200
	body = response.json()
	assert body["status"] == "FAILED"
	assert body["retry_count"] == 3


async def test_external_unavailable_no_retry_manual_review(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_unavailable)
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "dep-fail-2", "payload": sample_application_payload},
	)
	assert response.status_code == 200
	body = response.json()
	assert body["status"] == "MANUAL_REVIEW"
	assert body["retry_count"] == 0


async def test_partial_save_failure_marks_failed(client, sample_application_payload, monkeypatch):
	original = AuditService.log_rule_evaluation
	calls = {"count": 0}

	async def fail_second(self, session, request_id, stage_id, rule, result, payload_value):
		calls["count"] += 1
		if calls["count"] == 2:
			raise RuntimeError("simulated DB write failure")
		await original(self, session, request_id, stage_id, rule, result, payload_value)

	monkeypatch.setattr(AuditService, "log_rule_evaluation", fail_second)
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "dep-fail-3", "payload": sample_application_payload},
	)
	assert response.status_code == 500
