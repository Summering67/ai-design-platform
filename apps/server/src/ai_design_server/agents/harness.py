from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Any

from .diagnostics import (
    DiagnosticIssue,
    candidate_size,
    collect_schema_issues,
    redacted_snapshot,
    stable_digest,
)
from .errors import AgentError, ContractError, InputRequired
from .model import ModelPort

CandidateValidator = Callable[[dict[str, Any]], None]
CandidateIssueCollector = Callable[[dict[str, Any]], list[DiagnosticIssue]]
MAX_FEEDBACK_LENGTH = 240
LOGGER = logging.getLogger("ai_design_server.agents.harness")


def short_error_summary(error: AgentError) -> str:
    code = error.code.replace("\n", " ")[:64]
    path = error.path.replace("\n", " ")[:96] if error.path else ""
    reason = " ".join(error.message.split())[:120]
    summary = " | ".join(part for part in (code, path, reason) if part)
    return summary[:MAX_FEEDBACK_LENGTH]


def short_issue_summary(issues: Sequence[Mapping[str, Any]]) -> str:
    if not issues:
        return "validation_failed"
    issue = issues[0]
    error = ContractError(
        str(issue.get("code", "validation_failed")),
        str(issue.get("message", "候选产物校验失败")),
        path=str(issue.get("path")) if issue.get("path") else None,
    )
    return short_error_summary(error)


async def run_structured_harness(
    model: ModelPort,
    purpose: str,
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    validate_candidate: CandidateValidator,
    *,
    max_attempts: int = 2,
    stage: str | None = None,
    run_id: str | None = None,
    collect_candidate_issues: CandidateIssueCollector | None = None,
) -> dict[str, Any]:
    if max_attempts < 1:
        raise ValueError("Harness 尝试次数必须大于零")
    feedback = ""
    last_error: AgentError | None = None
    for attempt in range(max_attempts):
        started = time.monotonic()
        candidate: dict[str, Any] | None = None
        issues: list[DiagnosticIssue] = []
        request = dict(payload)
        if feedback:
            request["validationFeedback"] = feedback
        try:
            candidate = await model.structured(purpose, request, schema)
            issues = collect_schema_issues(schema, candidate)
            if collect_candidate_issues is not None:
                issues.extend(collect_candidate_issues(deepcopy(candidate)))
            if issues:
                if all(issue["keyword"] == "semantic" for issue in issues):
                    issue = issues[0]
                    raise ContractError(
                        issue["code"], issue.get("message", "候选语义校验失败"), path=issue["path"]
                    )
                raise ContractError(
                    "invalid_contract", "候选不符合 JSON Schema", path=issues[0]["path"]
                )
            validate_candidate(deepcopy(candidate))
            _log_trace(
                model,
                purpose,
                payload,
                schema,
                stage=stage,
                run_id=run_id,
                attempt=attempt + 1,
                status="success",
                failure_phase="",
                duration_ms=(time.monotonic() - started) * 1000,
                candidate=candidate,
                issues=[],
            )
            return candidate
        except InputRequired:
            _log_trace(
                model,
                purpose,
                payload,
                schema,
                stage=stage,
                run_id=run_id,
                attempt=attempt + 1,
                status="input_required",
                failure_phase="user_input",
                duration_ms=(time.monotonic() - started) * 1000,
                candidate=candidate,
                issues=[],
            )
            raise
        except AgentError as error:
            last_error = error
            if not issues:
                issues = [
                    {
                        "code": error.code,
                        "path": error.path or "/",
                        "keyword": "semantic",
                        "expected": "",
                        "actual": "",
                    }
                ]
            _log_trace(
                model,
                purpose,
                payload,
                schema,
                stage=stage,
                run_id=run_id,
                attempt=attempt + 1,
                status=(
                    "retrying"
                    if (isinstance(error, ContractError) or error.retryable)
                    and attempt + 1 < max_attempts
                    else "failed"
                ),
                failure_phase=_failure_phase(error, issues),
                duration_ms=(time.monotonic() - started) * 1000,
                candidate=candidate,
                issues=issues,
            )
            if (
                not isinstance(error, ContractError) and not error.retryable
            ) or attempt + 1 >= max_attempts:
                error.retryable = False
                raise
            feedback = short_issue_summary(issues)
    if last_error is not None:
        raise last_error
    raise AgentError("harness_exhausted", "Harness 校验循环已耗尽")


def _failure_phase(error: AgentError, issues: list[DiagnosticIssue]) -> str:
    if any(issue["keyword"] != "semantic" for issue in issues):
        return "json_schema"
    if error.code in {"invalid_model_json", "model_empty_response"}:
        return "model_response"
    if error.code.startswith("model_") or error.code == "agent_timeout":
        return "model_transport"
    if error.code == "invalid_model_response":
        return "response_envelope"
    if error.code.startswith(("ui_", "layout_", "invalid_generation_contract")):
        return "semantic_validation"
    return "agent_validation"


def _log_trace(
    model: ModelPort,
    purpose: str,
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    stage: str | None,
    run_id: str | None,
    attempt: int,
    status: str,
    failure_phase: str,
    duration_ms: float,
    candidate: dict[str, Any] | None,
    issues: list[DiagnosticIssue],
) -> None:
    contract = payload.get("generationContract", payload.get("contract", {}))
    extra = {
        "event_type": "agent_harness_attempt",
        "run_id": run_id or "",
        "stage": stage or str(schema.get("title", "agent")),
        "attempt": attempt,
        "status": status,
        "failure_phase": failure_phase,
        "duration_ms": round(duration_ms, 2),
        "output_bytes": candidate_size(candidate) if candidate is not None else 0,
        "issue_count": len(issues),
        "first_issue_path": issues[0]["path"] if issues else "",
        "model": str(getattr(model, "model_name", type(model).__name__)),
        "prompt_digest": stable_digest({"purpose": purpose, "payload": payload}),
        "schema_digest": stable_digest(schema),
        "contract_digest": stable_digest(contract),
        "issues": json.dumps(issues, ensure_ascii=False, separators=(",", ":")),
    }
    log = LOGGER.info if status in {"success", "input_required"} else LOGGER.warning
    log("Agent Harness 尝试完成", extra=extra)
    if candidate is not None and status != "success" and LOGGER.isEnabledFor(logging.DEBUG):
        LOGGER.debug(
            "Agent Harness 失败候选快照",
            extra={
                "event_type": "agent_harness_snapshot",
                "run_id": run_id or "",
                "stage": extra["stage"],
                "attempt": attempt,
                "candidate_snapshot": redacted_snapshot(candidate),
            },
        )
