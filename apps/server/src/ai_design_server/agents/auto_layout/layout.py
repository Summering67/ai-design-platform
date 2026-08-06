from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, cast

from ..errors import ContractError


def _walk(node: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    if node.get("id") == node_id:
        return node
    for child in node.get("children", []):
        found = _walk(child, node_id)
        if found is not None:
            return found
    return None


def apply_layout(document: Mapping[str, Any], operations: list[Mapping[str, Any]], contract: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = deepcopy(document)
    layout = contract.get("layout", {})
    allowed_modes = set(layout.get("modes", ["flex"]))
    allowed_sizing = set(layout.get("sizing", ["fixed", "fill", "hug", "minmax"]))
    changes: list[dict[str, Any]] = []
    for operation in operations:
        node_id = operation.get("nodeId")
        node = _walk(result["root"], node_id) if isinstance(node_id, str) else None
        if node is None:
            raise ContractError("layout_unknown_node", "布局计划引用未知节点")
        mode = operation.get("mode", "flex")
        if mode not in allowed_modes:
            raise ContractError("layout_mode_forbidden", "布局模式未被设计系统允许")
        if mode == "flex":
            direction = operation.get("direction", "row")
            if direction not in {"row", "column", "row-reverse", "column-reverse"}:
                raise ContractError("layout_direction_invalid", "Flex 方向无效")
            style = node.setdefault("style", {})
            for key in ("direction", "justifyContent", "alignItems", "flexWrap", "gap", "padding", "rowGap", "columnGap"):
                if key in operation:
                    value = operation[key]
                    if isinstance(value, (int, float)) and value < 0:
                        raise ContractError("layout_negative_value", "布局数值不能为负")
                    style_key = "flexDirection" if key == "direction" else "columnGap" if key == "gap" else key
                    style[style_key] = value
            style["display"] = "flex"
        breakpoints = operation.get("breakpoints")
        if breakpoints is not None:
            if not isinstance(breakpoints, Mapping):
                raise ContractError("layout_breakpoints_invalid", "响应式断点必须是对象")
            responsive = node.setdefault("responsive", {})
            allowed = {"direction", "justifyContent", "alignItems", "flexWrap", "gap", "rowGap", "columnGap", "padding", "sizing", "visible"}
            for breakpoint, values in breakpoints.items():
                if not isinstance(breakpoint, str) or not breakpoint or not isinstance(values, Mapping):
                    raise ContractError("layout_breakpoints_invalid", "响应式断点配置无效")
                if any(key not in allowed for key in values):
                    raise ContractError("layout_responsive_capability_forbidden", "响应式配置包含未允许的能力")
                if any(isinstance(value, (int, float)) and value < 0 for value in values.values()):
                    raise ContractError("layout_negative_value", "布局数值不能为负")
                responsive[breakpoint] = dict(values)
        sizing = operation.get("sizing")
        if sizing is not None:
            if sizing not in allowed_sizing:
                raise ContractError("layout_sizing_forbidden", "尺寸策略未被设计系统允许")
            node.setdefault("props", {})["data-sizing"] = sizing
        changes.append({"nodeId": node_id, "operation": dict(operation)})
    return cast(dict[str, Any], result), changes
