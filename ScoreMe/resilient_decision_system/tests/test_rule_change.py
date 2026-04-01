from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.core.external_dependency import ExternalCheckResult, ExternalDependencyService


pytestmark = pytest.mark.asyncio


async def _always_success(*_args, **_kwargs):
	return ExternalCheckResult(success=True, score=0.97, message="ok", latency_ms=8)


async def test_credit_score_700_passes_original_rule(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	payload = dict(sample_application_payload)
	payload["credit_score"] = 700
	response = await client.post(
		"/api/v1/workflow/submit",
		json={"workflow_id": "application_approval", "idempotency_key": "rule-change-1", "payload": payload},
	)
	assert response.status_code == 200
	assert response.json()["status"] in {"APPROVED", "MANUAL_REVIEW"}


async def test_change_threshold_and_reload_config(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	cfg_path = Path("config/workflows/application_approval.yaml")
	original_text = cfg_path.read_text(encoding="utf-8")

	try:
		cfg = yaml.safe_load(original_text)
		for rule in cfg["rules"]:
			if rule["rule_id"] == "rule_credit_score":
				rule["value"] = 750
		cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

		reload_resp = await client.post("/api/v1/config/reload")
		assert reload_resp.status_code == 200

		payload = dict(sample_application_payload)
		payload["credit_score"] = 700
		response = await client.post(
			"/api/v1/workflow/submit",
			json={"workflow_id": "application_approval", "idempotency_key": "rule-change-2", "payload": payload},
		)
		assert response.status_code == 200
		assert response.json()["status"] == "MANUAL_REVIEW"
	finally:
		cfg_path.write_text(original_text, encoding="utf-8")
		await client.post("/api/v1/config/reload")


async def test_add_new_rule_via_yaml_reload_reflected_in_audit(client, sample_application_payload, monkeypatch):
	monkeypatch.setattr(ExternalDependencyService, "call_credit_bureau", _always_success)
	cfg_path = Path("config/workflows/application_approval.yaml")
	original_text = cfg_path.read_text(encoding="utf-8")

	try:
		cfg = yaml.safe_load(original_text)
		cfg["rules"].append(
			{
				"rule_id": "rule_country_exists",
				"description": "Country field must exist",
				"rule_type": "mandatory_check",
				"field": "country",
				"operator": "exists",
				"value": True,
				"on_fail": "manual_review",
				"error_message": "Country missing",
			}
		)
		for stage in cfg["stages"]:
			if stage["stage_id"] == "intake_validation":
				stage["rules"].append("rule_country_exists")
		cfg["input_schema"]["country"] = "str"

		cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
		reload_resp = await client.post("/api/v1/config/reload")
		assert reload_resp.status_code == 200

		payload = dict(sample_application_payload)
		payload["country"] = "IN"
		response = await client.post(
			"/api/v1/workflow/submit",
			json={"workflow_id": "application_approval", "idempotency_key": "rule-change-3", "payload": payload},
		)
		assert response.status_code == 200
		request_id = response.json()["request_id"]

		audit = await client.get(f"/api/v1/audit/{request_id}")
		entries = audit.json()["audit_trail"]
		assert any(entry["rule_id"] == "rule_country_exists" for entry in entries)
	finally:
		cfg_path.write_text(original_text, encoding="utf-8")
		await client.post("/api/v1/config/reload")
