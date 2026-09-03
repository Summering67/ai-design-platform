from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from ai_design_server.agents.diagnostics import (
    MAX_SNAPSHOT_LENGTH,
    collect_schema_issues,
    redacted_snapshot,
    stable_digest,
)
from ai_design_server.agents.errors import AgentError, ContractError
from ai_design_server.agents.harness import MAX_FEEDBACK_LENGTH, run_structured_harness
from ai_design_server.agents.supervisor import _catalog


@pytest.mark.asyncio
async def test_harness_retries_with_short_feedback_without_mutating_candidate() -> None:
    first = {"value": "invalid", "nested": {"kept": True}}
    second = {"value": "valid"}
    original = deepcopy(first)
    payloads: list[dict[str, Any]] = []
    candidates = [first, second]

    async def structured(
        _purpose: str, payload: dict[str, Any], _schema: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        payloads.append(payload)
        return candidates.pop(0)

    def validate_candidate(candidate: dict[str, Any]) -> None:
        candidate["nested"] = "validator mutation"
        if candidate["value"] != "valid":
            raise ContractError(
                "invalid_contract",
                "原因" * 200,
                path="/root/children/0",
            )

    result = await run_structured_harness(
        type("Model", (), {"structured": staticmethod(structured)})(),
        "UI Design Agent",
        {"prd": {"id": "prd"}, "instruction": "生成初始 UI"},
        {"type": "object"},
        validate_candidate,
    )

    assert result == second
    assert first == original
    assert "validationFeedback" not in payloads[0]
    assert len(payloads[1]["validationFeedback"]) <= MAX_FEEDBACK_LENGTH
    assert payloads[1]["validationFeedback"].startswith("invalid_contract | /root/children/0")
    assert list(payloads[0]) == ["prd", "instruction"]
    assert list(payloads[1]) == ["prd", "validationFeedback", "instruction"]


@pytest.mark.asyncio
async def test_harness_raises_last_error_after_bounded_attempts() -> None:
    calls = 0

    async def structured(*_: Any, **__: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"invalid": True}

    def reject(_: dict[str, Any]) -> None:
        raise ContractError("invalid_contract", "候选无效", path="/root")

    with pytest.raises(ContractError) as raised:
        await run_structured_harness(
            type("Model", (), {"structured": staticmethod(structured)})(),
            "Auto Layout Agent",
            {},
            {"type": "object"},
            reject,
        )

    assert calls == 2
    assert raised.value.code == "invalid_contract"


@pytest.mark.asyncio
async def test_harness_exhaustion_disables_outer_model_retry() -> None:
    calls = 0

    async def structured(*_: Any, **__: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise AgentError("model_read_timeout", "Agent 模型读取超时", retryable=True)

    with pytest.raises(AgentError) as raised:
        await run_structured_harness(
            type("Model", (), {"structured": staticmethod(structured)})(),
            "UI Design Agent",
            {},
            {"type": "object"},
            lambda _: None,
        )

    assert calls == 2
    assert raised.value.code == "model_read_timeout"
    assert raised.value.retryable is False


def test_harness_is_not_registered_as_agent_task() -> None:
    assert "harness" not in _catalog()
    assert "specification" not in _catalog()


def test_schema_diagnostics_collect_multiple_paths_and_redact_snapshot() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["version", "root"],
        "properties": {
            "version": {"const": "1.0.0"},
            "root": {"type": "object"},
        },
    }
    candidate = {"token": "secret", "noise": "x" * 3000}

    issues = collect_schema_issues(schema, candidate)
    snapshot = redacted_snapshot(candidate)
    redacted = redacted_snapshot({"token": "secret"})

    assert len(issues) >= 3
    assert {issue["keyword"] for issue in issues} >= {"required", "additionalProperties"}
    assert all(issue["path"].startswith("/") for issue in issues)
    assert "secret" not in snapshot
    assert "secret" not in redacted
    assert "[redacted]" in redacted
    assert len(snapshot) <= MAX_SNAPSHOT_LENGTH


@pytest.mark.asyncio
async def test_harness_emits_replayable_trace_with_stable_fingerprints(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    caplog.set_level(logging.DEBUG, logger="ai_design_server.agents.harness")
    monkeypatch.setattr("ai_design_server.agents.harness.FAILED_CANDIDATE_ROOT", tmp_path)
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["version"],
        "properties": {"version": {"const": "1.0.0"}},
    }
    candidates = [{"token": "secret"}, {"version": "1.0.0"}]

    async def structured(*_: Any, **__: Any) -> dict[str, Any]:
        return candidates.pop(0)

    model = type(
        "Model",
        (),
        {"structured": staticmethod(structured), "model_name": "diagnostic-model"},
    )()
    result = await run_structured_harness(
        model,
        "UI Design Agent prompt",
        {"generationContract": {"profile": {"digest": "contract-v1"}}},
        schema,
        lambda _: None,
        stage="ui_design",
        run_id="run-diagnostic",
    )

    traces = [
        record
        for record in caplog.records
        if getattr(record, "event_type", "") == "agent_harness_attempt"
    ]
    snapshot = next(
        record.candidate_snapshot
        for record in caplog.records
        if getattr(record, "event_type", "") == "agent_harness_snapshot"
    )
    replayed = collect_schema_issues(schema, {"token": "secret"})

    assert result == {"version": "1.0.0"}
    assert [record.status for record in traces] == ["retrying", "success"]
    assert traces[0].failure_phase == "json_schema"
    assert traces[0].issue_count == len(replayed)
    assert json.loads(traces[0].issues) == replayed
    assert traces[0].prompt_digest == stable_digest(
        {
            "purpose": "UI Design Agent prompt",
            "payload": {"generationContract": {"profile": {"digest": "contract-v1"}}},
        }
    )
    assert traces[0].schema_digest == traces[1].schema_digest == stable_digest(schema)
    assert traces[0].model == "diagnostic-model"
    assert traces[0].run_id == "run-diagnostic"
    assert "secret" not in snapshot
    failed_candidate = json.loads(
        (tmp_path / "run-diagnostic/ui_design-attempt-01-failed.json").read_text(
            encoding="utf-8"
        )
    )
    assert failed_candidate == {"token": "[redacted]"}


@pytest.mark.asyncio
async def test_harness_does_not_log_candidate_snapshot_at_info_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="ai_design_server.agents.harness")

    async def structured(*_: Any, **__: Any) -> dict[str, Any]:
        return {"token": "secret"}

    with pytest.raises(ContractError):
        await run_structured_harness(
            type("Model", (), {"structured": staticmethod(structured)})(),
            "UI Design Agent prompt",
            {},
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["version"],
                "properties": {"version": {"const": "1.0.0"}},
            },
            lambda _: None,
            max_attempts=1,
            stage="ui_design",
        )

    assert all(
        getattr(record, "event_type", "") != "agent_harness_snapshot" for record in caplog.records
    )
