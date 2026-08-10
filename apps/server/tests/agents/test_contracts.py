from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from ai_design_server.agents.contracts import (
    load_default_generation_contract,
    validate_event,
    validate_prd,
    validate_report,
    validate_tree,
)
from ai_design_server.agents.errors import ContractError

ROOT = Path(__file__).resolve().parents[4]


def _read(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_v2_fixtures_validate() -> None:
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
    validate_prd(_read("packages/design-contract/fixtures/v2/standardized-prd.valid.json"))
    validate_report(_read("packages/design-contract/fixtures/v2/ui-validation-report.valid.json"))
    validate_event(_read("packages/design-contract/fixtures/v2/agent-run-event.valid.json"))
    validate_event(
        _read("packages/design-contract/fixtures/v2/agent-run-event.input-required.json")
    )
    validate_tree(_read("packages/design-contract/fixtures/v2/login-page.document.json"), contract)


def test_validate_tree_logs_schema_failure_path(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="ai_design_server.agents.contracts")
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
    document = _read("packages/design-contract/fixtures/v2/login-page.document.json")
    document["root"]["unknownField"] = True

    with pytest.raises(ContractError) as raised:
        validate_tree(document, contract)

    record = next(
        item
        for item in caplog.records
        if getattr(item, "event_type", "") == "design_document_schema_failure"
    )
    assert raised.value.path == "/root/unknownField"
    assert record.code == "invalid_ui_document"
    assert record.path == "/root/unknownField"
    assert record.keyword == "additionalProperties"
    assert record.schema_fields == "unknownField"


def test_default_generation_contract_exposes_all_ant_design_components() -> None:
    contract = load_default_generation_contract()
    fixture = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
    names = [
        "button",
        "float-button",
        "icon",
        "typography",
        "divider",
        "flex",
        "grid",
        "layout",
        "masonry",
        "space",
        "splitter",
        "anchor",
        "breadcrumb",
        "dropdown",
        "menu",
        "pagination",
        "steps",
        "tabs",
        "auto-complete",
        "cascader",
        "checkbox",
        "color-picker",
        "date-picker",
        "form",
        "input",
        "input-number",
        "mentions",
        "radio",
        "rate",
        "select",
        "slider",
        "switch",
        "time-picker",
        "transfer",
        "tree-select",
        "upload",
        "avatar",
        "badge",
        "calendar",
        "card",
        "carousel",
        "collapse",
        "descriptions",
        "empty",
        "image",
        "list",
        "popover",
        "qr-code",
        "segmented",
        "statistic",
        "table",
        "tag",
        "timeline",
        "tooltip",
        "tour",
        "tree",
        "alert",
        "drawer",
        "message",
        "modal",
        "notification",
        "popconfirm",
        "progress",
        "result",
        "skeleton",
        "spin",
        "watermark",
        "affix",
        "app",
        "border-beam",
        "config-provider",
        "util",
    ]
    expected = set(contract["components"])

    assert len(expected) == 72
    assert set(fixture["components"]) == expected
    assert all(not name.startswith("ui.") for name in expected)


def test_v2_prd_rejects_unknown_fields_and_duplicate_ids() -> None:
    invalid = _read("packages/design-contract/fixtures/v2/standardized-prd.invalid.json")
    with pytest.raises(ContractError):
        validate_prd(invalid)
