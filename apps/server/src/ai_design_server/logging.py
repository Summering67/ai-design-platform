from __future__ import annotations

import json
import logging
import time
from typing import Any

from .config import LogConfig

_SENSITIVE = {"authorization", "cookie", "password", "token", "api_key", "dsn", "body"}
_LOG_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "logger": record.name,
        }
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _LOG_RECORD_FIELDS:
                continue
            if key.lower() in _SENSITIVE:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = "unhandled_error"
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args and isinstance(record.args, dict):
            record.args = {key: value for key, value in record.args.items() if key not in _SENSITIVE}
        return True


def configure_logging(config: LogConfig) -> logging.Logger:
    logger = logging.getLogger("ai_design_server")
    logger.handlers.clear()
    logger.setLevel(getattr(logging, config.level.upper()))
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def request_log(logger: logging.Logger, method: str, path: str, status: int, started: float) -> None:
    logger.info(
        "HTTP 请求完成",
        extra={"method": method, "path": path, "status": status, "latency_ms": round((time.monotonic() - started) * 1000, 2)},
    )
