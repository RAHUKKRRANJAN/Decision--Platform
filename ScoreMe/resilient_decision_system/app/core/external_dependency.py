from __future__ import annotations

import asyncio
import os
import random
from dataclasses import dataclass

from app.utils.exceptions import ExternalServiceTimeoutError, ExternalServiceUnavailableError
from app.utils.logger import get_logger, log_external_call


@dataclass
class ExternalCheckResult:
	success: bool
	score: float
	message: str
	latency_ms: int


class ExternalDependencyService:
	"""
	Simulates calling an external API.
	- 70% of the time: returns success with a score/result
	- 20% of the time: raises ExternalServiceTimeoutError (simulate timeout)
	- 10% of the time: raises ExternalServiceUnavailableError (service down)
	"""

	def __init__(self) -> None:
		self.logger = get_logger(__name__)
		self.failure_rate = float(os.getenv("FAILURE_INJECTION_RATE", "0.3"))

	async def _simulate(self, service: str, identifier: str) -> ExternalCheckResult:
		latency_ms = random.randint(50, 500)
		await asyncio.sleep(latency_ms / 1000)

		failure_roll = random.random()
		timeout_threshold = self.failure_rate * (2 / 3)
		unavailable_threshold = self.failure_rate

		if failure_roll < timeout_threshold:
			log_external_call(self.logger, service, latency_ms, False)
			raise ExternalServiceTimeoutError(f"{service} timeout for identifier {identifier}")
		if failure_roll < unavailable_threshold:
			log_external_call(self.logger, service, latency_ms, False)
			raise ExternalServiceUnavailableError(f"{service} unavailable for identifier {identifier}")

		result = ExternalCheckResult(
			success=True,
			score=round(random.uniform(0.6, 0.99), 3),
			message=f"{service} succeeded",
			latency_ms=latency_ms,
		)
		log_external_call(self.logger, service, latency_ms, True)
		return result

	async def call_credit_bureau(self, applicant_id: str) -> ExternalCheckResult:
		return await self._simulate("credit_bureau", applicant_id)

	async def call_document_verifier(self, claim_id: str) -> ExternalCheckResult:
		return await self._simulate("document_verifier", claim_id)

	async def call_background_check(self, employee_id: str) -> ExternalCheckResult:
		return await self._simulate("background_check", employee_id)
