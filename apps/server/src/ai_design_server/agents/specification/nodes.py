from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict

from ..contracts import load_schema, validate_report, validate_tree
from ..errors import ContractError
from ..model import ModelPort
from .prompts import SYSTEM_PROMPT


class SpecificationState(TypedDict, total=False):
    document: dict[str, Any]
    prd: dict[str, Any]
    contract: dict[str, Any]
    report: dict[str, Any]
    corrected: dict[str, Any]
    resolved_user_inputs: list[dict[str, Any]]


def _issue(error: ContractError, *, status: str = "unresolved") -> dict[str, Any]:
    repairable = error.code != "contract_unavailable"
    return {
        "code": error.code,
        "severity": "error",
        "path": "/",
        "message": error.message,
        "repairable": repairable,
        "status": status,
    }


def _report(issues: list[dict[str, Any]]) -> dict[str, Any]:
    errors = sum(issue["severity"] == "error" for issue in issues)
    warnings = sum(issue["severity"] == "warning" for issue in issues)
    fixed = sum(issue["status"] == "fixed" for issue in issues)
    unresolved = sum(issue["status"] == "unresolved" for issue in issues)
    return {
        "version": "2.0.0",
        "passed": unresolved == 0 and errors == 0,
        "issues": issues,
        "summary": {
            "total": len(issues),
            "errors": errors,
            "warnings": warnings,
            "fixed": fixed,
            "unresolved": unresolved,
        },
    }


def check(state: SpecificationState, *, contract: dict[str, Any]) -> SpecificationState:
    try:
        validate_tree(state["document"], contract)
    except ContractError as error:
        report = _report([_issue(error)])
        validate_report(report)
        return {"report": report, "corrected": deepcopy(state["document"])}
    report = _report([])
    validate_report(report)
    return {"report": report, "corrected": deepcopy(state["document"])}


async def repair(
    state: SpecificationState, *, model: ModelPort, contract: dict[str, Any]
) -> SpecificationState:
    report = state["report"]
    if report["passed"]:
        return state
    if any(not issue["repairable"] for issue in report["issues"]):
        return state
    candidate = await model.structured(
        SYSTEM_PROMPT,
        {
            "prd": state["prd"],
            "resolvedUserInputs": state.get("resolved_user_inputs", []),
            "document": state["document"],
            "report": report,
            "generationContract": contract,
            "instruction": "将初始化 UI JSON 规范化为合法 v2 DesignDocument",
        },
        load_schema("design-document.schema.json"),
    )
    validate_tree(candidate, contract)
    original_ids = _ids(state["document"])
    if not original_ids.issubset(_ids(candidate)):
        raise ContractError("immutable_semantics_changed", "修正删除了已有稳定节点身份")
    fixed = [{**issue, "status": "fixed"} for issue in report["issues"]]
    next_report = _report(fixed)
    validate_report(next_report)
    return {"report": next_report, "corrected": candidate}


def _ids(document: dict[str, Any]) -> set[str]:
    result: set[str] = set()

    def visit(node: dict[str, Any]) -> None:
        if isinstance(node.get("id"), str):
            result.add(node["id"])
        for child in node.get("children", []):
            visit(child)

    root = document.get("root")
    if isinstance(root, dict):
        visit(root)
    return result
