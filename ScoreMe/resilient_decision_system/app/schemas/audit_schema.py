from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class AuditEntry(BaseModel):
	stage_id: str
	rule_id: str
	rule_description: str
	field_evaluated: str
	field_value: Any
	operator: str
	expected_value: Any
	result: str
	action_taken: str
	timestamp: datetime
	error_message: Optional[str] = None


class AuditResponse(BaseModel):
	request_id: str
	total_events: int
	audit_trail: List[AuditEntry]
