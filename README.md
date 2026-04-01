# Resilient Decision System

A configurable workflow decision engine built with FastAPI, SQLAlchemy async, YAML configs, and a complete audit trail.

This project is designed for cases where decisions must be:
- configurable without changing code,
- resilient to failures,
- safe against duplicate requests,
- and explainable to humans.

---

## Project Overview

The system executes business workflows like:
- application approval,
- claim processing,
- employee onboarding.

Each workflow is defined in YAML and loaded at runtime. Every rule evaluation is logged, every state transition is recorded, and each request returns a clear decision explanation.

### What You Get
- YAML-driven workflows and rules
- Hot config reload (`/api/v1/config/reload`)
- Idempotency by `idempotency_key`
- External dependency simulation with retry behavior
- Rule-level audit logs
- Request lifecycle history
- Explainable final decision response

---

## High-Level Architecture

```text
Client
	|
	v
+---------------------------+
| FastAPI API Layer         |
| - Workflow Routes         |
| - Audit Routes            |
| - Config Routes           |
| - Request Logging MW      |
+---------------------------+
	|
	v
+---------------------------+
| Workflow Engine           |
| - State Manager           |
| - Rules Engine            |
| - Audit Service           |
| - Idempotency Check       |
| - External Dependencies   |
+---------------------------+
	|
	v
+---------------------------+
| SQLite (SQLAlchemy Async) |
| - WorkflowRequest         |
| - AuditLog                |
| - StateHistory            |
+---------------------------+
	^
	|
+---------------------------+
| YAML Config Loader        |
| - Workflow validation     |
| - In-memory cache         |
| - Hot reload              |
+---------------------------+
```

---

## Quickstart

### 1) Install dependencies
```bash
pip install -r requirements.txt
```

### 2) Run the server
```bash
python run.py
```

### 3) Open API docs
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## API Documentation

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/workflow/submit` | Submit a workflow request |
| GET | `/api/v1/workflow/{request_id}` | Get current status and explanation |
| GET | `/api/v1/workflow/{request_id}/history` | Get state transition history |
| POST | `/api/v1/workflow/{request_id}/retry` | Retry FAILED/MANUAL_REVIEW request |
| GET | `/api/v1/audit/{request_id}` | Get complete audit trail |
| GET | `/api/v1/audit/{request_id}/explanation` | Get decision explanation only |
| GET | `/api/v1/config/workflows` | List all loaded workflows |
| GET | `/api/v1/config/workflows/{workflow_id}` | Get one workflow config |
| POST | `/api/v1/config/reload` | Reload workflow YAML files |

### Submit Request Example
```json
{
	"workflow_id": "application_approval",
	"idempotency_key": "req-001",
	"payload": {
		"applicant_id": "app-1001",
		"applicant_age": 30,
		"credit_score": 720,
		"requested_amount": 150000,
		"income": 85000,
		"employment_status": "employed",
		"debt_to_income_ratio": 0.31
	}
}
```

---

## Workflow Configuration Guide

All workflows live in:
- `config/workflows/*.yaml`

Each workflow YAML contains:
- workflow metadata (`workflow_id`, `workflow_name`, `version`, `description`)
- `entry_stage`
- `input_schema` (payload contract)
- `stages` (flow graph + transitions)
- `rules` (validation/decision logic)

### Supported Operators
- `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `exists`

### Add a New Workflow (No Code Change)
1. Add a new YAML file in `config/workflows/`
2. Define `input_schema`, `stages`, and `rules`
3. Call `POST /api/v1/config/reload`

---

## Example Requests

### Application Approval
```bash
curl -X POST "http://localhost:8000/api/v1/workflow/submit" \
	-H "Content-Type: application/json" \
	-d '{
		"workflow_id": "application_approval",
		"idempotency_key": "app-req-001",
		"payload": {
			"applicant_id": "A-100",
			"applicant_age": 28,
			"credit_score": 710,
			"requested_amount": 120000,
			"income": 95000,
			"employment_status": "employed",
			"debt_to_income_ratio": 0.35
		}
	}'
```

### Claim Processing
```bash
curl -X POST "http://localhost:8000/api/v1/workflow/submit" \
	-H "Content-Type: application/json" \
	-d '{
		"workflow_id": "claim_processing",
		"idempotency_key": "claim-req-001",
		"payload": {
			"claim_id": "C-200",
			"policy_active": true,
			"claim_amount": 50000,
			"days_since_incident": 7,
			"document_count": 3,
			"claimant_id": "U-903"
		}
	}'
```

### Employee Onboarding
```bash
curl -X POST "http://localhost:8000/api/v1/workflow/submit" \
	-H "Content-Type: application/json" \
	-d '{
		"workflow_id": "employee_onboarding",
		"idempotency_key": "onboard-req-001",
		"payload": {
			"employee_id": "E-301",
			"employee_email": "e301@company.com",
			"department": "engineering",
			"start_date": "2026-04-15",
			"salary": 98000
		}
	}'
```

### Check Status
```bash
curl "http://localhost:8000/api/v1/workflow/{request_id}"
```

### Get Audit Trail
```bash
curl "http://localhost:8000/api/v1/audit/{request_id}"
```

---

## Decision Explanation Example

```json
{
	"request_id": "uuid-here",
	"workflow_id": "application_approval",
	"status": "MANUAL_REVIEW",
	"decision_explanation": {
		"final_decision": "MANUAL_REVIEW",
		"stages_evaluated": ["intake_validation", "credit_check"],
		"rules_triggered": [
			{
				"stage": "intake_validation",
				"rule_id": "rule_age_check",
				"description": "Applicant must be 18 or older",
				"result": "PASS",
				"action": "continue",
				"field": "applicant_age",
				"expected": {"operator": "gte", "value": 18},
				"actual": 25,
				"message": "applicant_age=25 satisfies gte 18"
			},
			{
				"stage": "credit_check",
				"rule_id": "rule_credit_score",
				"description": "Credit score must be at least 650",
				"result": "FAIL",
				"action": "manual_review",
				"field": "credit_score",
				"expected": {"operator": "gte", "value": 650},
				"actual": 620,
				"message": "credit_score=620 does not satisfy gte 650"
			}
		],
		"total_rules_passed": 3,
		"total_rules_failed": 1,
		"summary": "Request passed intake validation (3/3 rules passed). Credit check failed: credit_score of 620 is below minimum threshold of 650. Request has been escalated for manual review."
	}
}
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Structured logger level |
| `FAILURE_INJECTION_RATE` | `0.3` | External dependency failure probability |
| `DATABASE_URL` | `sqlite+aiosqlite:///./decision_system.db` | Async SQLAlchemy database URL |

---

## Idempotency Guide

Idempotency ensures a request is processed exactly once for a given key.

How it works:
1. First call with a new `idempotency_key` creates and executes a request.
2. Repeating the same key returns the existing request state.
3. Replay responses include header: `X-Idempotent-Replay: true`.

Example retry scenario:
1. Client submits request with `idempotency_key=payment-123`
2. Client times out before receiving response
3. Client retries with same key
4. Server returns same `request_id` and current/final state safely
