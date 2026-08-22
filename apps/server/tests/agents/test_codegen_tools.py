from __future__ import annotations

import pytest

from ai_design_server.agents.codegen.tools import CandidateWorkspace, bounded_diagnostics
from ai_design_server.agents.errors import AgentError


@pytest.mark.asyncio
async def test_candidate_workspace_is_atomic_and_rejects_extra_files() -> None:
    async with CandidateWorkspace("Fixture") as workspace:
        await workspace.write_candidate(
            {
                "Fixture.tsx": "import './Fixture.css'; export default function Fixture() { return null; }",
                "Fixture.css": ".fixture {}",
            }
        )
        assert set(await workspace.read_candidate()) == {"Fixture.tsx", "Fixture.css"}
        with pytest.raises(AgentError) as error:
            await workspace.write_candidate({"Fixture.tsx": "x", "Fixture.css": "y", "extra.txt": "z"})
        assert error.value.code == "codegen_generation_failed"


@pytest.mark.asyncio
async def test_candidate_workspace_rejects_path_traversal_and_cleans_up() -> None:
    with pytest.raises(AgentError) as error:
        CandidateWorkspace("../escape")
    assert error.value.code == "codegen_input_invalid"


def test_bounded_diagnostics_redacts_paths_and_deduplicates() -> None:
    diagnostics = bounded_diagnostics(
        [
            {"tool": "tsc", "rule": "TS2322", "file": "/private/work/Fixture.tsx", "line": 2, "column": 3, "message": "type mismatch"},
            {"tool": "tsc", "rule": "TS2322", "file": "/private/work/Fixture.tsx", "line": 2, "column": 3, "message": "type mismatch"},
        ]
    )
    assert len(diagnostics) == 1
    assert diagnostics[0]["file"] == "Fixture.tsx"
