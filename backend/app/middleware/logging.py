import uuid
import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        structlog.contextvars.bind_contextvars(request_id=request_id)
        logger.info("request_started",
                    method=request.method,
                    path=request.url.path)

        response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info("request_completed",
                    status_code=response.status_code,
                    elapsed_ms=elapsed_ms)

        structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = request_id
        return response
