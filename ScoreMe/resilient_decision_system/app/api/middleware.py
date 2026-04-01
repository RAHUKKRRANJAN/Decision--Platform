from __future__ import annotations

import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.utils.logger import clear_request_id, get_logger, set_request_id


class RequestLoggingMiddleware(BaseHTTPMiddleware):
	def __init__(self, app):
		super().__init__(app)
		self.logger = get_logger(__name__)

	async def dispatch(self, request: Request, call_next):
		request_id = request.headers.get("X-Request-ID", str(uuid4()))
		set_request_id(request_id)
		start = time.perf_counter()

		try:
			response = await call_next(request)
			return response
		finally:
			latency_ms = int((time.perf_counter() - start) * 1000)
			status_code = getattr(locals().get("response"), "status_code", 500)
			self.logger.info(
				"API request",
				extra={
					"extra": {
						"method": request.method,
						"path": request.url.path,
						"status_code": status_code,
						"latency_ms": latency_ms,
					}
				},
			)
			clear_request_id()
