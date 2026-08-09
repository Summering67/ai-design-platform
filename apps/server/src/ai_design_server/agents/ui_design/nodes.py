from __future__ import annotations

from typing import Any, TypedDict

from ..contracts import load_schema, validate_initial_ui_document
from ..harness import run_structured_harness
from ..model import ModelPort
from .prompts import SYSTEM_PROMPT


class UIDesignState(TypedDict, total=False):
    prd: dict[str, Any]
    contract: dict[str, Any]
    candidate: dict[str, Any]
    resolved_user_inputs: list[dict[str, Any]]
    run_id: str


async def generate(state: UIDesignState, *, model: ModelPort) -> UIDesignState:
    candidate = await run_structured_harness(
        model,
        SYSTEM_PROMPT,
        {
            "prd": state["prd"],
            "resolvedUserInputs": state.get("resolved_user_inputs", []),
            "generationContract": state["contract"],
            "instruction": "生成初始 UI JSON",
        },
        load_schema("initial-ui-document.schema.json"),
        lambda value: validate_initial_ui_document(value, state["contract"]),
        stage="ui_design",
        run_id=state.get("run_id"),
    )
    return {"candidate": candidate}
