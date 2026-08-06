import json
from pathlib import Path

import pytest

from ai_design_server.design import v2
from ai_design_server.errors import InvalidRequestError

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "packages/design-contract/fixtures/v2"


def test_v2_schema_resource_validates_contract_fixture() -> None:
    payload = (FIXTURE_ROOT / "login-page.document.json").read_bytes()

    result = v2.prepare_v2(payload, allowed=True)

    assert result["original_version"] == "2.0.0"


def test_v2_schema_rejects_invalid_fixture() -> None:
    payload = json.loads((FIXTURE_ROOT / "invalid/runtime-field.document.json").read_text())

    with pytest.raises(InvalidRequestError):
        v2.prepare_v2(json.dumps(payload).encode(), allowed=True)


def test_v2_schema_falls_back_to_workspace_in_source_mode(monkeypatch) -> None:
    monkeypatch.setattr(v2.resources, "files", lambda _: _MissingResource())

    assert json.loads(v2._schema_text())["$schema"].endswith("2020-12/schema")


class _MissingResource:
    def joinpath(self, _: str) -> "_MissingResource":
        return self

    def is_file(self) -> bool:
        return False
