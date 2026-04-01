# Architecture: Resilient Decision System

## 1. System Overview Diagram
```text
+---------+      +--------------------+      +--------------------+
| Client  | ---> | FastAPI API Layer  | ---> | Workflow Engine    |
+---------+      +--------------------+      +--------------------+
								|                           |      |      |
								|                           |      |      |
								v                           v      v      v
					  +-------------+            +-------------+  +----------------------+
					  | Middleware  |            | Rules Engine|  | External Dependencies|
					  | + Logging   |            +-------------+  | (simulated services) |
					  +-------------+                                 +-------------------+
								|
								v
					  +----------------------------+
					  | SQLite + SQLAlchemy Async  |
					  | WorkflowRequest, AuditLog, |
					  | StateHistory               |
					  +----------------------------+
```

## 2. Component Descriptions
- `app/main.py`: FastAPI app factory, middleware, exception handlers, startup initialization.
- `app/api/routes/workflow_routes.py`: Submit/get/history/retry workflow request APIs.
- `app/api/routes/audit_routes.py`: Audit trail and explanation APIs.
- `app/api/routes/config_routes.py`: Workflow config listing/detail/reload APIs.
- `app/core/workflow_engine.py`: Orchestrates stage traversal, retries, external checks, and final decisions.
- `app/core/rules_engine.py`: Evaluates all configured rules with operator support and explainable traces.
- `app/core/state_manager.py`: Enforces legal lifecycle transitions and writes state history.
- `app/core/audit_service.py`: Persists rule audit events and builds decision explanations.
- `app/core/idempotency.py`: Prevents duplicate request processing.
- `app/core/external_dependency.py`: Simulates external checks with failure injection.
- `config/loader.py`: Loads, validates, caches, and hot-reloads workflow YAML.
- `app/database.py` + `app/models/*`: Async SQLAlchemy infrastructure and persistence entities.
- `app/utils/logger.py`: JSON structured logging with `request_id` context propagation.
- `app/utils/exceptions.py`: Domain exception taxonomy.

## 3. Data Flow
1. Client submits `POST /api/v1/workflow/submit`.
2. API validates workflow ID and payload against YAML input schema.
3. Idempotency check determines replay vs new request.
4. New request persisted as `PENDING`.
5. Workflow engine transitions request to `IN_PROGRESS`.
6. Current stage rules are evaluated in order.
7. Every evaluated rule is written to `AuditLog`.
8. If stage needs external check, service is called with retry policy:
	- timeout -> retry up to 3 attempts
	- unavailable -> immediate manual review
9. Stage outcome determines next transition:
	- success -> next stage or `APPROVED` if `DONE`
	- reject -> `REJECTED`
	- manual review -> `MANUAL_REVIEW`
	- retry -> `RETRY` then back to `IN_PROGRESS` or `FAILED` when max retries reached
10. Final response returns full status and decision explanation.

## 4. Database Schema

### `workflow_requests`
- `id` (PK, UUID string)
- `idempotency_key` (unique index)
- `workflow_id` (index)
- `status`
- `current_stage`
- `payload` (JSON text)
- `created_at`, `updated_at`
- `retry_count`
- `workflow_version`

### `audit_logs`
- `id` (PK)
- `request_id` (FK -> `workflow_requests.id`, indexed)
- rule metadata: `stage_id`, `rule_id`, `rule_description`, `rule_type`
- evaluated value context: `field_evaluated`, `field_value`, `operator`, `expected_value`
- `result`, `action_taken`, `timestamp`, `error_message`

### `state_history`
- `id` (PK)
- `request_id` (FK -> `workflow_requests.id`, indexed)
- `from_status`, `to_status`
- `from_stage`, `to_stage`
- `transition_reason`, `triggered_by`, `timestamp`
- `metadata` (JSON text)

Relationship summary:
- One `WorkflowRequest` to many `AuditLog`
- One `WorkflowRequest` to many `StateHistory`

## 5. State Machine Diagram
```text
PENDING ----> IN_PROGRESS ----> APPROVED
	|              |   |   \----> REJECTED
	|              |   \-------> MANUAL_REVIEW
	|              \-----------> RETRY ----> IN_PROGRESS
	|                                 \----> FAILED
	\---------------------------------------------> FAILED (error path)
```

Valid transitions enforced:
- `PENDING -> IN_PROGRESS`
- `IN_PROGRESS -> APPROVED | REJECTED | MANUAL_REVIEW | RETRY | FAILED`
- `RETRY -> IN_PROGRESS | FAILED`

## 6. Configuration Model
YAML workflow config maps directly into `WorkflowConfig` Pydantic schema:
- `rules[]` define reusable rule definitions.
- `stages[]` reference rule IDs and transition directives.
- `input_schema` defines required payload fields and expected primitive types.

Hot reload process:
1. Update YAML file(s).
2. Call `POST /api/v1/config/reload`.
3. Loader validates and atomically swaps in-memory cache.

## 7. Trade-offs and Design Decisions
- SQLite chosen for hackathon simplicity and zero-infra startup; async SQLAlchemy keeps migration path open.
- YAML chosen over DB-driven config because it is human-readable, diff-friendly, version-controllable, and easy to hot-reload.
- Rule evaluation returns first-failure outcome but logs all rules for explainability and audit completeness.
- Tenacity selected for declarative retry logic and deterministic retry policy testing.
- Async architecture chosen to better handle concurrent I/O (DB + external checks).

## 8. Scaling Considerations
- Replace SQLite with PostgreSQL and async connection pooling.
- Add Redis idempotency cache for low-latency duplicate lookup.
- Introduce Celery/RQ workers to decouple HTTP request lifecycle from long-running workflow execution.
- Stream audit events to Kafka for analytics and compliance pipelines.
- Horizontal scale API replicas as stateless services with shared DB/cache.
- Persist workflow config versions in DB to support historical replay against exact past rule sets.

## 9. Assumptions Made
- Payload type validation is primitive (`str/int/float/bool/list/dict`) based on YAML `input_schema` hints.
- Audit logs are append-only and immutable via API (no delete endpoint).
- Manual retry endpoint allows retries for `FAILED` and `MANUAL_REVIEW`; blocks `APPROVED` and `REJECTED`.
- External dependency simulation is intentionally probabilistic for resilience testing.
- For Python 3.13 environments, SQLAlchemy requires a newer version than `2.0.30`; compatibility pin applied in `requirements.txt`.
