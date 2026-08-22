from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_design_server.agents.codegen.defaults import (
    load_default_codegen_request,
    output_directory_for,
    write_codegen_files,
)
from ai_design_server.agents.errors import AgentError

_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cf00000004000101 000018dd8db40000000049454e44ae426082".replace(" ", "")
)


def _payload() -> dict[str, object]:
    fixture = Path(__file__).resolve().parents[4] / "packages/design-contract/fixtures/v2/codegen-request.valid.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


def test_default_loader_reads_final_document_and_canvas_image(tmp_path: Path) -> None:
    payload = _payload()
    document = payload["document"]
    assert isinstance(document, dict)
    document["resolvedLayouts"] = {"desktop": {"viewport": {"width": 1, "height": 1}, "nodes": {}}}
    source = tmp_path / "03-auto_layout-attempt-01.json"
    source.write_text(json.dumps({"final_document": document}), encoding="utf-8")
    (tmp_path / "desktop.png").write_bytes(_PNG_1X1)

    request, loaded_source = load_default_codegen_request(tmp_path)

    assert loaded_source == source
    assert request["document"] == document
    assert request["canvasImages"][0]["viewportId"] == "desktop"


def test_default_loader_requires_canvas_image(tmp_path: Path) -> None:
    payload = _payload()
    source = tmp_path / "03-auto_layout-attempt-01.json"
    source.write_text(json.dumps({"final_document": payload["document"]}), encoding="utf-8")

    with pytest.raises(AgentError, match="画布图片"):
        load_default_codegen_request(tmp_path)


def test_codegen_files_are_written_under_the_run_output(tmp_path: Path) -> None:
    source = tmp_path / "generation" / "run" / "03-auto_layout-attempt-01.json"
    output_root = tmp_path
    result = {"files": [{"path": "Page.tsx", "content": "export default function Page() {}"}, {"path": "Page.css", "content": ".page {}"}]}

    output = output_directory_for(source, output_root)
    write_codegen_files(result, output)

    assert (output / "Page.tsx").read_text() == result["files"][0]["content"]
    assert (output / "Page.css").read_text() == result["files"][1]["content"]
