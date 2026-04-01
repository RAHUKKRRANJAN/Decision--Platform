from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class SubmitWorkflowRequest(BaseModel):
	workflow_id: str
	idempotency_key: str
	payload: Dict[str, Any]


class RuleTrace(BaseModel):
	stage: str
	rule_id: str
	description: str
	result: str
	action: str
	field: str
	expected: Any
	actual: Any
	message: str


class DecisionExplanation(BaseModel):
	final_decision: str
	stages_evaluated: List[str]
	rules_triggered: List[RuleTrace]
	total_rules_passed: int
	total_rules_failed: int
	summary: str


class WorkflowStatusResponse(BaseModel):
	request_id: str
	idempotency_key: str
	workflow_id: str
	status: str
	current_stage: str
	retry_count: int
	created_at: datetime
	updated_at: datetime
	decision_explanation: Optional[DecisionExplanation] = None

	model_config = ConfigDict(from_attributes=True)
