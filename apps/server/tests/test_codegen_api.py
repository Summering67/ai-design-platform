from __future__ import annotations

import asyncio

import pytest

from ai_design_server.agents.codegen.tools import (
    CandidateWorkspace,
    CanvasCaptureAdapter,
    PreviewRendererAdapter,
    UnavailableCanvasCapture,
)
from ai_design_server.app import create_app
from ai_design_server.config import AIConfig, AuthConfig, DatabaseConfig, RuntimeConfig


def _config() -> RuntimeConfig:
    return RuntimeConfig(
        database=DatabaseConfig(dsn="postgresql://localhost/aidp"),
        ai=AIConfig(base_url="https://ai.test", api_key="test-key", vision_enabled=True),
        auth=AuthConfig(fixed_user_password="test-password"),
    )


def test_codegen_route_is_independent_from_project_generation_routes() -> None:
    app = create_app(config=_config())
    paths = set(app.openapi()["paths"])

    assert "/api/codegen" in paths
    assert "/api/projects" in paths
    assert "/api/codegen" not in {"/api/projects", "/api/projects/{project_id}/generations"}


@pytest.mark.asyncio
async def test_preview_renderer_adapter_enforces_viewport_and_output_limits() -> None:
    async def render(workspace: CandidateWorkspace, viewport_id: str, width: int, height: int) -> bytes:
        return b"png"

    adapter = PreviewRendererAdapter(render, max_pixels=100)
    async with CandidateWorkspace("Fixture") as workspace:
        assert await adapter.render(workspace, "desktop", 10, 10) == b"png"
        with pytest.raises(Exception, match="超出限制"):
            await adapter.render(workspace, "desktop", 11, 10)


@pytest.mark.asyncio
async def test_canvas_capture_adapter_reads_requested_viewports_automatically() -> None:
    calls: list[tuple[dict[str, object], dict[str, object]]] = []

    async def capture(document: dict[str, object], canvas: dict[str, object]) -> list[dict[str, object]]:
        calls.append((document, canvas))
        return [{"viewportId": "desktop", "width": 1, "height": 1, "mimeType": "image/png", "image": {"kind": "ref", "id": "captured"}}]

    adapter = CanvasCaptureAdapter(capture)
    document = {"resolvedLayouts": {"desktop": {}}}
    canvas = {"viewportIds": ["desktop"]}
    images = await adapter.capture(document, canvas)

    assert images[0]["viewportId"] == "desktop"
    assert calls == [(document, canvas)]


@pytest.mark.asyncio
async def test_canvas_capture_adapter_rejects_unknown_viewport_and_unavailable_capture() -> None:
    async def capture(document: dict[str, object], canvas: dict[str, object]) -> list[dict[str, object]]:
        return []

    adapter = CanvasCaptureAdapter(capture)
    with pytest.raises(Exception, match="viewport 无效"):
        await adapter.capture({"resolvedLayouts": {}}, {"viewportIds": ["desktop"]})
    with pytest.raises(Exception, match="没有可用的截图捕获器"):
        await UnavailableCanvasCapture().capture({}, {})


@pytest.mark.asyncio
async def test_canvas_capture_adapter_times_out() -> None:
    async def capture(document: dict[str, object], canvas: dict[str, object]) -> list[dict[str, object]]:
        await asyncio.sleep(0.05)
        return []

    adapter = CanvasCaptureAdapter(capture, timeout=0.001)
    with pytest.raises(Exception, match="截图超时"):
        await adapter.capture({"resolvedLayouts": {"desktop": {}}}, {"viewportIds": ["desktop"]})
