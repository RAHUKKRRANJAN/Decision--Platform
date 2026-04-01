from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.audit_service import AuditService
from app.core.external_dependency import ExternalDependencyService
from app.core.rules_engine import RulesEngine
from app.core.state_manager import StateManager
from app.models.request_model import WorkflowRequest
from app.schemas.config_schema import StageConfig, WorkflowConfig
from app.schemas.request_schema import DecisionExplanation
from app.utils.exceptions import (
	ExternalServiceTimeoutError,
	ExternalServiceUnavailableError,
	PartialSaveFailureError,
)
from app.utils.logger import get_logger


@dataclass
class WorkflowExecutionResult:
	request: WorkflowRequest
	decision_explanation: DecisionExplanation


class WorkflowEngine:
	def __init__(self) -> None:
		self.rules_engine = RulesEngine()
		self.state_manager = StateManager()
		self.audit_service = AuditService()
		self.external_service = ExternalDependencyService()
		self.logger = get_logger(__name__)

	@retry(
		wait=wait_exponential(multiplier=1, min=1, max=10),
		stop=stop_after_attempt(3),
		retry=retry_if_exception_type(ExternalServiceTimeoutError),
		reraise=True,
	)
	async def _external_call_with_retry(self, workflow_id: str, payload: dict[str, Any]):
		if workflow_id == "application_approval":
			return await self.external_service.call_credit_bureau(payload.get("applicant_id", "unknown"))
		if workflow_id == "claim_processing":
			return await self.external_service.call_document_verifier(payload.get("claim_id", "unknown"))
		if workflow_id == "employee_onboarding":
			return await self.external_service.call_background_check(payload.get("employee_id", "unknown"))
		return None

	async def _handle_stage_retry(
		self,
		session: AsyncSession,
		request: WorkflowRequest,
		stage: StageConfig,
		reason: str,
	) -> bool:
		request.retry_count += 1
		if request.retry_count >= stage.max_retries:
			await self.state_manager.transition(
				session,
				request,
				"FAILED",
				request.current_stage,
				f"Max retries reached for stage {stage.stage_id}. Last reason: {reason}",
				"retry_handler",
				{"stage_id": stage.stage_id, "retry_count": request.retry_count},
			)
			return False

		await self.state_manager.transition(
			session,
			request,
			"RETRY",
			stage.stage_id,
			reason,
			"retry_handler",
			{"retry_count": request.retry_count},
		)
		await session.commit()
		await asyncio.sleep(stage.retry_delay_seconds)
		await self.state_manager.transition(
			session,
			request,
			"IN_PROGRESS",
			stage.stage_id,
			f"Retrying stage {stage.stage_id}",
			"retry_handler",
			{"retry_count": request.retry_count},
		)
		return True

	async def execute_workflow(
		self,
		request_id: str,
		workflow_config: WorkflowConfig,
		payload: dict,
		session: AsyncSession,
	) -> WorkflowExecutionResult:
		rules_by_id = {rule.rule_id: rule for rule in workflow_config.rules}
		stages_by_id = {stage.stage_id: stage for stage in workflow_config.stages}

		request_stmt = select(WorkflowRequest).where(WorkflowRequest.id == request_id)
		request_result = await session.execute(request_stmt)
		request = request_result.scalar_one()

		try:
			if request.status == "PENDING":
				await self.state_manager.transition(
					session,
					request,
					"IN_PROGRESS",
					workflow_config.entry_stage,
					"Workflow execution started",
					"system",
					None,
				)
				await session.commit()

			current_stage_id = request.current_stage or workflow_config.entry_stage

			while True:
				stage = stages_by_id[current_stage_id]
				stage_eval = self.rules_engine.evaluate_stage_rules(stage, rules_by_id, payload)

				for eval_result in stage_eval.rules_evaluated:
					rule = rules_by_id[eval_result.rule_id]
					await self.audit_service.log_rule_evaluation(
						session,
						request.id,
						stage.stage_id,
						rule,
						eval_result,
						payload.get(rule.field),
					)

				if stage.requires_external_check and stage_eval.overall_outcome == "SUCCESS":
					try:
						await self._external_call_with_retry(workflow_config.workflow_id, payload)
					except ExternalServiceUnavailableError:
						stage_eval.overall_outcome = "MANUAL_REVIEW"
					except ExternalServiceTimeoutError as exc:
						should_continue = await self._handle_stage_retry(session, request, stage, str(exc))
						if not should_continue:
							await session.commit()
							break
						await session.commit()
						continue

				if stage_eval.overall_outcome == "SUCCESS":
					if stage.on_success == "DONE":
						await self.state_manager.transition(
							session,
							request,
							"APPROVED",
							stage.stage_id,
							f"Stage {stage.stage_id} completed. Workflow approved.",
							"rule_engine",
							None,
						)
						await session.commit()
						break

					request.current_stage = stage.on_success
					request.updated_at = datetime.now(timezone.utc)
					await session.commit()
					current_stage_id = stage.on_success
					continue

				if stage_eval.overall_outcome == "REJECTED":
					await self.state_manager.transition(
						session,
						request,
						"REJECTED",
						stage.stage_id,
						f"Stage {stage.stage_id} rejected request",
						"rule_engine",
						None,
					)
					await session.commit()
					break

				if stage_eval.overall_outcome == "MANUAL_REVIEW":
					await self.state_manager.transition(
						session,
						request,
						"MANUAL_REVIEW",
						stage.stage_id,
						f"Stage {stage.stage_id} flagged for manual review",
						"rule_engine",
						None,
					)
					await session.commit()
					break

				should_continue = await self._handle_stage_retry(
					session,
					request,
					stage,
					f"Rule failure triggered retry in stage {stage.stage_id}",
				)
				await session.commit()
				if not should_continue:
					break
				current_stage_id = stage.stage_id

		except Exception as exc:  # noqa: BLE001
			request_pk = request.id
			await session.rollback()
			try:
				reload_stmt = select(WorkflowRequest).where(WorkflowRequest.id == request_pk)
				reload_result = await session.execute(reload_stmt)
				reload_request = reload_result.scalar_one_or_none()
				if reload_request is None:
					raise PartialSaveFailureError("Request disappeared before failure handling")

				if reload_request.status in {"PENDING", "IN_PROGRESS", "RETRY"}:
					if reload_request.status == "PENDING":
						reload_request.status = "IN_PROGRESS"
					await self.state_manager.transition(
						session,
						reload_request,
						"FAILED",
						reload_request.current_stage,
						f"PARTIAL_FAILURE: {exc}",
						"system",
						{"error": str(exc)},
					)
				else:
					reload_request.status = "FAILED"
					reload_request.updated_at = datetime.now(timezone.utc)
					await session.flush()
				await session.commit()
			except Exception as db_exc:  # noqa: BLE001
				raise PartialSaveFailureError(
					f"Workflow execution failed and save failed: {db_exc}"
				) from db_exc
			raise PartialSaveFailureError(f"Workflow execution failure: {exc}") from exc

		await session.refresh(request)
		audit_logs = await self.audit_service.get_full_audit(session, request.id)
		state_history = await self.state_manager.get_history(session, request.id)
		explanation = self.audit_service.build_decision_explanation(request, audit_logs, state_history)
		return WorkflowExecutionResult(request=request, decision_explanation=explanation)
