from __future__ import annotations

from typing import Any, TypedDict

from ..contracts import load_schema, validate_prd
from ..errors import AgentError, ContractError, InputQuestion, InputRequired
from ..model import ModelPort
from .prompts import SYSTEM_PROMPT


class RequirementState(TypedDict, total=False):
    input: str
    candidate: dict[str, Any]
    error: str
    attempt: int
    resolved_user_inputs: list[dict[str, Any]]


async def parse(state: RequirementState, *, model: ModelPort) -> RequirementState:
    raw = state.get("input", "").strip()
    if not raw:
        raise AgentError("invalid_requirement", "产品需求不能为空")
    candidate = await model.structured(
        SYSTEM_PROMPT,
        {"requirement": raw, "resolvedUserInputs": state.get("resolved_user_inputs", []), "instruction": "不要遗漏明确约束；关键冲突放入 blockingIssues"},
        load_schema("standardized-prd.schema.json"),
    )
    try:
        validate_prd(candidate, allow_blocking=True)
    except ContractError as error:
        if state.get("attempt", 1) > 1:
            raise
        return {"input": raw, "attempt": 2, "error": error.code}
    if candidate["blockingIssues"]:
        raise InputRequired([InputQuestion(item["id"], item["text"]) for item in candidate["blockingIssues"]])
    return {"candidate": candidate, "attempt": state.get("attempt", 1)}


async def repair(state: RequirementState, *, model: ModelPort) -> RequirementState:
    if not state.get("error"):
        return state
    candidate = await model.structured(
        SYSTEM_PROMPT,
        {"requirement": state["input"], "resolvedUserInputs": state.get("resolved_user_inputs", []), "error": state["error"], "instruction": "仅修复 Schema 或引用错误"},
        load_schema("standardized-prd.schema.json"),
    )
    validate_prd(candidate, allow_blocking=True)
    if candidate["blockingIssues"]:
        raise InputRequired([InputQuestion(item["id"], item["text"]) for item in candidate["blockingIssues"]])
    return {"candidate": candidate, "attempt": 2}
