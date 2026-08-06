from __future__ import annotations

from typing import Any

from ..errors import InvalidRequestError

MAX_DOCUMENT_BYTES = 1 << 20


def prepare_v1(payload: bytes, allowed: bool) -> dict[str, Any]:
    if not allowed:
        raise PermissionError("无权修改设计文档")
    if not payload or len(payload) > MAX_DOCUMENT_BYTES:
        raise InvalidRequestError("设计文档无效")
    import json

    document = json.loads(payload)
    if not isinstance(document, dict) or not str(document.get("version", "")).startswith("1."):
        raise InvalidRequestError("设计文档版本不受支持")
    required = {"id", "name", "assets", "tokens", "componentDefinitions", "componentBindings", "pages"}
    if not required.issubset(document) or not isinstance(document["pages"], list) or not document["pages"]:
        raise InvalidRequestError("设计文档无效")
    for page in document["pages"]:
        nodes = page.get("nodes", {})
        root_id = page.get("rootId")
        root = nodes.get(root_id)
        if not root or root.get("kind") != "root" or root.get("parentId") is not None:
            raise InvalidRequestError("设计文档无效")
        visited: set[str] = set()

        def visit(node_id: str, parent_id: str | None, nodes: dict[str, Any] = nodes, visited: set[str] = visited) -> None:
            if node_id in visited or node_id not in nodes:
                raise InvalidRequestError("设计文档无效")
            node = nodes[node_id]
            if node.get("parentId") != parent_id:
                raise InvalidRequestError("设计文档无效")
            visited.add(node_id)
            children = node.get("childIds", [])
            if len(children) != len(set(children)):
                raise InvalidRequestError("设计文档无效")
            for child_id in children:
                visit(child_id, node_id)

        visit(root_id, None)
        if len(visited) != len(nodes):
            raise InvalidRequestError("设计文档无效")
    if document["version"] != "1.0.0":
        document["version"] = "1.0.0"
        return {"original_version": "1.0.0", "document": document, "warnings": [{"code": "migrated_version", "message": "文档已迁移到 1.0.0"}]}
    return {"original_version": "1.0.0", "document": document, "warnings": []}
