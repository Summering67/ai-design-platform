from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request

from .agents.codegen.agent import run_codegen
from .agents.codegen.defaults import (
    DEFAULT_AGENT_OUTPUT_ROOT,
    DEFAULT_CODEGEN_INPUT_DIR,
    load_default_codegen_request,
    output_directory_for,
)
from .agents.codegen.tools import (
    UnavailableCanvasCapture,
    UnavailablePreviewRenderer,
    UnavailableStaticVerifier,
)
from .agents.errors import AgentError
from .agents.model import MultimodalModelPort
from .auth.router import current_user
from .database import UserModel
from .dto import CodegenRequest

router = APIRouter(prefix="/api/codegen")


def _model(request: Request) -> MultimodalModelPort:
    return request.app.state.agent_model  # type: ignore[no-any-return]


@router.post("", response_model=None)
async def codegen(
    body: CodegenRequest,
    request: Request,
    _: UserModel = Depends(current_user),
) -> dict[str, Any]:
    verifier = getattr(request.app.state, "codegen_verifier", UnavailableStaticVerifier())
    renderer = getattr(request.app.state, "codegen_renderer", UnavailablePreviewRenderer())
    capture = getattr(request.app.state, "codegen_canvas_capture", None) or UnavailableCanvasCapture()
    try:
        request_body = body.model_dump(by_alias=True, exclude_none=True)
        output_directory = None
        if "document" not in request_body:
            options = request_body.get("options")
            request_body, source = load_default_codegen_request(DEFAULT_CODEGEN_INPUT_DIR)
            if options is not None:
                request_body["options"] = options
            output_directory = output_directory_for(source, DEFAULT_AGENT_OUTPUT_ROOT)
        else:
            canvas = request_body.get("canvas")
            if not isinstance(canvas, dict):
                raise AgentError("codegen_input_invalid", "Codegen 请求缺少画布上下文")
            images = await capture.capture(request_body["document"], canvas)
            request_body["canvasImages"] = images
        request_body.pop("canvas", None)
        return await asyncio.wait_for(
            run_codegen(
                request_body,
                _model(request),
                request.app.state.config.agent,
                verifier=verifier,
                renderer=renderer,
                output_directory=output_directory,
            ),
            timeout=request.app.state.config.agent.total_timeout or None,
        )
    except TimeoutError as error:
        raise AgentError("codegen_timeout", "Codegen 运行超时") from error
