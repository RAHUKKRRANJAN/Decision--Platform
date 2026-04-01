from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict


request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
	"request_id", default=None
)


def set_request_id(request_id: str) -> None:
	request_id_ctx.set(request_id)


def get_request_id() -> str | None:
	return request_id_ctx.get()


def clear_request_id() -> None:
	request_id_ctx.set(None)


class JsonFormatter(logging.Formatter):
	def format(self, record: logging.LogRecord) -> str:
		payload: Dict[str, Any] = {
			"timestamp": datetime.now(timezone.utc).isoformat(),
			"level": record.levelname,
			"name": record.name,
			"message": record.getMessage(),
			"extra": {},
		}

		rid = get_request_id()
		if rid:
			payload["request_id"] = rid

		for attr in ("extra", "rule_id", "result", "field", "value", "from_status", "to_status"):
			if hasattr(record, attr):
				if attr == "extra" and isinstance(getattr(record, attr), dict):
					payload["extra"].update(getattr(record, attr))
				elif attr != "extra":
					payload["extra"][attr] = getattr(record, attr)

		if record.exc_info:
			payload["extra"]["exception"] = self.formatException(record.exc_info)

		return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
	logger = logging.getLogger(name)
	if logger.handlers:
		return logger

	level_name = os.getenv("LOG_LEVEL", "INFO").upper()
	logger.setLevel(getattr(logging, level_name, logging.INFO))

	handler = logging.StreamHandler(sys.stdout)
	handler.setFormatter(JsonFormatter())
	logger.addHandler(handler)
	logger.propagate = False
	return logger


def log_rule_evaluation(
	logger: logging.Logger,
	rule_id: str,
	result: str,
	field: str,
	value: Any,
) -> None:
	logger.info(
		"Rule evaluated",
		extra={"extra": {"rule_id": rule_id, "result": result, "field": field, "value": value}},
	)


def log_state_transition(
	logger: logging.Logger,
	request_id: str,
	from_status: str,
	to_status: str,
	reason: str,
) -> None:
	logger.info(
		"State transition",
		extra={
			"extra": {
				"request_id": request_id,
				"from": from_status,
				"to": to_status,
				"reason": reason,
			}
		},
	)


def log_external_call(
	logger: logging.Logger,
	service: str,
	latency_ms: int,
	success: bool,
) -> None:
	logger.info(
		"External dependency call",
		extra={
			"extra": {
				"service": service,
				"latency_ms": latency_ms,
				"success": success,
			}
		},
	)
