"""Normalize Pydantic JSON Schema for OpenAI/LiteLLM strict structured outputs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from pydantic import BaseModel


def openai_strict_json_schema(schema: type[BaseModel]) -> dict[str, object]:
    """Build a JSON Schema that satisfies OpenAI strict structured-output rules.

    Every object must list all ``properties`` keys in ``required`` and set
    ``additionalProperties`` to false (including nested objects / ``$defs``).
    """
    raw = cast(dict[str, Any], deepcopy(schema.model_json_schema()))
    _normalize_object_node(raw)
    defs = raw.get("$defs")
    if isinstance(defs, dict):
        for node in defs.values():
            if isinstance(node, dict):
                _normalize_object_node(cast(dict[str, Any], node))
    return cast(dict[str, object], raw)


def _normalize_object_node(node: dict[str, Any]) -> None:
    props = node.get("properties")
    if isinstance(props, dict):
        node["additionalProperties"] = False
        node["required"] = list(props.keys())
        for child in props.values():
            if isinstance(child, dict):
                _normalize_object_node(cast(dict[str, Any], child))

    for key in ("anyOf", "oneOf", "allOf"):
        variants = node.get(key)
        if isinstance(variants, list):
            for variant in variants:
                if isinstance(variant, dict):
                    _normalize_object_node(cast(dict[str, Any], variant))

    items = node.get("items")
    if isinstance(items, dict):
        _normalize_object_node(items)
    elif isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                _normalize_object_node(cast(dict[str, Any], item))
