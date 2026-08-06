from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_design_server.agents.contracts import (
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
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")
    validate_prd(_read("packages/design-contract/fixtures/v2/standardized-prd.valid.json"))
    validate_report(_read("packages/design-contract/fixtures/v2/ui-validation-report.valid.json"))
    validate_event(_read("packages/design-contract/fixtures/v2/agent-run-event.valid.json"))
    validate_tree(_read("packages/design-contract/fixtures/v2/login-page.document.json"), contract)


def test_v2_prd_rejects_unknown_fields_and_duplicate_ids() -> None:
    invalid = _read("packages/design-contract/fixtures/v2/standardized-prd.invalid.json")
    with pytest.raises(ContractError):
        validate_prd(invalid)
