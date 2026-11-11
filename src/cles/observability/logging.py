"""Structured JSON logging with a per-request id, and a redaction helper."""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Literal

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

CaptureMode = Literal["none", "redacted", "full"]


def new_request_id() -> str:
    """Start a new request scope and return its id."""
    rid = uuid.uuid4().hex
    request_id_var.set(rid)
    return rid


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "message": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Send JSON logs to stderr (stdout is reserved for a stage's JSON summary)."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def redact(text: str, mode: CaptureMode) -> str:
    """Apply the telemetry capture policy to case text before it is logged or exported."""
    if mode == "full":
        return text
    if mode == "none":
        return ""
    return f"[redacted: {len(text)} chars]"
