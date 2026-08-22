from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_design_server.agents.codegen.contracts import validate_codegen_request
from ai_design_server.agents.errors import AgentError

ROOT = Path(__file__).resolve().parents[4]


def _fixture(name: str) -> dict[str, object]:
    return json.loads(
        (ROOT / "packages/design-contract/fixtures/v2" / name).read_text(encoding="utf-8")
    )


def test_codegen_request_freezes_context_and_derives_digests() -> None:
    context = validate_codegen_request(_fixture("codegen-request.valid.json"))

    assert context.component_name == "CodegenFixture"
    assert context.file_base_name == "CodegenFixture"
    assert context.document_digest
    assert context.input_digest
    context.document["name"] = "changed"
    assert context.document_digest != ""


def test_codegen_request_rejects_duplicate_viewport_images() -> None:
    request = _fixture("codegen-request.valid.json")
    assert isinstance(request["canvasImages"], list)
    request["canvasImages"].append(dict(request["canvasImages"][0]))

    with pytest.raises(AgentError, match="viewport 图片不可重复") as error:
        validate_codegen_request(request)

    assert error.value.code == "codegen_input_invalid"


def test_codegen_request_rejects_invalid_file_name() -> None:
    request = _fixture("codegen-request.valid.json")
    assert isinstance(request["options"], dict)
    request["options"]["fileBaseName"] = "../escape"

    with pytest.raises(AgentError) as error:
        validate_codegen_request(request)

    assert error.value.code == "codegen_input_invalid"
