from __future__ import annotations

import base64
import json
import struct
from pathlib import Path
from typing import Any

from ..errors import AgentError

SERVER_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_AGENT_OUTPUT_ROOT = SERVER_ROOT / ".agent-outputs"
DEFAULT_CODEGEN_INPUT_DIR = (
    DEFAULT_AGENT_OUTPUT_ROOT
    / "207bae28-0348-49b3-9d52-2391b6790f47"
    / "2804b82c-4f87-4981-9bc7-2fd32d7c4da3"
)
_IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _image_size(data: bytes, suffix: str) -> tuple[int, int]:
    if suffix == ".png" and data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if suffix in {".jpg", ".jpeg"} and data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            length = int.from_bytes(data[index : index + 2], "big")
            if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
                return (
                    int.from_bytes(data[index + 5 : index + 7], "big"),
                    int.from_bytes(data[index + 3 : index + 5], "big"),
                )
            index += length
    if suffix == ".webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP" and data[12:16] == b"VP8X":
        return (
            1 + int.from_bytes(data[24:27], "little"),
            1 + int.from_bytes(data[27:30], "little"),
        )
    raise AgentError("codegen_input_invalid", "无法读取画布图片尺寸")


def _image_request(path: Path, document: dict[str, Any]) -> dict[str, Any]:
    data = path.read_bytes()
    width, height = _image_size(data, path.suffix.lower())
    viewport_id = path.stem
    viewport = document.get("resolvedLayouts", {}).get(viewport_id, {}).get("viewport", {})
    if viewport.get("width") != width or viewport.get("height") != height:
        raise AgentError("codegen_input_invalid", "画布图片尺寸与 DesignDocument 不一致")
    return {
        "viewportId": viewport_id,
        "width": width,
        "height": height,
        "mimeType": _IMAGE_TYPES[path.suffix.lower()],
        "image": {"kind": "base64", "data": base64.b64encode(data).decode("ascii")},
    }


def load_default_codegen_request(
    input_dir: Path = DEFAULT_CODEGEN_INPUT_DIR,
) -> tuple[dict[str, Any], Path]:
    candidates = sorted(input_dir.glob("03-auto_layout-attempt-*.json"))
    source = candidates[-1] if candidates else None
    if source is None:
        raise AgentError("codegen_input_invalid", "默认 Auto Layout 输出不存在")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        document = payload.get("final_document")
        if not isinstance(document, dict):
            raise AgentError("codegen_input_invalid", "Auto Layout 输出缺少 final_document")
        manifest = input_dir / "canvas-images.json"
        if manifest.is_file():
            manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
            images = manifest_value.get("canvasImages") if isinstance(manifest_value, dict) else manifest_value
            if not isinstance(images, list):
                raise AgentError("codegen_input_invalid", "画布图片清单格式无效")
        else:
            images = [
                _image_request(path, document)
                for path in sorted(input_dir.iterdir())
                if path.is_file() and path.suffix.lower() in _IMAGE_TYPES
            ]
        if not images:
            raise AgentError("codegen_input_invalid", "默认输入目录缺少画布图片")
        return {"document": document, "canvasImages": images}, source
    except AgentError:
        raise
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise AgentError("codegen_input_invalid", "默认 Codegen 输入无法读取") from error


def output_directory_for(source: Path, output_root: Path = DEFAULT_AGENT_OUTPUT_ROOT) -> Path:
    try:
        relative = source.parent.resolve().relative_to(output_root.resolve())
    except ValueError as error:
        raise AgentError("codegen_output_invalid", "Codegen 输出目录无效") from error
    return output_root / relative / "codegen"


def write_codegen_files(result: dict[str, Any], output_directory: Path) -> None:
    try:
        output_directory.mkdir(parents=True, exist_ok=True)
        for file in result["files"]:
            target = (output_directory / file["path"]).resolve()
            if target.parent != output_directory.resolve():
                raise AgentError("codegen_output_invalid", "Codegen 文件路径无效")
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(file["content"], encoding="utf-8", newline="\n")
            temporary.replace(target)
    except AgentError:
        raise
    except OSError as error:
        raise AgentError("codegen_output_invalid", "Codegen 文件无法写入") from error
