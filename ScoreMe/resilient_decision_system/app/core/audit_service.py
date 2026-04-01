from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rules_engine import RuleEvaluationResult
from app.models.audit_model import AuditLog
from app.models.request_model import WorkflowRequest
from app.models.state_model import StateHistory
from app.schemas.config_schema import RuleConfig
from app.schemas.request_schema import DecisionExplanation, RuleTrace


class AuditService:
	async def log_rule_evaluation(
		self,
		session: AsyncSession,
		request_id: str,
		stage_id: str,
		rule: RuleConfig,
		result: RuleEvaluationResult,
		payload_value: Any,
	) -> None:
		entry = AuditLog(
			request_id=request_id,
			stage_id=stage_id,
			rule_id=rule.rule_id,
			rule_description=rule.description,
			rule_type=rule.rule_type,
			field_evaluated=rule.field,
			field_value=json.dumps(payload_value, default=str),
			operator=rule.operator,
			expected_value=json.dumps(rule.value, default=str),
			result="PASS" if result.passed else "FAIL",
			action_taken=result.action,
			error_message=None if result.passed else result.trace.message,
		)
		session.add(entry)

	async def get_full_audit(self, session: AsyncSession, request_id: str) -> List[AuditLog]:
		stmt = select(AuditLog).where(AuditLog.request_id == request_id).order_by(AuditLog.timestamp.asc())
		result = await session.execute(stmt)
		return list(result.scalars().all())

	def build_decision_explanation(
		self,
		request: WorkflowRequest,
		audit_logs: List[AuditLog],
		state_history: List[StateHistory],
	) -> DecisionExplanation:
		traces: list[RuleTrace] = []
		passed = 0
		failed = 0

		for log in audit_logs:
			actual = json.loads(log.field_value)
			expected = json.loads(log.expected_value)
			trace = RuleTrace(
				stage=log.stage_id,
				rule_id=log.rule_id,
				description=log.rule_description,
				result=log.result,
				action=log.action_taken,
				field=log.field_evaluated,
				expected={"operator": log.operator, "value": expected},
				actual=actual,
				message=log.error_message
				if log.error_message
				else f"{log.field_evaluated} satisfied {log.operator}",
			)
			traces.append(trace)
			if log.result == "PASS":
				passed += 1
			else:
				failed += 1

		stage_order = list(OrderedDict.fromkeys([entry.to_stage for entry in state_history if entry.to_stage]))
		if not stage_order:
			stage_order = list(OrderedDict.fromkeys([trace.stage for trace in traces]))

		summary = (
			f"Request {request.id} reached {request.status} after evaluating "
			f"{len(stage_order)} stages with {passed} passed and {failed} failed rules."
		)

		return DecisionExplanation(
			final_decision=request.status,
			stages_evaluated=stage_order,
			rules_triggered=traces,
			total_rules_passed=passed,
			total_rules_failed=failed,
			summary=summary,
		)
