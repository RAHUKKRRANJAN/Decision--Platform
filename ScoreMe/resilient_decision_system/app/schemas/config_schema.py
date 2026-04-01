from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class RuleConfig(BaseModel):
	rule_id: str
	description: str
	rule_type: Literal["mandatory_check", "threshold_check", "conditional_branch"]
	field: str
	operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "exists"]
	value: Any
	on_fail: Literal["reject", "manual_review", "retry"]
	error_message: str


class StageConfig(BaseModel):
	stage_id: str
	stage_name: str
	rules: List[str]
	on_success: str
	on_reject: str
	on_manual_review: str
	on_retry: str
	max_retries: int = Field(default=3, ge=0)
	retry_delay_seconds: float = Field(default=1.0, ge=0)
	requires_external_check: bool = False


class WorkflowConfig(BaseModel):
	workflow_id: str
	workflow_name: str
	version: str
	description: str
	entry_stage: str
	stages: List[StageConfig]
	rules: List[RuleConfig]
	input_schema: Dict[str, str]
