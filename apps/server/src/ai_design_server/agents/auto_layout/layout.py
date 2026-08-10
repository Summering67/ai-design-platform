from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from math import isfinite
from typing import Any, cast

from ..errors import ContractError

DEFAULT_VIEWPORTS = ({"id": "desktop", "width": 1440.0, "height": 900.0},)


def _number(value: Any, fallback: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        return fallback
    return float(value)


def _insets(value: Any, fallback: Any = 0) -> dict[str, float]:
    if isinstance(value, Mapping):
        return {side: max(0.0, _number(value.get(side), 0.0)) for side in ("top", "right", "bottom", "left")}
    amount = max(0.0, _number(value, 0.0))
    return {side: amount for side in ("top", "right", "bottom", "left")}


def _style_number(node: Mapping[str, Any], key: str) -> float | None:
    value = node.get("style", {}).get(key) if isinstance(node.get("style"), Mapping) else None
    return _number(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _measurement(node: Mapping[str, Any], measurements: Mapping[str, Any]) -> tuple[float, float, float | None]:
    node_id = node.get("id")
    value = measurements.get(node_id, {}) if isinstance(node_id, str) else {}
    if not isinstance(value, Mapping):
        value = {}
    width = _number(value.get("width"), _style_number(node, "width") or 0.0)
    height = _number(value.get("height"), _style_number(node, "height") or 0.0)
    baseline = value.get("baseline")
    return width, height, _number(baseline) if isinstance(baseline, (int, float)) else None


def _sizing(node: Mapping[str, Any], axis: str, available: float, measurements: Mapping[str, Any], assets: Mapping[str, Any]) -> tuple[float, float, float]:
    item = node.get("layoutItem") if isinstance(node.get("layoutItem"), Mapping) else {}
    spec = item.get(axis) if isinstance(item, Mapping) else None
    measured_width, measured_height, _ = _measurement(node, measurements)
    measured = measured_width if axis == "width" else measured_height
    if node.get("kind") == "image":
        asset_id = node.get("assetId")
        asset = assets.get(asset_id, {}) if isinstance(asset_id, str) else {}
        if isinstance(asset, Mapping):
            measured = _number(asset.get("width"), measured) if axis == "width" else _number(asset.get("height"), measured)
    spec_map = spec if isinstance(spec, Mapping) else {}
    mode = spec_map.get("mode")
    if mode == "fixed":
        value = max(0.0, _number(spec_map.get("value"), measured))
    elif mode == "fill":
        value = max(0.0, available)
    elif mode == "hug":
        node_id = node.get("id")
        if not measurements.get(node_id if isinstance(node_id, str) else "") and not node.get("children") and _style_number(node, axis) is None and node.get("kind") != "image":
            raise ContractError("layout_measurement_missing", f"hug 尺寸缺少 {axis} measurement")
        value = max(0.0, measured)
    elif mode == "minmax":
        value = max(0.0, _number(spec_map.get("min"), measured))
    else:
        value = max(0.0, _style_number(node, axis) or measured)
    minimum = max(0.0, _number(spec_map.get("min"), 0.0))
    maximum = _number(spec_map.get("max"), float("inf")) if spec_map.get("max") is not None else float("inf")
    if maximum < minimum:
        raise ContractError("layout_constraint_conflict", "布局尺寸的 max 不能小于 min")
    return min(max(value, minimum), maximum), minimum, maximum


def _layout_direction(layout: Mapping[str, Any]) -> str:
    direction = layout.get("direction", "column")
    return direction if direction in {"row", "row-reverse", "column", "column-reverse"} else "column"


def _node_item(node: Mapping[str, Any], viewport_id: str) -> dict[str, Any]:
    item = dict(node.get("layoutItem", {})) if isinstance(node.get("layoutItem"), Mapping) else {}
    responsive = node.get("responsive")
    override = responsive.get(viewport_id) if isinstance(responsive, Mapping) else None
    if isinstance(override, Mapping) and isinstance(override.get("layoutItem"), Mapping):
        item.update(override["layoutItem"])
    return item


def _layout_node(
    node: Mapping[str, Any],
    width: float,
    height: float,
    x: float,
    y: float,
    viewport_id: str,
    measurements: Mapping[str, Any],
    assets: Mapping[str, Any],
    snapshot: dict[str, dict[str, float]],
) -> None:
    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id:
        raise ContractError("layout_unknown_node", "布局节点缺少 ID")
    snapshot[node_id] = {"x": round(x, 3), "y": round(y, 3), "width": round(max(0.0, width), 3), "height": round(max(0.0, height), 3)}
    children = node.get("children", [])
    if not isinstance(children, list) or not children:
        return
    raw_layout = node.get("layout") if isinstance(node.get("layout"), Mapping) else {"mode": "flex"}
    layout = dict(cast(Mapping[str, Any], raw_layout))
    responsive = node.get("responsive")
    override = responsive.get(viewport_id) if isinstance(responsive, Mapping) else None
    if isinstance(override, Mapping):
        if isinstance(override.get("layout"), Mapping):
            layout.update(override["layout"])
        for key in ("direction", "justifyContent", "alignItems", "wrap", "gap", "rowGap", "columnGap", "padding"):
            if key in override:
                layout[key] = override[key]
    if layout.get("mode") == "absolute":
        layout = {"mode": "flex", "direction": "column", "gap": 0, "padding": 0}
    direction = _layout_direction(layout)
    padding = _insets(layout.get("padding", 0))
    content_width = max(0.0, width - padding["left"] - padding["right"])
    content_height = max(0.0, height - padding["top"] - padding["bottom"])
    main_size = content_width if direction.startswith("row") else content_height
    gap = max(0.0, _number(layout.get("gap"), 0.0))
    if direction.startswith("row"):
        gap = max(gap, _number(layout.get("columnGap"), gap))
    else:
        gap = max(gap, _number(layout.get("rowGap"), gap))
    normal: list[dict[str, Any]] = []
    absolute: list[Mapping[str, Any]] = []
    for child in children:
        if not isinstance(child, Mapping):
            continue
        item = _node_item(child, viewport_id)
        position = item.get("position", "auto") if isinstance(item, Mapping) else "auto"
        (absolute if position == "absolute" else normal).append(dict(child))
    entries: list[dict[str, Any]] = []
    for child in normal:
        item = _node_item(child, viewport_id)
        margin = _insets(item.get("margin", 0) if isinstance(item, Mapping) else 0)
        child_width, _, _ = _sizing(child, "width", content_width, measurements, assets)
        child_height, _, _ = _sizing(child, "height", content_height, measurements, assets)
        main_axis = "width" if direction.startswith("row") else "height"
        main_spec = item.get(main_axis) if isinstance(item, Mapping) else None
        basis = child_width if direction.startswith("row") else child_height
        if isinstance(main_spec, Mapping) and main_spec.get("mode") == "fill":
            basis = 0.0
        flex_grow = max(0.0, _number(item.get("flexGrow"), _number(item.get("grow"), 0.0)) if isinstance(item, Mapping) else 0.0)
        if isinstance(main_spec, Mapping) and main_spec.get("mode") == "fill":
            flex_grow = max(1.0, flex_grow)
        flex_shrink = max(0.0, _number(item.get("flexShrink"), _number(item.get("shrink"), 1.0)) if isinstance(item, Mapping) else 1.0)
        if isinstance(item, Mapping) and item.get("flexBasis") is not None and isinstance(item.get("flexBasis"), (int, float)):
            basis = max(0.0, _number(item.get("flexBasis")))
        main_spec_map = main_spec if isinstance(main_spec, Mapping) else {}
        main_min = max(0.0, _number(main_spec_map.get("min"), 0.0))
        main_max = _number(main_spec_map.get("max"), float("inf")) if main_spec_map.get("max") is not None else float("inf")
        entries.append({"node": child, "item": item, "margin": margin, "width": child_width, "height": child_height, "basis": basis, "grow": flex_grow, "shrink": flex_shrink, "min": main_min, "max": main_max})
    lines: list[list[dict[str, Any]]] = [[]]
    wrap = layout.get("wrap", "nowrap") != "nowrap"
    used = 0.0
    for entry in entries:
        margin = entry["margin"]
        outer = entry["basis"] + (margin["left"] + margin["right"] if direction.startswith("row") else margin["top"] + margin["bottom"])
        if wrap and lines[-1] and used + gap + outer > main_size:
            lines.append([])
            used = 0.0
        lines[-1].append(entry)
        used += outer + (gap if len(lines[-1]) > 1 else 0.0)
    line_cross_cursor = 0.0
    if layout.get("alignItems") == "baseline":
        for entry in entries:
            _, _, baseline = _measurement(entry["node"], measurements)
            if baseline is None:
                raise ContractError("layout_baseline_measurement_missing", "baseline 对齐缺少 measurement")
    for line_index, raw_line in enumerate(lines):
        line = list(reversed(raw_line)) if direction.endswith("-reverse") else raw_line
        total_basis = sum(entry["basis"] + (entry["margin"]["left"] + entry["margin"]["right"] if direction.startswith("row") else entry["margin"]["top"] + entry["margin"]["bottom"]) for entry in line)
        free = main_size - total_basis - gap * max(0, len(line) - 1)
        if free >= 0:
            grow_total = sum(entry["grow"] for entry in line)
            for entry in line:
                entry["resolved"] = entry["basis"] + (free * entry["grow"] / grow_total if grow_total else 0.0)
        else:
            shrink_total = sum(entry["shrink"] * max(entry["basis"], 1.0) for entry in line)
            for entry in line:
                reduction = (-free) * entry["shrink"] * max(entry["basis"], 1.0) / shrink_total if shrink_total else 0.0
                entry["resolved"] = max(0.0, entry["basis"] - reduction)
        for entry in line:
            entry["resolved"] = min(max(entry["resolved"], entry["min"]), entry["max"])
        line_cross = max((entry["height"] + entry["margin"]["top"] + entry["margin"]["bottom"] if direction.startswith("row") else entry["width"] + entry["margin"]["left"] + entry["margin"]["right"] for entry in line), default=0.0)
        justify = layout.get("justifyContent", "flex-start")
        remaining = max(0.0, main_size - sum(entry["resolved"] + (entry["margin"]["left"] + entry["margin"]["right"] if direction.startswith("row") else entry["margin"]["top"] + entry["margin"]["bottom"]) for entry in line) - gap * max(0, len(line) - 1))
        extra_gap = 0.0
        cursor = 0.0
        if justify == "center": cursor = remaining / 2
        elif justify in {"flex-end", "end"}: cursor = remaining
        elif justify == "space-between" and len(line) > 1: extra_gap = remaining / (len(line) - 1)
        elif justify in {"space-around", "space-evenly"} and line:
            divisor = len(line) if justify == "space-around" else len(line) + 1
            extra_gap = remaining / divisor
            cursor = extra_gap / 2 if justify == "space-around" else extra_gap
        for entry in line:
            margin = entry["margin"]
            if direction.startswith("row"):
                cross = entry["height"]
                align = entry["item"].get("alignSelf", layout.get("alignItems", "stretch")) if isinstance(entry["item"], Mapping) else layout.get("alignItems", "stretch")
                if align == "stretch" and not isinstance(entry["item"].get("height"), Mapping):
                    cross = max(0.0, line_cross - margin["top"] - margin["bottom"])
                cross_offset = margin["top"]
                if align in {"center"}: cross_offset = (line_cross - cross) / 2
                elif align in {"flex-end", "end"}: cross_offset = line_cross - cross - margin["bottom"]
                child_x = padding["left"] + cursor + margin["left"]
                child_y = padding["top"] + line_cross_cursor + cross_offset
                child_w, child_h = entry["resolved"], cross
                cursor += entry["resolved"] + margin["left"] + margin["right"] + gap + extra_gap
            else:
                cross = entry["width"]
                align = entry["item"].get("alignSelf", layout.get("alignItems", "stretch")) if isinstance(entry["item"], Mapping) else layout.get("alignItems", "stretch")
                if align == "stretch" and not isinstance(entry["item"].get("width"), Mapping):
                    cross = max(0.0, line_cross - margin["left"] - margin["right"])
                cross_offset = margin["left"]
                if align == "center": cross_offset = (line_cross - cross) / 2
                elif align in {"flex-end", "end"}: cross_offset = line_cross - cross - margin["right"]
                child_x = padding["left"] + line_cross_cursor + cross_offset
                child_y = padding["top"] + cursor + margin["top"]
                child_w, child_h = cross, entry["resolved"]
                cursor += entry["resolved"] + margin["top"] + margin["bottom"] + gap + extra_gap
            offset = entry["item"].get("offset", {}) if isinstance(entry["item"], Mapping) else {}
            child_x += _number(offset.get("x"), 0.0) if isinstance(offset, Mapping) else 0.0
            child_y += _number(offset.get("y"), 0.0) if isinstance(offset, Mapping) else 0.0
            _layout_node(entry["node"], child_w, child_h, child_x, child_y, viewport_id, measurements, assets, snapshot)
        line_cross_cursor += line_cross + gap
    for child in absolute:
        item = _node_item(child, viewport_id)
        inset = item.get("inset", {}) if isinstance(item, Mapping) else {}
        inset = inset if isinstance(inset, Mapping) else {}
        child_width, _, _ = _sizing(child, "width", content_width, measurements, assets)
        child_height, _, _ = _sizing(child, "height", content_height, measurements, assets)
        child_x = _number(inset.get("left"), 0.0)
        child_y = _number(inset.get("top"), 0.0)
        _layout_node(child, child_width, child_height, child_x, child_y, viewport_id, measurements, assets, snapshot)


def resolve_layouts(
    document: Mapping[str, Any],
    viewports: Sequence[Mapping[str, Any]] | None = None,
    measurements: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    selected = viewports or list(DEFAULT_VIEWPORTS)
    result: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for viewport in selected:
        if not isinstance(viewport, Mapping):
            raise ContractError("layout_viewport_invalid", "viewport 配置无效")
        viewport_id = viewport.get("id")
        width = _number(viewport.get("width"))
        height = _number(viewport.get("height"))
        if not isinstance(viewport_id, str) or not viewport_id or viewport_id in seen or width <= 0 or height <= 0:
            raise ContractError("layout_viewport_invalid", "viewport 必须具有唯一 ID 和正尺寸")
        seen.add(viewport_id)
        snapshot: dict[str, dict[str, float]] = {}
        _layout_node(document["root"], width, height, 0.0, 0.0, viewport_id, measurements or {}, document.get("assets", {}), snapshot)
        result[viewport_id] = {"viewport": {"width": width, "height": height}, "nodes": snapshot}
    return result


def move_node_with_offset(document: Mapping[str, Any], node_id: str, viewport_id: str, x: float, y: float, viewports: Sequence[Mapping[str, Any]] | None = None, measurements: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = cast(dict[str, Any], deepcopy(document))
    current = result.get("resolvedLayouts", {}).get(viewport_id, {}).get("nodes", {}).get(node_id)
    if not isinstance(current, Mapping):
        raise ContractError("layout_geometry_missing", "指定节点没有 Geometry")
    def visit(node: dict[str, Any]) -> bool:
        if node.get("id") == node_id:
            item = node.setdefault("layoutItem", {})
            offset = item.setdefault("offset", {})
            offset["x"] = _number(offset.get("x"), 0.0) + _number(x) - _number(current.get("x"))
            offset["y"] = _number(offset.get("y"), 0.0) + _number(y) - _number(current.get("y"))
            return True
        return any(visit(child) for child in node.get("children", []) if isinstance(child, dict))
    if not visit(result["root"]):
        raise ContractError("layout_unknown_node", "布局计划引用未知节点")
    result["resolvedLayouts"] = resolve_layouts(result, viewports, measurements)
    return result


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
            if _has_negative_number(planned_layout):
                raise ContractError("layout_negative_value", "布局数值不能为负")
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
        position = planned_item.get("position")
        if position == "absolute" and not isinstance(planned_item.get("inset"), Mapping):
            raise ContractError("layout_absolute_inset_required", "absolute 节点必须提供 inset")
        if position in {"auto", "flow", None} and "inset" in planned_item and "position" in planned_item:
            raise ContractError("layout_auto_inset_conflict", "auto 节点不能提供 inset")
        if position == "absolute" and "offset" in planned_item:
            raise ContractError("layout_absolute_offset_conflict", "absolute 节点不能提供 offset")
        changes.append({"nodeId": node_id, "operation": dict(operation)})
    return cast(dict[str, Any], result), changes
