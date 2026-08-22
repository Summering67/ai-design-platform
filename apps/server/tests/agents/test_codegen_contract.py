from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

ROOT = Path(__file__).resolve().parents[4]
SCHEMA_ROOT = ROOT / "packages/design-contract/schema/v2"
FIXTURE_ROOT = ROOT / "packages/design-contract/fixtures/v2"


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(name: str) -> Draft202012Validator:
    schema = _json(SCHEMA_ROOT / name)
    store = {}
    store[schema["$id"]] = schema
    if name == "codegen-request.schema.json":
        document_schema = _json(SCHEMA_ROOT / "design-document.schema.json")
        store[document_schema["$id"]] = document_schema
    resolver = RefResolver((SCHEMA_ROOT / name).as_uri(), schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def test_codegen_request_and_result_fixtures_validate() -> None:
    assert list(_validator("codegen-request.schema.json").iter_errors(_json(FIXTURE_ROOT / "codegen-request.valid.json"))) == []
    assert list(_validator("codegen-result.schema.json").iter_errors(_json(FIXTURE_ROOT / "codegen-result.valid.json"))) == []


def test_codegen_request_rejects_duplicate_viewports() -> None:
    request = _json(FIXTURE_ROOT / "invalid/codegen-request.duplicate-viewport.json")
    assert list(_validator("codegen-request.schema.json").iter_errors(request)) == []
    assert isinstance(request, dict)
    viewport_ids = [image["viewportId"] for image in request["canvasImages"]]
    assert len(viewport_ids) != len(set(viewport_ids))


def test_codegen_result_rejects_path_traversal() -> None:
    errors = list(
        _validator("codegen-result.schema.json").iter_errors(
            _json(FIXTURE_ROOT / "invalid/codegen-result.path-traversal.json")
        )
    )
    assert errors
