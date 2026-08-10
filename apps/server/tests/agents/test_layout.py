from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_design_server.agents.auto_layout.layout import (
    apply_layout,
    move_node_with_offset,
    resolve_layouts,
)
from ai_design_server.agents.contracts import validate_tree
from ai_design_server.agents.errors import ContractError

ROOT = Path(__file__).resolve().parents[4]


def _read(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_layout_is_deterministic_and_keeps_v2_document_valid() -> None:
    document = _read("packages/design-contract/fixtures/v2/login-page.document.json")
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
    operations = [
        {
            "nodeId": "root",
            "layout": {"mode": "flex", "direction": "column", "wrap": "wrap", "gap": 16},
        }
    ]
    first, changes = apply_layout(document, operations, contract)
    second, _ = apply_layout(document, operations, contract)
    validate_tree(first, contract)
    assert first == second
    assert changes[0]["nodeId"] == "root"
    assert first["root"]["layout"]["wrap"] == "wrap"


def test_layout_rejects_unknown_node() -> None:
    document = _read("packages/design-contract/fixtures/v2/login-page.document.json")
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
    with pytest.raises(ContractError, match="未知节点"):
        apply_layout(document, [{"nodeId": "missing", "layout": {"mode": "flex"}}], contract)


def test_layout_applies_constrained_responsive_breakpoints() -> None:
    document = _read("packages/design-contract/fixtures/v2/login-page.document.json")
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
    result, _ = apply_layout(
        document,
        [
            {
                "nodeId": "root",
                "responsive": {
                    "mobile": {
                        "direction": "column",
                        "wrap": "wrap",
                        "gap": 8,
                        "layoutItem": {"width": {"mode": "fill"}},
                    }
                },
            }
        ],
        contract,
    )
    validate_tree(result, contract)
    assert result["root"]["responsive"]["mobile"]["direction"] == "column"
    assert result["root"]["responsive"]["mobile"]["wrap"] == "wrap"
    assert result["root"]["responsive"]["mobile"]["layoutItem"]["width"]["mode"] == "fill"


def test_layout_rejects_unregistered_responsive_capability() -> None:
    document = _read("packages/design-contract/fixtures/v2/login-page.document.json")
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
    with pytest.raises(ContractError, match="未允许"):
        apply_layout(
            document,
            [{"nodeId": "root", "responsive": {"mobile": {"mediaQuery": "@media"}}}],
            contract,
        )


def test_layout_rejects_duplicate_node_operations() -> None:
    document = _read("packages/design-contract/fixtures/v2/login-page.document.json")
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
    operations = [
        {"nodeId": "root", "layout": {"mode": "flex"}},
        {"nodeId": "root", "layoutItem": {"width": {"mode": "fill"}}},
    ]
    with pytest.raises(ContractError, match="重复节点"):
        apply_layout(document, operations, contract)


def test_resolve_layouts_is_deterministic_and_covers_tree() -> None:
    document = _read("packages/design-contract/fixtures/v2/login-page.document.json")
    viewports = [{"id": "desktop", "width": 1440, "height": 900}]
    first = resolve_layouts(document, viewports)
    second = resolve_layouts(document, viewports)
    assert first == second
    assert set(first["desktop"]["nodes"]) == {"root", "logo-node", "title", "submit"}


def test_resolve_layouts_reports_missing_hug_measurement_path() -> None:
    document = _read("packages/design-contract/fixtures/v2/login-page.document.json")
    document["root"]["children"][1]["layoutItem"] = {"width": {"mode": "hug"}}

    with pytest.raises(ContractError, match="节点 title") as raised:
        resolve_layouts(document, measurements={"title": {"height": 40}})

    assert raised.value.code == "layout_measurement_missing"
    assert raised.value.path == "/root/children/1/layoutItem/width"


def test_move_node_writes_offset_and_recomputes_geometry() -> None:
    document = _read("packages/design-contract/fixtures/v2/login-page.document.json")
    document["resolvedLayouts"] = resolve_layouts(document)
    moved = move_node_with_offset(document, "title", "desktop", 32, 48)
    assert moved["root"]["children"][1]["layoutItem"]["offset"] == {"x": 32, "y": 8}
    assert moved["resolvedLayouts"]["desktop"]["nodes"]["title"]["x"] == 32
    assert moved["resolvedLayouts"]["desktop"]["nodes"]["title"]["y"] == 48
