from __future__ import annotations

from typing import Any, Literal, TypedDict

from .contracts import CanvasImage, CodegenPlan

CodegenPhase = Literal[
    "input",
    "planning",
    "generating",
    "checking",
    "reviewing",
    "repairing",
    "completed",
    "failed",
]


class CodegenDiagnostic(TypedDict, total=False):
    tool: str
    rule: str
    file: str
    line: int
    column: int
    message: str
    severity: Literal["error", "warning", "info"]


class CodegenState(TypedDict, total=False):
    run_id: str
    phase: CodegenPhase
    document: dict[str, Any]
    canvas_images: tuple[CanvasImage, ...]
    document_digest: str
    input_digest: str
    component_name: str
    file_base_name: str
    plan: CodegenPlan
    plan_summary: str
    candidate: dict[str, str]
    diagnostics: list[CodegenDiagnostic]
    visual_diagnostics: list[CodegenDiagnostic]
    repair_attempts: int
    tool_calls: int
    checks: list[dict[str, Any]]
    risks: list[str]
