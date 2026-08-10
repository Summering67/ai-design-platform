from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ai_design_server.agents.contracts import (
    load_default_generation_contract,
    load_schema,
    validate_initial_ui_document,
)
from ai_design_server.agents.errors import ContractError

ROOT = Path(__file__).resolve().parents[4]


def _fixture(name: str) -> object:
    return json.loads(
        (ROOT / "packages/design-contract/fixtures/v2" / name).read_text(encoding="utf-8")
    )


def test_initial_ui_and_layout_plan_valid_fixtures() -> None:
    for schema, fixture in (
        ("initial-ui-document.schema.json", "initial-ui-document.valid.json"),
        ("layout-plan.schema.json", "layout-plan.valid.json"),
    ):
        assert list(Draft202012Validator(load_schema(schema)).iter_errors(_fixture(fixture))) == []


def test_initial_ui_and_layout_plan_reject_forbidden_fields() -> None:
    for schema, fixture in (
        ("initial-ui-document.schema.json", "initial-ui-document.invalid.json"),
        ("layout-plan.schema.json", "layout-plan.invalid.json"),
    ):
        assert list(Draft202012Validator(load_schema(schema)).iter_errors(_fixture(fixture)))


def test_initial_ui_semantic_gate_rejects_duplicate_ids_and_unknown_assets() -> None:
    document = _fixture("initial-ui-document.valid.json")
    assert isinstance(document, dict)
    document["root"]["children"][0]["id"] = document["root"]["id"]
    try:
        validate_initial_ui_document(document, load_default_generation_contract())
    except ContractError as error:
        assert error.code == "ui_duplicate_id"
    else:
        raise AssertionError("重复节点 ID 应被语义门禁拒绝")


def test_initial_ui_reuses_design_document_visual_style() -> None:
    initial_schema = load_schema("initial-ui-document.schema.json")
    design_schema = load_schema("design-document.schema.json")

    assert initial_schema["$defs"]["style"] == design_schema["$defs"]["visualStyle"]
    for name, definition in design_schema["$defs"]["visualStyle"]["properties"].items():
        assert design_schema["$defs"]["style"]["properties"][name] == definition

    document = _fixture("initial-ui-document.valid.json")
    assert isinstance(document, dict)
    document["root"]["style"].update(
        {
            "borderRightWidth": 1,
            "borderRightColor": "#E5E7EB",
            "borderStyle": "solid",
            "boxShadow": "0 1px 2px rgb(0 0 0 / 0.1)",
            "fontFamily": "Inter",
            "letterSpacing": 0.2,
        }
    )

    assert list(Draft202012Validator(initial_schema).iter_errors(document)) == []


def test_initial_ui_rejects_layout_owned_fields() -> None:
    schema = load_schema("initial-ui-document.schema.json")
    document = _fixture("initial-ui-document.valid.json")
    assert isinstance(document, dict)
    document["root"]["layout"] = {"mode": "flex", "gap": 8}
    document["root"]["layoutItem"] = {"width": {"mode": "fill"}}
    document["root"]["responsive"] = {"mobile": {"direction": "column"}}
    document["root"]["style"]["display"] = "flex"

    paths = {
        "/" + "/".join(str(item) for item in error.absolute_path)
        for error in Draft202012Validator(schema).iter_errors(document)
    }

    assert "/root" in paths
    assert "/root/style" in paths


def test_initial_ui_accepts_only_non_geometric_layout_intent() -> None:
    schema = load_schema("initial-ui-document.schema.json")
    document = _fixture("initial-ui-document.valid.json")
    assert isinstance(document, dict)
    assert list(Draft202012Validator(schema).iter_errors(document)) == []

    document["root"]["layoutIntent"]["direction"] = "column"
    paths = {
        "/" + "/".join(str(item) for item in error.absolute_path)
        for error in Draft202012Validator(schema).iter_errors(document)
    }
    assert "/root/layoutIntent" in paths
