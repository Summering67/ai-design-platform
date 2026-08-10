from __future__ import annotations

from typing import Any

from ..contracts import validate_initial_ui_document, validate_tree


def compile_initial_ui_document(
    initial: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    validate_initial_ui_document(initial, contract)
    profile = contract["profile"]
    components = {
        key: {
            "id": value.get("id", key),
            **({"slots": value["slots"]} if isinstance(value.get("slots"), dict) else {}),
        }
        for key, value in contract.get("components", {}).items()
        if isinstance(value, dict)
    }

    def convert(node: dict[str, Any]) -> dict[str, Any]:
        result = {
            key: node[key]
            for key in (
                "id",
                "kind",
                "name",
                "tag",
                "packageName",
                "defaultModule",
                "style",
                "props",
                "tokens",
                "text",
                "assetId",
                "alt",
            )
            if key in node
        }
        result["children"] = [convert(child) for child in node["children"]]
        return result

    document = {
        "$schema": "https://ai-design-platform.dev/schema/v2/design-document.schema.json",
        "version": "2.0.0",
        "id": initial["id"],
        "name": initial["name"],
        "designSystem": {
            "id": profile["id"],
            "version": profile["version"],
            "digest": profile["digest"],
            "tokens": {token: token for token in contract.get("tokens", [])},
            "components": components,
            "allowedTags": sorted(
                set(components) | {"div", "span", "img", "h1", "p", "main", "section", "form"}
            ),
        },
        "assets": initial["assets"],
        "root": convert(initial["root"]),
    }
    validate_tree(document, contract)
    return document
