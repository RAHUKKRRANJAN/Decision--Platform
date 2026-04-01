from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from app.schemas.config_schema import RuleConfig, StageConfig
from app.schemas.request_schema import RuleTrace
from app.utils.exceptions import RuleEvaluationError


@dataclass
class RuleEvaluationResult:
	rule_id: str
	passed: bool
	action: str
	trace: RuleTrace


@dataclass
class StageEvaluationResult:
	stage_id: str
	overall_outcome: Literal["SUCCESS", "REJECTED", "MANUAL_REVIEW", "RETRY"]
	rules_evaluated: List[RuleEvaluationResult]
	first_failure: Optional[RuleEvaluationResult]


class RulesEngine:
	def _coerce(self, left: Any, right: Any) -> tuple[Any, Any]:
		if isinstance(left, (int, float)) and isinstance(right, str):
			try:
				return left, float(right)
			except ValueError:
				return left, right
		if isinstance(right, (int, float)) and isinstance(left, str):
			try:
				return float(left), right
			except ValueError:
				return left, right
		return left, right

	def _eval_operator(self, operator: str, actual: Any, expected: Any) -> bool:
		actual, expected = self._coerce(actual, expected)
		if operator == "eq":
			return actual == expected
		if operator == "neq":
			return actual != expected
		if operator == "gt":
			return actual > expected
		if operator == "gte":
			return actual >= expected
		if operator == "lt":
			return actual < expected
		if operator == "lte":
			return actual <= expected
		if operator == "in":
			return actual in expected
		if operator == "not_in":
			return actual not in expected
		if operator == "exists":
			return actual is not None
		raise RuleEvaluationError(f"Unsupported operator: {operator}")

	def evaluate_rule(self, stage_id: str, rule: RuleConfig, payload: dict) -> RuleEvaluationResult:
		field_exists = rule.field in payload
		actual = payload.get(rule.field)

		if not field_exists and rule.operator != "exists":
			message = "field not found in payload"
			trace = RuleTrace(
				stage=stage_id,
				rule_id=rule.rule_id,
				description=rule.description,
				result="FAIL",
				action=rule.on_fail,
				field=rule.field,
				expected={"operator": rule.operator, "value": rule.value},
				actual=None,
				message=message,
			)
			return RuleEvaluationResult(rule_id=rule.rule_id, passed=False, action=rule.on_fail, trace=trace)

		try:
			passed = self._eval_operator(rule.operator, actual, rule.value)
		except Exception as exc:  # noqa: BLE001
			raise RuleEvaluationError(f"Error evaluating rule {rule.rule_id}: {exc}") from exc

		result = "PASS" if passed else "FAIL"
		action = "continue" if passed else rule.on_fail
		message = (
			f"{rule.field}={actual} satisfies {rule.operator} {rule.value}"
			if passed
			else f"{rule.field}={actual} does not satisfy {rule.operator} {rule.value}"
		)
		trace = RuleTrace(
			stage=stage_id,
			rule_id=rule.rule_id,
			description=rule.description,
			result=result,
			action=action,
			field=rule.field,
			expected={"operator": rule.operator, "value": rule.value},
			actual=actual,
			message=message if passed else rule.error_message,
		)
		return RuleEvaluationResult(rule_id=rule.rule_id, passed=passed, action=action, trace=trace)

	def evaluate_stage_rules(
		self,
		stage: StageConfig,
		all_rules: Dict[str, RuleConfig],
		payload: dict,
	) -> StageEvaluationResult:
		evaluations: List[RuleEvaluationResult] = []
		first_failure: Optional[RuleEvaluationResult] = None

		for rule_id in stage.rules:
			rule = all_rules[rule_id]
			result = self.evaluate_rule(stage.stage_id, rule, payload)
			evaluations.append(result)
			if not result.passed and first_failure is None:
				first_failure = result

		if first_failure is None:
			outcome: Literal["SUCCESS", "REJECTED", "MANUAL_REVIEW", "RETRY"] = "SUCCESS"
		elif first_failure.action == "reject":
			outcome = "REJECTED"
		elif first_failure.action == "manual_review":
			outcome = "MANUAL_REVIEW"
		else:
			outcome = "RETRY"

		return StageEvaluationResult(
			stage_id=stage.stage_id,
			overall_outcome=outcome,
			rules_evaluated=evaluations,
			first_failure=first_failure,
		)
