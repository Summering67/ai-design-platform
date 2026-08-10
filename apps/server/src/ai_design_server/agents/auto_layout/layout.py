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


def _has_negative_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value < 0
    if isinstance(value, Mapping):
        return any(_has_negative_number(item) for item in value.values())
    return False


def apply_layout(
    document: Mapping[str, Any], operations: list[Mapping[str, Any]], contract: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = deepcopy(document)
    layout = contract.get("layout", {})
    allowed_modes = set(layout.get("modes", ["flex"]))
    allowed_sizing = set(layout.get("sizing", ["fixed", "fill", "hug", "minmax"]))
    changes: list[dict[str, Any]] = []
    node_ids = [operation.get("nodeId") for operation in operations]
    if len(node_ids) != len(set(node_ids)):
        raise ContractError("layout_duplicate_node", "布局计划包含重复节点")
    for operation in operations:
        node_id = operation.get("nodeId")
        node = _walk(result["root"], node_id) if isinstance(node_id, str) else None
        if node is None:
            raise ContractError("layout_unknown_node", "布局计划引用未知节点")
        raw_layout = operation.get("layout")
        raw_item = operation.get("layoutItem")
        planned_layout: Mapping[str, Any] = raw_layout if isinstance(raw_layout, Mapping) else {}
        planned_item: Mapping[str, Any] = raw_item if isinstance(raw_item, Mapping) else {}
        mode = planned_layout.get("mode")
        if mode is not None and mode not in allowed_modes:
            raise ContractError("layout_mode_forbidden", "布局模式未被设计系统允许")
        if planned_layout:
            node["layout"] = dict(planned_layout)
        if planned_item:
            node["layoutItem"] = dict(planned_item)
        if mode == "flex":
            direction = planned_layout.get("direction", "row")
            if direction not in {"row", "column", "row-reverse", "column-reverse"}:
                raise ContractError("layout_direction_invalid", "Flex 方向无效")
            style = node.setdefault("style", {})
            for key in ("justifyContent", "alignItems", "rowGap", "columnGap"):
                if key in planned_layout:
                    style[key] = planned_layout[key]
            if "gap" in planned_layout:
                style["rowGap"] = planned_layout["gap"]
                style["columnGap"] = planned_layout["gap"]
            padding = planned_layout.get("padding")
            if isinstance(padding, Mapping):
                for side in ("top", "right", "bottom", "left"):
                    if side in padding:
                        style[f"padding{side.capitalize()}"] = padding[side]
            if _has_negative_number(planned_layout):
                raise ContractError("layout_negative_value", "布局数值不能为负")
            style["flexDirection"] = direction
            if "wrap" in planned_layout:
                style["flexWrap"] = planned_layout["wrap"]
            style["display"] = "flex"
        breakpoints = operation.get("responsive")
        if breakpoints is not None:
            if not isinstance(breakpoints, Mapping):
                raise ContractError("layout_breakpoints_invalid", "响应式断点必须是对象")
            responsive = node.setdefault("responsive", {})
            allowed = {
                "minWidth",
                "maxWidth",
                "direction",
                "justifyContent",
                "alignItems",
                "wrap",
                "gap",
                "rowGap",
                "columnGap",
                "padding",
                "layout",
                "layoutItem",
                "visible",
            }
            for breakpoint, values in breakpoints.items():
                if (
                    not isinstance(breakpoint, str)
                    or not breakpoint
                    or not isinstance(values, Mapping)
                ):
                    raise ContractError("layout_breakpoints_invalid", "响应式断点配置无效")
                if any(key not in allowed for key in values):
                    raise ContractError(
                        "layout_responsive_capability_forbidden", "响应式配置包含未允许的能力"
                    )
                if _has_negative_number(values):
                    raise ContractError("layout_negative_value", "布局数值不能为负")
                responsive[breakpoint] = dict(values)
        for sizing in (planned_item.get("width"), planned_item.get("height")):
            if isinstance(sizing, Mapping) and sizing.get("mode") not in allowed_sizing:
                raise ContractError("layout_sizing_forbidden", "尺寸策略未被设计系统允许")
        changes.append({"nodeId": node_id, "operation": dict(operation)})
    return cast(dict[str, Any], result), changes
