from __future__ import annotations

import asyncio
import os
import re
import tempfile
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar, Protocol, Self

from ..errors import AgentError
from .state import CodegenDiagnostic

_BASE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_MAX_FILE_BYTES = 1_000_000


class StaticVerifier(Protocol):
    async def verify(self, workspace: CandidateWorkspace) -> list[CodegenDiagnostic]: ...


class PreviewRenderer(Protocol):
    async def render(
        self, workspace: CandidateWorkspace, viewport_id: str, width: int, height: int
    ) -> bytes: ...


class CanvasCapture(Protocol):
    async def capture(
        self, document: Mapping[str, Any], canvas: Mapping[str, Any]
    ) -> list[dict[str, Any]]: ...


class UnavailableCanvasCapture:
    async def capture(
        self, document: Mapping[str, Any], canvas: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        raise AgentError("codegen_canvas_capture_unavailable", "当前画布没有可用的截图捕获器")


class CanvasCaptureAdapter:
    """将画布桥接器封装为 Agent 可调用的自动截图工具。"""

    def __init__(
        self,
        capture_fn: Callable[[Mapping[str, Any], Mapping[str, Any]], Awaitable[list[dict[str, Any]]]],
        *,
        timeout: float = 30.0,
        max_images: int = 8,
    ) -> None:
        self.capture_fn = capture_fn
        self.timeout = timeout
        self.max_images = max_images

    async def capture(
        self, document: Mapping[str, Any], canvas: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        viewport_ids = canvas.get("viewportIds")
        layouts = document.get("resolvedLayouts")
        if (
            not isinstance(viewport_ids, list)
            or not 1 <= len(viewport_ids) <= self.max_images
            or not all(isinstance(item, str) and item for item in viewport_ids)
            or not isinstance(layouts, Mapping)
            or any(item not in layouts for item in viewport_ids)
        ):
            raise AgentError("codegen_input_invalid", "画布上下文的 viewport 无效")
        try:
            images = await asyncio.wait_for(self.capture_fn(document, canvas), timeout=self.timeout)
        except TimeoutError as error:
            raise AgentError("codegen_timeout", "画布截图超时") from error
        if not isinstance(images, list) or not 1 <= len(images) <= self.max_images:
            raise AgentError("codegen_canvas_capture_failed", "画布截图数量无效")
        return images


class VisualReviewer(Protocol):
    async def review(
        self, source_image: Mapping[str, Any], preview: bytes, *, viewport_id: str
    ) -> list[CodegenDiagnostic]: ...


class CandidateWorkspace(AbstractAsyncContextManager["CandidateWorkspace"]):
    def __init__(self, file_base_name: str, *, max_file_bytes: int = _MAX_FILE_BYTES) -> None:
        if not _BASE_NAME.fullmatch(file_base_name):
            raise AgentError("codegen_input_invalid", "候选文件名无效")
        self.file_base_name = file_base_name
        self.max_file_bytes = max_file_bytes
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self._root: Path | None = None

    async def __aenter__(self) -> Self:
        self._temporary = tempfile.TemporaryDirectory(prefix="design-codegen-")
        self._root = Path(self._temporary.name).resolve()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()
        self._temporary = None
        self._root = None

    def _path(self, suffix: str) -> Path:
        if self._root is None:
            raise AgentError("codegen_workspace_closed", "Codegen 工作区已关闭")
        path = (self._root / f"{self.file_base_name}{suffix}").resolve()
        if path.parent != self._root:
            raise AgentError("codegen_security_violation", "候选路径无效")
        return path

    async def write_candidate(self, files: Mapping[str, str]) -> None:
        expected = {f"{self.file_base_name}.tsx", f"{self.file_base_name}.css"}
        if set(files) != expected:
            raise AgentError("codegen_generation_failed", "候选必须恰好包含 TSX 和 CSS")
        for name, content in files.items():
            if not isinstance(content, str) or not content.strip():
                raise AgentError("codegen_generation_failed", "候选文件不能为空")
            if len(content.encode()) > self.max_file_bytes:
                raise AgentError("codegen_limit_exceeded", "候选文件超出大小限制")
            suffix = ".tsx" if name.endswith(".tsx") else ".css" if name.endswith(".css") else ""
            if not suffix or name != f"{self.file_base_name}{suffix}":
                raise AgentError("codegen_security_violation", "候选文件名无效")
            target = self._path(suffix)
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(content, encoding="utf-8", newline="\n")
            os.replace(temporary, target)

    async def read_candidate(self) -> dict[str, str]:
        files: dict[str, str] = {}
        for suffix in (".tsx", ".css"):
            path = self._path(suffix)
            if not path.is_file():
                raise AgentError("codegen_generation_failed", "候选文件不完整")
            files[path.name] = path.read_text(encoding="utf-8")
        return files

    @property
    def root(self) -> Path:
        if self._root is None:
            raise AgentError("codegen_workspace_closed", "Codegen 工作区已关闭")
        return self._root


class UnavailablePreviewRenderer:
    async def render(
        self, workspace: CandidateWorkspace, viewport_id: str, width: int, height: int
    ) -> bytes:
        raise AgentError("codegen_visual_mismatch", "预览渲染器不可用")


class PreviewRendererAdapter:
    """对预览后端提供固定的 viewport、超时和图片大小边界。"""

    def __init__(
        self,
        render_fn: Callable[[CandidateWorkspace, str, int, int], Awaitable[bytes]],
        *,
        timeout: float = 30.0,
        max_bytes: int = 8_000_000,
        max_pixels: int = 20_000_000,
    ) -> None:
        self.render_fn = render_fn
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_pixels = max_pixels

    async def render(
        self, workspace: CandidateWorkspace, viewport_id: str, width: int, height: int
    ) -> bytes:
        if not viewport_id or width <= 0 or height <= 0 or width * height > self.max_pixels:
            raise AgentError("codegen_limit_exceeded", "预览 viewport 超出限制")
        try:
            image = await asyncio.wait_for(
                self.render_fn(workspace, viewport_id, width, height), timeout=self.timeout
            )
        except TimeoutError as error:
            raise AgentError("codegen_timeout", "预览渲染超时") from error
        if not image or len(image) > self.max_bytes:
            raise AgentError("codegen_limit_exceeded", "预览图片超出大小限制")
        return image


class UnavailableStaticVerifier:
    async def verify(self, workspace: CandidateWorkspace) -> list[CodegenDiagnostic]:
        raise AgentError("codegen_verification_failed", "静态检查器不可用")


class FixedStaticVerifier:
    """使用服务端固定命令检查候选，不接受模型提供的命令。"""

    _ALLOWED_EXECUTABLES: ClassVar[set[str]] = {"pnpm", "node", "npx", "prettier", "tsc", "eslint"}

    def __init__(self, commands: Mapping[str, Sequence[str]], *, timeout: float = 30.0) -> None:
        self.commands = dict(commands)
        self.timeout = timeout
        if set(self.commands) - {"format", "typescript", "eslint"}:
            raise ValueError("静态检查名称无效")
        if any(not command or Path(command[0]).name not in self._ALLOWED_EXECUTABLES for command in self.commands.values()):
            raise ValueError("静态检查命令不在允许列表")

    async def verify(self, workspace: CandidateWorkspace) -> list[CodegenDiagnostic]:
        diagnostics: list[CodegenDiagnostic] = []
        for name, command in self.commands.items():
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    cwd=workspace.root,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                output, _ = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            except TimeoutError as error:
                raise AgentError("codegen_timeout", f"{name} 检查超时") from error
            if process.returncode:
                text = output.decode("utf-8", errors="replace")
                diagnostics.append(
                    {
                        "tool": name,
                        "rule": f"{name}_failed",
                        "file": _diagnostic_file(text),
                        "line": _diagnostic_line(text),
                        "column": _diagnostic_column(text),
                        "message": _diagnostic_message(text),
                        "severity": "error",
                    }
                )
        return diagnostics


def _diagnostic_file(output: str) -> str:
    match = re.search(r"(?:^|\n)([^\s:]+\.(?:tsx|css))(?:[:(](\d+))?", output)
    return match.group(1) if match else ""


def _diagnostic_line(output: str) -> int:
    match = re.search(r"\.(?:tsx|css)[:(](\d+)", output)
    return int(match.group(1)) if match else 0


def _diagnostic_column(output: str) -> int:
    match = re.search(r"\.(?:tsx|css):\d+:(\d+)", output)
    return int(match.group(1)) if match else 0


def _diagnostic_message(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return (lines[-1] if lines else "静态检查失败")[:400]


def bounded_diagnostics(
    diagnostics: Sequence[Mapping[str, Any]], *, max_items: int = 40, max_bytes: int = 12000
) -> list[CodegenDiagnostic]:
    result: list[CodegenDiagnostic] = []
    seen: set[tuple[str, str, str, int, int]] = set()
    for item in diagnostics:
        message = str(item.get("message", "")).replace("\n", " ").strip()[:400]
        normalized: CodegenDiagnostic = {
            "tool": str(item.get("tool", "unknown"))[:40],
            "rule": str(item.get("rule", "unknown"))[:80],
            "file": Path(str(item.get("file", ""))).name[:120],
            "line": max(0, int(item.get("line", 0) or 0)),
            "column": max(0, int(item.get("column", 0) or 0)),
            "message": message,
            "severity": item.get("severity", "error") if item.get("severity") in {"error", "warning", "info"} else "error",
        }
        key = (normalized["tool"], normalized["rule"], normalized["file"], normalized["line"], normalized["column"])
        if key in seen or not message:
            continue
        seen.add(key)
        candidate = [*result, normalized]
        if len(candidate) > max_items or len(str(candidate).encode()) > max_bytes:
            break
        result.append(normalized)
    return result
