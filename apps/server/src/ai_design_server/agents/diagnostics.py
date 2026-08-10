from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any, NotRequired, TypedDict

from jsonschema import Draft202012Validator

_SENSITIVE_KEYS = frozenset(
    {"authorization", "body", "cookie", "dsn", "password", "api_key", "token"}
)
MAX_ISSUES = 20
MAX_SUMMARY_LENGTH = 160
MAX_SNAPSHOT_LENGTH = 2048


class DiagnosticIssue(TypedDict):
    code: str
    path: str
    keyword: str
    expected: str
    actual: str
    message: NotRequired[str]


def stable_digest(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()}"


def _pointer(path: Iterable[object]) -> str:
    parts = [str(item).replace("~", "~0").replace("/", "~1") for item in path]
    return "/" + "/".join(parts) if parts else "/"


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[redacted]" if str(key).lower() in _SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def redacted_snapshot(value: Any, *, max_length: int = MAX_SNAPSHOT_LENGTH) -> str:
    serialized = json.dumps(
        _redact(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str
    )
    if len(serialized) <= max_length:
        return serialized
    return f"{serialized[: max_length - 15]}...[truncated]"


def _summary(value: Any) -> str:
    return redacted_snapshot(value, max_length=MAX_SUMMARY_LENGTH)


def collect_schema_issues(
    schema: Mapping[str, Any], candidate: Any, *, limit: int = MAX_ISSUES
) -> list[DiagnosticIssue]:
    if limit < 1:
        return []
    errors = sorted(
        Draft202012Validator(dict(schema)).iter_errors(candidate),
        key=lambda error: (_pointer(error.absolute_path), str(error.validator)),
    )
    return [
        {
            "code": f"schema_{error.validator or 'validation'}",
            "path": _pointer(error.absolute_path),
            "keyword": str(error.validator or "validation"),
            "expected": _summary(error.validator_value),
            "actual": _summary(error.instance),
        }
        for error in errors[:limit]
    ]


def candidate_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str).encode())
