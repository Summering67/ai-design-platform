from __future__ import annotations

from typing import Any, TypedDict

from ..contracts import load_schema, validate_prd
from ..errors import AgentError, ContractError
from ..model import ModelPort
from .prompts import SYSTEM_PROMPT


class RequirementState(TypedDict, total=False):
    input: str
    candidate: dict[str, Any]
    error: str
    attempt: int


async def parse(state: RequirementState, *, model: ModelPort) -> RequirementState:
    raw = state.get("input", "").strip()
    if not raw:
        raise AgentError("invalid_requirement", "产品需求不能为空")
    candidate = await model.structured(
        SYSTEM_PROMPT,
        {"requirement": raw, "instruction": "不要遗漏明确约束；关键冲突放入 blockingIssues"},
        load_schema("standardized-prd.schema.json"),
    )
    try:
        validate_prd(candidate)
    except ContractError as error:
        if state.get("attempt", 1) > 1:
            raise
        return {"input": raw, "attempt": 2, "error": error.code}
    return {"candidate": candidate, "attempt": state.get("attempt", 1)}


async def repair(state: RequirementState, *, model: ModelPort) -> RequirementState:
    if not state.get("error"):
        return state
    candidate = await model.structured(
        SYSTEM_PROMPT,
        {"requirement": state["input"], "error": state["error"], "instruction": "仅修复 Schema 或引用错误"},
        load_schema("standardized-prd.schema.json"),
    )
    validate_prd(candidate)
    return {"candidate": candidate, "attempt": 2}
