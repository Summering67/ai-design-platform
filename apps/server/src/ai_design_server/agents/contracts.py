from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .diagnostics import MAX_ISSUES, DiagnosticIssue
from .errors import ContractError


def _root() -> Path:
    current = Path(__file__).resolve()
    for directory in (current, *current.parents):
        if (directory / "pnpm-workspace.yaml").exists():
            return directory
    return current.parents[5]


def schema_path(name: str) -> Path:
    return _root() / "packages" / "design-contract" / "schema" / "v2" / name


def load_schema(name: str) -> dict[str, Any]:
    try:
        value = json.loads(schema_path(name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError("contract_unavailable", "设计契约不可用") from error
    if not isinstance(value, dict):
        raise ContractError("contract_unavailable", "设计契约格式无效")
    style = value.get("$defs", {}).get("style")
    if isinstance(style, dict) and style.get("$ref", "").startswith(
        "design-document.schema.json#/$defs/"
    ):
        design_document = load_schema("design-document.schema.json")
        value["$defs"]["style"] = design_document["$defs"][style["$ref"].rsplit("/", 1)[-1]]
        value["$defs"]["styleValue"] = design_document["$defs"]["styleValue"]
    return value


def load_default_generation_contract() -> dict[str, Any]:
    try:
        value = json.loads(
            Path(__file__).with_name("default-generation-contract.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError("contract_unavailable", "默认生成契约不可用") from error
    if not isinstance(value, dict):
        raise ContractError("contract_unavailable", "默认生成契约格式无效")
    validate_profile_contract(value)
    return value


def validate(name: str, value: Any) -> None:
    schema = load_schema(name)
    error = next(Draft202012Validator(schema).iter_errors(value), None)
    if error is not None:
        path = "/" + "/".join(str(item) for item in error.absolute_path)
        raise ContractError("invalid_contract", "契约校验失败", path=path or "/")


def validate_profile_contract(contract: Mapping[str, Any]) -> None:
    if not isinstance(contract.get("profile"), Mapping):
        raise ContractError("invalid_generation_contract", "生成契约缺少 Profile")
    profile = contract["profile"]
    if any(
        not isinstance(profile.get(key), str) or not profile[key].strip()
        for key in ("id", "version", "digest")
    ):
        raise ContractError("invalid_generation_contract", "生成契约 Profile 引用无效")


def validate_prd(value: Any, *, allow_blocking: bool = False) -> None:
    validate("standardized-prd.schema.json", value)
    pages = value["pages"]
    page_ids = [page["id"] for page in pages]
    if len(page_ids) != len(set(page_ids)):
        raise ContractError("prd_duplicate_id", "PRD 页面 ID 重复")
    page_set = set(page_ids)
    if any(step["pageId"] not in page_set for flow in value["flows"] for step in flow["steps"]):
        raise ContractError("prd_invalid_reference", "PRD 流程引用不存在的页面")
    if value["blockingIssues"] and not allow_blocking:
        raise ContractError("prd_blocking_issue", "PRD 存在未解决的阻断问题")


def validate_report(value: Any) -> None:
    validate("ui-validation-report.schema.json", value)
    issues = value["issues"]
    summary = value["summary"]
    if summary["total"] != len(issues):
        raise ContractError("report_count_mismatch", "校验报告计数不一致")
    if summary["fixed"] + summary["unresolved"] > summary["total"]:
        raise ContractError("report_count_mismatch", "校验报告修复计数不一致")


def validate_event(value: Any) -> None:
    validate("agent-run-event.schema.json", value)


def validate_tree(value: Any, contract: Mapping[str, Any]) -> None:
    schema_path_v2 = (
        _root() / "packages" / "design-contract" / "schema" / "v2" / "design-document.schema.json"
    )
    try:
        schema = json.loads(schema_path_v2.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError("contract_unavailable", "v2 DesignDocument 契约不可用") from error
    schema_error = next(Draft202012Validator(schema).iter_errors(value), None)
    if schema_error is not None:
        raise ContractError("invalid_ui_document", "UI 文档结构无效") from schema_error
    profile = contract.get("profile", {})
    document_profile = value.get("designSystem")
    if not isinstance(document_profile, Mapping) or any(
        document_profile.get(key) != profile.get(key) for key in ("id", "version", "digest")
    ):
        raise ContractError("profile_drift", "UI 文档 Profile 与运行契约不一致")
    kind_mapping = {"frame": "element", "component-instance": "component"}
    allowed_kinds = {
        kind_mapping.get(kind, kind)
        for kind in contract.get("nodeKinds", ["element", "text", "image", "component"])
    }
    components = set(contract.get("components", {})) | set(document_profile.get("components", {}))
    allowed_tags = set(document_profile.get("allowedTags", []))
    icons = set(contract.get("icons", []))
    tokens = set(contract.get("tokens", []))
    seen: set[str] = set()

    def visit(node: Mapping[str, Any], path: str, depth: int) -> int:
        if depth > 32:
            raise ContractError("ui_depth_limit", "UI 文档嵌套过深")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id or node_id in seen:
            raise ContractError("ui_duplicate_id", f"UI 节点 ID 无效: {path}")
        seen.add(node_id)
        kind = node.get("kind")
        if kind not in allowed_kinds:
            raise ContractError("ui_kind_forbidden", f"UI 节点类型未被允许: {path}")
        if (
            kind == "component"
            and node.get("tag") not in components
            and node.get("tag") not in allowed_tags
        ):
            raise ContractError("ui_component_forbidden", f"组件未被允许: {path}")
        if kind == "icon" and node.get("name") not in icons:
            raise ContractError("ui_icon_forbidden", f"图标未被允许: {path}")
        for token in node.get("tokens", []):
            if token not in tokens:
                raise ContractError("ui_token_forbidden", f"Token 未被允许: {path}")
        children = node.get("children", [])
        if kind in {"text", "image"} and children:
            raise ContractError("ui_leaf_children", f"叶子节点不能包含 children: {path}")
        return 1 + sum(
            visit(child, f"{path}/children/{index}", depth + 1)
            for index, child in enumerate(children)
        )

    total = 0
    total = visit(value["root"], "/root", 1)
    if total > 500:
        raise ContractError("ui_node_limit", "UI 节点数量超限")


def collect_initial_ui_document_issues(
    value: Any, contract: Mapping[str, Any], *, limit: int = MAX_ISSUES
) -> list[DiagnosticIssue]:
    if limit < 1 or not isinstance(value, Mapping):
        return []
    profile = contract.get("profile", {})
    components = set(contract.get("components", {})) | set(profile.get("components", {}))
    allowed_tags = set(profile.get("allowedTags", []))
    tokens = set(contract.get("tokens", []))
    assets = value.get("assets", {})
    asset_ids = set(assets) if isinstance(assets, Mapping) else set()
    seen: set[str] = set()
    issues: list[DiagnosticIssue] = []
    node_count = 0

    def visit(node: Mapping[str, Any], path: str, depth: int) -> None:
        nonlocal node_count
        if len(issues) >= limit:
            return
        node_count += 1
        if depth > 32:
            issues.append(_semantic_issue("ui_depth_limit", "初始 UI JSON 嵌套过深", path))
            return
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id:
            if node_id in seen:
                issues.append(
                    _semantic_issue("ui_duplicate_id", "初始 UI 节点 ID 重复", f"{path}/id")
                )
            seen.add(node_id)
        kind = node.get("kind")
        component = contract.get("components", {}).get(node.get("tag"), {})
        if (
            kind == "component"
            and node.get("tag") not in components
            and node.get("tag") not in allowed_tags
        ):
            issues.append(_semantic_issue("ui_component_forbidden", "组件未被允许", f"{path}/tag"))
        if (
            kind == "component"
            and isinstance(component, Mapping)
            and isinstance(component.get("packageName"), str)
            and node.get("packageName") != component["packageName"]
        ):
            issues.append(
                _semantic_issue(
                    "ui_component_package_forbidden",
                    "组件包名与生成契约不一致",
                    f"{path}/packageName",
                )
            )
        if (
            kind == "image"
            and isinstance(node.get("assetId"), str)
            and node["assetId"] not in asset_ids
        ):
            issues.append(
                _semantic_issue("ui_asset_forbidden", "图片资源未被允许", f"{path}/assetId")
            )
        node_tokens = node.get("tokens", [])
        if isinstance(node_tokens, list):
            issues.extend(
                _semantic_issue("ui_token_forbidden", "Token 未被允许", f"{path}/tokens/{index}")
                for index, token in enumerate(node_tokens)
                if isinstance(token, str) and token not in tokens
            )
            del issues[limit:]
        children = node.get("children", [])
        if not isinstance(children, list):
            return
        for index, child in enumerate(children):
            if isinstance(child, Mapping):
                visit(child, f"{path}/children/{index}", depth + 1)

    root = value.get("root")
    if isinstance(root, Mapping):
        visit(root, "/root", 1)
    if node_count > 500 and len(issues) < limit:
        issues.append(_semantic_issue("ui_node_limit", "初始 UI 节点数量超限", "/root"))
    return issues[:limit]


def _semantic_issue(code: str, message: str, path: str) -> DiagnosticIssue:
    return {
        "code": code,
        "path": path,
        "keyword": "semantic",
        "expected": "",
        "actual": "",
        "message": message,
    }


def validate_initial_ui_document(value: Any, contract: Mapping[str, Any]) -> None:
    validate("initial-ui-document.schema.json", value)
    issues = collect_initial_ui_document_issues(value, contract, limit=1)
    if issues:
        issue = issues[0]
        raise ContractError(issue["code"], issue["message"], path=issue["path"])
