from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

from jsonschema import Draft202012Validator, RefResolver

from ..errors import AgentError

ROOT = Path(__file__).resolve().parents[6]
SCHEMA_ROOT = ROOT / "packages/design-contract/schema/v2"

CODEGEN_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["viewportIds", "componentMappings", "layoutStrategy", "styleStrategy", "assets", "risks"],
    "properties": {
        "viewportIds": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "string", "minLength": 1}},
        "componentMappings": {"type": "array", "maxItems": 500, "items": {"type": "object", "additionalProperties": False, "required": ["nodeId", "renderAs"], "properties": {"nodeId": {"type": "string", "minLength": 1}, "renderAs": {"type": "string", "minLength": 1}, "reason": {"type": "string", "maxLength": 300}}}},
        "layoutStrategy": {"type": "string", "minLength": 1, "maxLength": 2000},
        "styleStrategy": {"type": "string", "minLength": 1, "maxLength": 2000},
        "antdImports": {"type": "array", "maxItems": 100, "items": {"type": "string", "minLength": 1}},
        "assets": {"type": "array", "maxItems": 500, "items": {"type": "object", "additionalProperties": False, "required": ["assetId", "usage"], "properties": {"assetId": {"type": "string", "minLength": 1}, "usage": {"type": "string", "minLength": 1, "maxLength": 300}}}},
        "risks": {"type": "array", "maxItems": 50, "items": {"type": "string", "maxLength": 300}},
        "summary": {"type": "string", "maxLength": 1000}
    }
}

_COMPONENT_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_FILE_BASE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_FORBIDDEN_IMPORT = re.compile(r"(?:from|import)\s+[^;\n]*(?:ai_design_server|packages/|\.agent-outputs)")
_DYNAMIC_CODE = re.compile(r"\b(?:eval|new\s+Function|dangerouslySetInnerHTML)\b")


class CanvasImage(TypedDict):
    viewportId: str
    width: int
    height: int
    mimeType: str
    image: dict[str, str]


class CodegenPlan(TypedDict):
    viewportIds: list[str]
    componentMappings: list[dict[str, str]]
    layoutStrategy: str
    styleStrategy: str
    assets: list[dict[str, str]]
    risks: list[str]
    antdImports: NotRequired[list[str]]
    summary: NotRequired[str]


@dataclass(frozen=True, slots=True)
class CodegenContext:
    document: dict[str, Any]
    canvas_images: tuple[CanvasImage, ...]
    component_name: str
    file_base_name: str
    document_digest: str
    input_digest: str


def _read_schema(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8")))


def _error(message: str, *, path: str | None = None) -> AgentError:
    return AgentError("codegen_input_invalid", message, path=path)


def _validate_schema(value: object, name: str) -> None:
    schema = _read_schema(name)
    store = {schema["$id"]: schema}
    if name == "codegen-request.schema.json":
        document_schema = _read_schema("design-document.schema.json")
        store[document_schema["$id"]] = document_schema
    validator = Draft202012Validator(
        schema,
        resolver=RefResolver.from_schema(schema, store=store),
    )
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    if errors:
        first = errors[0]
        path = "/" + "/".join(str(item) for item in first.absolute_path)
        raise _error("Codegen 输入契约无效", path=path or "/")


def _document_semantics(document: dict[str, Any]) -> None:
    resolved = document.get("resolvedLayouts", {})
    assets = document.get("assets", {})
    components = document.get("designSystem", {}).get("components", {})
    seen: set[str] = set()

    def visit(node: object, path: str) -> None:
        if not isinstance(node, dict):
            raise _error("DesignDocument 节点无效", path=path)
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id or node_id in seen:
            raise _error("DesignDocument 节点 ID 无效", path=f"{path}/id")
        seen.add(node_id)
        if node.get("kind") == "image" and node.get("assetId") not in assets:
            raise _error("图片资产引用无效", path=f"{path}/assetId")
        if node.get("kind") == "component":
            tag = node.get("tag")
            if not isinstance(tag, str) or tag not in components:
                raise _error("组件未在设计系统中注册", path=f"{path}/tag")
        children = node.get("children")
        if not isinstance(children, list):
            raise _error("节点 children 无效", path=f"{path}/children")
        for index, child in enumerate(children):
            visit(child, f"{path}/children/{index}")

    visit(document.get("root"), "/root")
    if not isinstance(resolved, dict):
        raise _error("resolvedLayouts 无效", path="/resolvedLayouts")


def _validate_images(document: dict[str, Any], images: list[CanvasImage]) -> None:
    layouts = document.get("resolvedLayouts", {})
    seen: set[str] = set()
    for index, image in enumerate(images):
        path = f"/canvasImages/{index}"
        viewport_id = image["viewportId"]
        if viewport_id in seen:
            raise _error("viewport 图片不可重复", path=f"{path}/viewportId")
        seen.add(viewport_id)
        viewport = layouts.get(viewport_id)
        if not isinstance(viewport, dict):
            raise _error("viewport 不存在于 DesignDocument", path=f"{path}/viewportId")
        expected = viewport.get("viewport", {})
        if image["width"] != expected.get("width") or image["height"] != expected.get("height"):
            raise _error("viewport 图片尺寸与 DesignDocument 不一致", path=path)
        source = image["image"]
        if source["kind"] == "base64":
            try:
                base64.b64decode(source["data"], validate=True)
            except ValueError as error:
                raise _error("画布图片编码无效", path=f"{path}/image/data") from error


def _name_options(document: dict[str, Any], options: Mapping[str, Any] | None) -> tuple[str, str]:
    options = options or {}
    component_name = options.get("componentName") or _pascal_case(str(document.get("name") or document.get("id")))
    file_base_name = options.get("fileBaseName") or component_name
    if not isinstance(component_name, str) or not _COMPONENT_NAME.fullmatch(component_name):
        raise _error("组件名称无效", path="/options/componentName")
    if not isinstance(file_base_name, str) or not _FILE_BASE_NAME.fullmatch(file_base_name):
        raise _error("文件名无效", path="/options/fileBaseName")
    return component_name, file_base_name


def _pascal_case(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", value)
    candidate = "".join(part[:1].upper() + part[1:] for part in parts)
    return candidate if candidate and candidate[0].isalpha() else f"Design{candidate}"


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_codegen_request(request: Mapping[str, Any]) -> CodegenContext:
    value = cast(dict[str, Any], dict(request))
    try:
        _validate_schema(value, "codegen-request.schema.json")
        document = cast(dict[str, Any], value["document"])
        _document_semantics(document)
        images = cast(list[CanvasImage], value["canvasImages"])
        _validate_images(document, images)
        component_name, file_base_name = _name_options(document, value.get("options"))
        document_copy = json.loads(json.dumps(document, ensure_ascii=False))
        image_copy = tuple(cast(CanvasImage, json.loads(json.dumps(image, ensure_ascii=False))) for image in images)
        return CodegenContext(
            document=document_copy,
            canvas_images=image_copy,
            component_name=component_name,
            file_base_name=file_base_name,
            document_digest=_digest(document_copy),
            input_digest=_digest({"document": document_copy, "canvasImages": image_copy}),
        )
    except AgentError:
        raise
    except (TypeError, KeyError, OSError, json.JSONDecodeError) as error:
        raise _error("Codegen 输入无效") from error


def validate_plan(value: object, context: CodegenContext) -> CodegenPlan:
    errors = list(Draft202012Validator(CODEGEN_PLAN_SCHEMA).iter_errors(value))
    if errors or not isinstance(value, dict):
        raise AgentError("codegen_plan_invalid", "CodePlan 格式无效")
    plan = cast(CodegenPlan, value)
    if set(plan["viewportIds"]) != {image["viewportId"] for image in context.canvas_images}:
        raise AgentError("codegen_plan_invalid", "CodePlan viewport 范围无效")
    return plan


def validate_codegen_result(value: Mapping[str, Any], context: CodegenContext) -> dict[str, Any]:
    _validate_schema(dict(value), "codegen-result.schema.json")
    result = dict(value)
    files = result.get("files")
    if not isinstance(files, list) or len(files) != 2:
        raise AgentError("codegen_generation_failed", "Codegen 必须返回两个文件")
    expected = {f"{context.file_base_name}.tsx": "text/tsx", f"{context.file_base_name}.css": "text/css"}
    if {file.get("path") for file in files if isinstance(file, dict)} != set(expected):
        raise AgentError("codegen_generation_failed", "Codegen 文件名不符合输出契约")
    for file in files:
        if not isinstance(file, dict):
            raise AgentError("codegen_generation_failed", "Codegen 文件格式无效")
        path = file.get("path")
        if not isinstance(path, str) or expected.get(path) != file.get("mediaType"):
            raise AgentError("codegen_generation_failed", "Codegen 文件媒体类型无效")
        content = file.get("content")
        if not isinstance(content, str) or _FORBIDDEN_IMPORT.search(content) or _DYNAMIC_CODE.search(content):
            raise AgentError("codegen_generation_failed", "Codegen 文件包含禁止内容")
        if path == f"{context.file_base_name}.tsx" and (
            "export default" not in content or f"./{context.file_base_name}.css" not in content
        ):
            raise AgentError("codegen_generation_failed", "TSX 缺少默认导出或 CSS 相对导入")
        if path == f"{context.file_base_name}.css" and "@import" in content:
            raise AgentError("codegen_generation_failed", "CSS 不允许远程或外部导入")
    return result
