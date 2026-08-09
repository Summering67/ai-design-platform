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
    return json.loads((ROOT / "packages/design-contract/fixtures/v2" / name).read_text(encoding="utf-8"))


def test_initial_ui_and_layout_plan_valid_fixtures() -> None:
    for schema, fixture in (("initial-ui-document.schema.json", "initial-ui-document.valid.json"), ("layout-plan.schema.json", "layout-plan.valid.json")):
        assert list(Draft202012Validator(load_schema(schema)).iter_errors(_fixture(fixture))) == []


def test_initial_ui_and_layout_plan_reject_forbidden_fields() -> None:
    for schema, fixture in (("initial-ui-document.schema.json", "initial-ui-document.invalid.json"), ("layout-plan.schema.json", "layout-plan.invalid.json")):
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
