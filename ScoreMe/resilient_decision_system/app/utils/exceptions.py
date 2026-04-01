from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
	from app.models.request_model import WorkflowRequest


class WorkflowNotFoundError(Exception):
	pass


class InvalidStateTransitionError(Exception):
	pass


class DuplicateRequestError(Exception):
	def __init__(self, existing_request: "WorkflowRequest"):
		self.existing_request = existing_request
		super().__init__(
			f"Duplicate request for idempotency key {existing_request.idempotency_key}"
		)


class ExternalServiceTimeoutError(Exception):
	pass


class ExternalServiceUnavailableError(Exception):
	pass


class InvalidPayloadError(Exception):
	pass


class RuleEvaluationError(Exception):
	pass


class PartialSaveFailureError(Exception):
	pass


class ConfigValidationError(Exception):
	pass
