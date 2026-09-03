from __future__ import annotations

import base64
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from ...config import AgentConfig
from ..errors import AgentError
from ..model import MultimodalModelPort
from .contracts import (
    CODEGEN_PLAN_SCHEMA,
    CodegenContext,
    CodegenPlan,
    validate_codegen_request,
    validate_codegen_result,
    validate_plan,
)
from .defaults import write_codegen_files
from .prompts import (
    CODEGEN_SYSTEM_PROMPT,
    GENERATE_INSTRUCTION,
    PLAN_INSTRUCTION,
    REPAIR_INSTRUCTION,
    VISUAL_REVIEW_INSTRUCTION,
)
from .state import CodegenDiagnostic, CodegenState
from .tools import CandidateWorkspace, PreviewRenderer, StaticVerifier, bounded_diagnostics

EventSink = Callable[[dict[str, Any]], Awaitable[None]]

_FILES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["files", "summary"],
    "properties": {
        "files": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "content"],
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "content": {"type": "string", "minLength": 1, "maxLength": 1_000_000},
                },
            },
        },
        "summary": {"type": "string", "maxLength": 1000},
    },
}

_VISUAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["issues"],
    "properties": {
        "issues": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["category", "severity", "confidence", "message"],
                "properties": {
                    "category": {"enum": ["structure", "layout", "style", "content"]},
                    "severity": {"enum": ["blocking", "warning", "info"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "message": {"type": "string", "minLength": 1, "maxLength": 400},
                },
            },
        }
    },
}


async def run_codegen(
    request: Mapping[str, Any],
    model: MultimodalModelPort,
    config: AgentConfig,
    *,
    verifier: StaticVerifier,
    renderer: PreviewRenderer,
    emit: EventSink | None = None,
    output_directory: Path | None = None,
) -> dict[str, Any]:
    context = validate_codegen_request(request)
    if any(image["width"] * image["height"] > config.codegen_max_image_pixels for image in context.canvas_images):
        raise AgentError("codegen_limit_exceeded", "画布图片像素超出限制")
    if not getattr(model, "supports_vision", False) or not callable(
        getattr(model, "structured_multimodal", None)
    ):
        raise AgentError("codegen_model_unavailable", "Codegen 需要支持视觉输入的模型")
    run_id = str(uuid4())
    state: CodegenState = {
        "run_id": run_id,
        "phase": "input",
        "document": context.document,
        "canvas_images": context.canvas_images,
        "document_digest": context.document_digest,
        "input_digest": context.input_digest,
        "component_name": context.component_name,
        "file_base_name": context.file_base_name,
        "repair_attempts": 0,
        "tool_calls": 0,
        "checks": [],
        "risks": [],
    }
    await _emit(emit, run_id, "input", {"documentDigest": context.document_digest})
    plan = await _plan(context, model, config, emit=emit, run_id=run_id)
    state["phase"] = "generating"
    state["plan"] = cast(CodegenPlan, plan)
    state["risks"] = plan.get("risks", [])
    await _emit(emit, run_id, "generating", {})
    async with CandidateWorkspace(
        context.file_base_name, max_file_bytes=config.codegen_max_file_bytes
    ) as workspace:
        candidate, summary = await _generate(context, plan, model, emit=emit, run_id=run_id)
        state["candidate"] = candidate
        await workspace.write_candidate(candidate)
        repair_attempts = 0
        tool_calls = 1
        checks: list[dict[str, Any]] = []
        diagnostics: list[CodegenDiagnostic] = []
        while True:
            if tool_calls >= config.codegen_max_tool_calls:
                raise AgentError("codegen_limit_exceeded", "Codegen 工具调用超出限制")
            tool_calls += 1
            await _emit(emit, run_id, "checking", {"attempt": repair_attempts + 1})
            diagnostics = bounded_diagnostics(await verifier.verify(workspace))
            state["diagnostics"] = diagnostics
            state["phase"] = "checking"
            checks.append({"name": "format", "status": "passed" if not diagnostics else "failed", "attempts": repair_attempts + 1})
            state["checks"] = checks
            if not diagnostics:
                break
            if repair_attempts >= config.codegen_repair_attempts:
                raise AgentError("codegen_verification_failed", "生成代码未通过静态检查")
            repair_attempts += 1
            await _emit(emit, run_id, "repairing", {"attempt": repair_attempts, "reason": "static"})
            candidate, summary = await _repair(
                context,
                plan,
                await workspace.read_candidate(),
                diagnostics,
                model,
                emit=emit,
                run_id=run_id,
            )
            await workspace.write_candidate(candidate)
            state["candidate"] = candidate
            tool_calls += 1
            state["repair_attempts"] = repair_attempts
        await _emit(emit, run_id, "reviewing", {})
        visual_issues = await _review_visuals(context, workspace, model, renderer, emit=emit, run_id=run_id)
        state["phase"] = "reviewing"
        state["visual_diagnostics"] = cast(list[CodegenDiagnostic], visual_issues)
        visual_repairs = 0
        while visual_issues:
            blocking = [issue for issue in visual_issues if issue.get("severity") == "blocking" and float(issue.get("confidence", 0)) >= 0.8]
            if not blocking:
                break
            if visual_repairs >= config.codegen_repair_attempts:
                raise AgentError("codegen_visual_mismatch", "生成预览未通过视觉检查")
            visual_repairs += 1
            await _emit(emit, run_id, "repairing", {"attempt": visual_repairs, "reason": "visual"})
            candidate, summary = await _repair(
                context,
                plan,
                await workspace.read_candidate(),
                bounded_diagnostics([dict(issue) for issue in visual_issues]),
                model,
                emit=emit,
                run_id=run_id,
            )
            await workspace.write_candidate(candidate)
            state["candidate"] = candidate
            tool_calls += 1
            state["repair_attempts"] = repair_attempts + visual_repairs
            if tool_calls >= config.codegen_max_tool_calls:
                raise AgentError("codegen_limit_exceeded", "Codegen 工具调用超出限制")
            tool_calls += 1
            diagnostics = bounded_diagnostics(await verifier.verify(workspace))
            if diagnostics:
                raise AgentError("codegen_verification_failed", "视觉修复后静态检查失败")
            visual_issues = await _review_visuals(context, workspace, model, renderer, emit=emit, run_id=run_id)
        files = await workspace.read_candidate()
    result = {
        "version": "2.0.0",
        "documentId": context.document["id"],
        "componentName": context.component_name,
        "fileBaseName": context.file_base_name,
        "files": [
            {"path": name, "mediaType": "text/tsx" if name.endswith(".tsx") else "text/css", "content": content}
            for name, content in sorted(files.items())
        ],
        "planSummary": summary[:2000],
        "verification": {
            "checks": checks + [{"name": "visual", "status": "passed", "attempts": visual_repairs + 1}],
            "repairAttempts": repair_attempts + visual_repairs,
            "risks": plan.get("risks", [])[:20],
        },
    }
    completed = validate_codegen_result(result, context)
    if output_directory is not None:
        write_codegen_files(completed, output_directory)
    state["phase"] = "completed"
    await _emit(emit, run_id, "completed", {"repairAttempts": completed["verification"]["repairAttempts"]})
    return completed


async def _plan(
    context: CodegenContext,
    model: MultimodalModelPort,
    config: AgentConfig,
    *,
    emit: EventSink | None,
    run_id: str,
) -> dict[str, Any]:
    for attempt in range(config.codegen_plan_attempts):
        await _emit(emit, run_id, "planning", {"attempt": attempt + 1})
        try:
            result = await model.structured_multimodal(
                "多模态 Codegen Agent",
                _parts(context, PLAN_INSTRUCTION),
                CODEGEN_PLAN_SCHEMA,
            )
            return cast(dict[str, Any], validate_plan(result, context))
        except AgentError as error:
            if attempt >= config.codegen_plan_attempts - 1:
                raise AgentError("codegen_plan_invalid", "CodePlan 多次生成失败") from error
    raise AgentError("codegen_plan_invalid", "CodePlan 生成失败")


async def _generate(
    context: CodegenContext,
    plan: Mapping[str, Any],
    model: MultimodalModelPort,
    *,
    emit: EventSink | None,
    run_id: str,
) -> tuple[dict[str, str], str]:
    result = await model.structured_multimodal(
        "多模态 Codegen Agent",
        _parts(context, GENERATE_INSTRUCTION, extra={"codePlan": plan}),
        _FILES_SCHEMA,
    )
    return _candidate_from_model(result, context)


async def _repair(
    context: CodegenContext,
    plan: Mapping[str, Any],
    candidate: Mapping[str, str],
    diagnostics: Sequence[Mapping[str, Any]],
    model: MultimodalModelPort,
    *,
    emit: EventSink | None,
    run_id: str,
) -> tuple[dict[str, str], str]:
    result = await model.structured_multimodal(
        "多模态 Codegen Agent",
        _parts(
            context,
            REPAIR_INSTRUCTION,
            extra={"codePlan": plan, "candidate": candidate, "diagnostics": diagnostics},
        ),
        _FILES_SCHEMA,
    )
    return _candidate_from_model(result, context)


async def _review_visuals(
    context: CodegenContext,
    workspace: CandidateWorkspace,
    model: MultimodalModelPort,
    renderer: PreviewRenderer,
    *,
    emit: EventSink | None,
    run_id: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for image in context.canvas_images:
        preview = await renderer.render(
            workspace, image["viewportId"], image["width"], image["height"]
        )
        parts = _parts(
            context, VISUAL_REVIEW_INSTRUCTION, extra={"viewportId": image["viewportId"]}
        )
        parts.insert(
            -1,
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64.b64encode(preview).decode()}"},
            },
        )
        result = await model.structured_multimodal("视觉审查器", parts, _VISUAL_SCHEMA)
        raw = result.get("issues", [])
        if isinstance(raw, list):
            issues.extend(item for item in raw if isinstance(item, dict))
    return issues


def _candidate_from_model(result: Mapping[str, Any], context: CodegenContext) -> tuple[dict[str, str], str]:
    raw_files = result.get("files")
    if not isinstance(raw_files, list) or len(raw_files) != 2:
        raise AgentError("codegen_generation_failed", "模型没有返回双文件候选")
    files: dict[str, str] = {}
    for raw in raw_files:
        if not isinstance(raw, dict) or not isinstance(raw.get("path"), str) or not isinstance(raw.get("content"), str):
            raise AgentError("codegen_generation_failed", "模型返回的文件格式无效")
        files[raw["path"]] = raw["content"]
    return files, str(result.get("summary", ""))[:2000]


def _parts(
    context: CodegenContext,
    instruction: str,
    *,
    extra: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [
        {"type": "text", "text": CODEGEN_SYSTEM_PROMPT},
        {
            "type": "text",
            "text": json.dumps(
                {
                    "document": context.document,
                    "viewports": [image["viewportId"] for image in context.canvas_images],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        },
    ]
    for image in context.canvas_images:
        source = image["image"]
        url = (
            f"data:{image['mimeType']};base64,{source['data']}"
            if source["kind"] == "base64"
            else f"ref://{source['id']}"
        )
        parts.append({"type": "image_url", "image_url": {"url": url, "detail": "high"}})
    parts.extend(
        {
            "type": "text",
            "text": json.dumps({key: value}, ensure_ascii=False, separators=(",", ":")),
        }
        for key, value in (extra or {}).items()
    )
    parts.append({"type": "text", "text": instruction})
    return parts


async def _emit(emit: EventSink | None, run_id: str, stage: str, payload: dict[str, Any]) -> None:
    if emit is not None:
        await emit({"version": "2.0.0", "event": "stage", "runId": run_id, "stage": stage, "payload": payload})
