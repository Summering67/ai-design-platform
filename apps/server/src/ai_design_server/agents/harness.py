from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from .diagnostics import (
    DiagnosticIssue,
    candidate_size,
    collect_schema_issues,
    redacted_snapshot,
    redacted_value,
    stable_digest,
)
from .errors import AgentError, ContractError, InputRequired
from .model import ModelPort

CandidateValidator = Callable[[dict[str, Any]], None]
CandidateIssueCollector = Callable[[dict[str, Any]], list[DiagnosticIssue]]
MAX_FEEDBACK_LENGTH = 240
LOGGER = logging.getLogger("ai_design_server.agents.harness")
FAILED_CANDIDATE_ROOT = Path(__file__).resolve().parents[3] / ".agent-outputs" / "by-run"


async def _save_failed_candidate(
    candidate: dict[str, Any] | None,
    run_id: str | None,
    stage: str | None,
    attempt: int,
) -> None:
    if candidate is None or not run_id:
        return
    safe_run_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", run_id).strip(".-")[:80]
    safe_stage = re.sub(r"[^a-zA-Z0-9._-]+", "-", stage or "agent").strip(".-")[:80]
    if not safe_run_id or not safe_stage:
        return
    target = FAILED_CANDIDATE_ROOT / safe_run_id / f"{safe_stage}-attempt-{attempt:02d}-failed.json"
    serialized = json.dumps(redacted_value(candidate), ensure_ascii=False, indent=2, sort_keys=True)

    def write() -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(f"{serialized}\n", encoding="utf-8")
        temporary.replace(target)

    try:
        await asyncio.to_thread(write)
    except OSError:
        LOGGER.warning(
            "保存 Agent Harness 失败候选失败",
            extra={"run_id": run_id, "stage": stage or "", "attempt": attempt},
        )


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
    trace_contract: Mapping[str, Any] | None = None,
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
        instruction = request.pop("instruction", None)
        if feedback:
            request["validationFeedback"] = feedback
        if instruction is not None:
            request["instruction"] = instruction
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
                trace_contract=trace_contract,
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
                trace_contract=trace_contract,
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
                trace_contract=trace_contract,
            )
            await _save_failed_candidate(candidate, run_id, stage, attempt + 1)
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
    trace_contract: Mapping[str, Any] | None,
) -> None:
    contract = trace_contract or payload.get("generationContract", payload.get("contract", {}))
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
