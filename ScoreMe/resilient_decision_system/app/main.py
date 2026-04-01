from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.middleware import RequestLoggingMiddleware
from app.api.routes.audit_routes import router as audit_router
from app.api.routes.config_routes import router as config_router
from app.api.routes.workflow_routes import router as workflow_router
from app.database import init_db
from app.utils.exceptions import (
	DuplicateRequestError,
	InvalidPayloadError,
	InvalidStateTransitionError,
	WorkflowNotFoundError,
)
from config.loader import load_all_workflows


@asynccontextmanager
async def lifespan(_: FastAPI):
	await init_db()
	workflows_dir = Path(__file__).resolve().parents[1] / "config" / "workflows"
	if not workflows_dir.exists():
		workflows_dir = Path(__file__).resolve().parents[2] / "config" / "workflows"
	load_all_workflows(str(workflows_dir))
	yield


def create_app() -> FastAPI:
	app = FastAPI(
		title="Resilient Decision System",
		version="1.0.0",
		description=(
			"Configurable workflow decision platform with YAML-driven rules, "
			"idempotent request handling, full audit trail, and explainable outcomes."
		),
		lifespan=lifespan,
	)

	app.add_middleware(RequestLoggingMiddleware)
	app.add_middleware(
		CORSMiddleware,
		allow_origins=["*"],
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"],
	)

	@app.exception_handler(WorkflowNotFoundError)
	async def workflow_not_found_handler(_: Request, exc: WorkflowNotFoundError):
		return JSONResponse(status_code=404, content={"detail": str(exc)})

	@app.exception_handler(InvalidStateTransitionError)
	async def invalid_state_handler(_: Request, exc: InvalidStateTransitionError):
		return JSONResponse(status_code=400, content={"detail": str(exc)})

	@app.exception_handler(DuplicateRequestError)
	async def duplicate_handler(_: Request, exc: DuplicateRequestError):
		return JSONResponse(
			status_code=200,
			content={
				"detail": str(exc),
				"request_id": exc.existing_request.id,
				"idempotency_key": exc.existing_request.idempotency_key,
			},
			headers={"X-Idempotent-Replay": "true"},
		)

	@app.exception_handler(ValidationError)
	async def pydantic_validation_handler(_: Request, exc: ValidationError):
		return JSONResponse(status_code=422, content={"detail": exc.errors()})

	@app.exception_handler(RequestValidationError)
	async def request_validation_handler(_: Request, exc: RequestValidationError):
		return JSONResponse(status_code=422, content={"detail": exc.errors()})

	@app.exception_handler(InvalidPayloadError)
	async def invalid_payload_handler(_: Request, exc: InvalidPayloadError):
		return JSONResponse(status_code=400, content={"detail": str(exc)})

	@app.exception_handler(Exception)
	async def generic_handler(_: Request, exc: Exception):
		request_id = str(uuid4())
		return JSONResponse(
			status_code=500,
			content={"detail": "Internal server error", "request_id": request_id, "error": str(exc)},
		)

	app.include_router(workflow_router, prefix="/api/v1")
	app.include_router(audit_router, prefix="/api/v1")
	app.include_router(config_router, prefix="/api/v1")

	return app


app = create_app()
