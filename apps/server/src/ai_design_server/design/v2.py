from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..errors import InvalidRequestError

MAX_DOCUMENT_BYTES = 1 << 20


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[5] / "packages" / "design-contract" / "schema" / "v2" / "design-document.schema.json"


def prepare_v2(payload: bytes, allowed: bool) -> dict[str, Any]:
    if not allowed:
        raise PermissionError("无权修改设计文档")
    if not payload or len(payload) > MAX_DOCUMENT_BYTES:
        raise InvalidRequestError("设计文档无效")
    try:
        document = json.loads(payload)
        if not isinstance(document, dict) or document.get("version") != "2.0.0":
            raise InvalidRequestError("设计文档版本不受支持")
        schema = json.loads(_schema_path().read_text(encoding="utf-8"))
        error = next(Draft202012Validator(schema).iter_errors(document), None)
        if error:
            raise InvalidRequestError("设计文档无效") from error
        _validate_semantics(document)
        return {"original_version": "2.0.0", "document": document, "warnings": []}
    except InvalidRequestError:
        raise
    except (OSError, json.JSONDecodeError, TypeError, KeyError) as error:
        raise InvalidRequestError("设计文档无效") from error


def _validate_semantics(document: dict[str, Any]) -> None:
    assets = document.get("assets", {})
    design_system = document.get("designSystem", {})
    components = design_system.get("components", {})
    allowed_tags = set(design_system.get("allowedTags", []))
    ids: set[str] = set()

    def visit(node: dict[str, Any], path: str) -> None:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id or node_id in ids:
            raise InvalidRequestError("设计文档无效")
        ids.add(node_id)
        if node.get("kind") == "image" and node.get("assetId") not in assets:
            raise InvalidRequestError("设计文档无效")
        if node.get("kind") == "component":
            tag = node.get("tag")
            registered = tag in components or any(isinstance(value, dict) and value.get("id") == tag for value in components.values())
            if not registered or (allowed_tags and tag not in allowed_tags):
                raise InvalidRequestError("设计文档无效")
        for index, child in enumerate(node.get("children", [])):
            if not isinstance(child, dict):
                raise InvalidRequestError("设计文档无效")
            visit(child, f"{path}/children/{index}")

    root = document.get("root")
    if not isinstance(root, dict):
        raise InvalidRequestError("设计文档无效")
    visit(root, "/root")
