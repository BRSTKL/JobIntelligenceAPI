from __future__ import annotations

import logging
from contextvars import ContextVar, Token


_request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Attach the active request ID to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_context.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Set up basic application logging once."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(request_id)s | %(name)s | %(message)s"
        )
    )
    handler.addFilter(RequestIdFilter())

    root_logger.setLevel(level)
    root_logger.addHandler(handler)


def set_request_id(request_id: str) -> Token[str]:
    """Store the request ID for the current request context."""
    return _request_id_context.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    """Restore the previous request ID when a request finishes."""
    _request_id_context.reset(token)
