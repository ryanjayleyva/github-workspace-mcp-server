#!/usr/bin/env python3
"""Validate the n8n workflow JSON for structural sanity."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "workflow" / "github-workspace-mcp-server.json"


def as_dict(value: object) -> dict[str, object] | None:
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def as_list(value: object) -> list[object] | None:
    if isinstance(value, list):
        return cast("list[object]", value)
    return None


def node_label(node: dict[str, object], index: int) -> str:
    name = node.get("name")
    return name if isinstance(name, str) and name else f"node #{index}"


def check_top_level(data: dict[str, object], errors: list[str]) -> None:
    name = data.get("name")
    if not isinstance(name, str) or not name:
        errors.append("top level 'name' is missing or empty")
    nodes = as_list(data.get("nodes"))
    if not nodes:
        errors.append("top level 'nodes' must be a non empty list")
    if as_dict(data.get("connections")) is None:
        errors.append("top level 'connections' must be an object")


def check_node(node: dict[str, object], index: int, errors: list[str]) -> None:
    label = node_label(node, index)
    for key in ("id", "name", "type"):
        value = node.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"{label}: missing or empty field '{key}'")
    position = as_list(node.get("position"))
    valid = (
        position is not None
        and len(position) == 2
        and all(isinstance(v, (int, float)) for v in position)
    )
    if not valid:
        errors.append(f"{label}: 'position' must be two numbers")


def check_unique(nodes: list[object], errors: list[str]) -> set[str]:
    """Flag duplicate ids and names; return the unique node names."""
    ids: dict[str, list[str]] = {}
    names: dict[str, list[str]] = {}
    for index, item in enumerate(nodes):
        node = as_dict(item)
        if node is None:
            continue
        label = node_label(node, index)
        node_id = node.get("id")
        if isinstance(node_id, str):
            ids.setdefault(node_id, []).append(label)
        node_name = node.get("name")
        if isinstance(node_name, str):
            names.setdefault(node_name, []).append(label)

    for node_id, labels in ids.items():
        if len(labels) > 1:
            errors.append(f"duplicate node id {node_id} in {labels}")
    for node_name, labels in names.items():
        if len(labels) > 1:
            message = f"duplicate node name '{node_name}'"
            errors.append(f"{message} used {len(labels)} times")
    return set(names)


def is_trigger(node: dict[str, object]) -> bool:
    node_type = node.get("type")
    return isinstance(node_type, str) and "mcpTrigger" in node_type


def check_trigger(nodes: list[object], errors: list[str]) -> None:
    triggers: list[dict[str, object]] = []
    for item in nodes:
        node = as_dict(item)
        if node is not None and is_trigger(node):
            triggers.append(node)
    if len(triggers) != 1:
        message = "expected exactly one mcpTrigger node"
        errors.append(f"{message}, found {len(triggers)}")


def check_connections(
    connections: dict[str, object],
    node_names: set[str],
    errors: list[str],
) -> None:
    for source, raw_channels in connections.items():
        if source not in node_names:
            errors.append(f"unknown source node '{source}'")
        channels = as_dict(raw_channels)
        if channels is None:
            continue
        for channel, raw_groups in channels.items():
            groups = as_list(raw_groups)
            if groups is None:
                continue
            for raw_group in groups:
                group = as_list(raw_group)
                if group is None:
                    continue
                for raw_link in group:
                    link = as_dict(raw_link)
                    if link is None:
                        continue
                    target = link.get("node")
                    if not isinstance(target, str) or target not in node_names:
                        message = f"connection from '{source}'"
                        errors.append(f"{message} ({channel}) -> '{target}'")


def load_workflow() -> object | None:
    """Print FAIL and return None when the file cannot be read or parsed."""
    try:
        text = WORKFLOW.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"FAIL: cannot read workflow -> {exc}")
        return None
    try:
        return cast("object", json.loads(text))
    except json.JSONDecodeError as exc:
        print(f"FAIL: workflow is not valid JSON -> {exc}")
        return None


def main() -> int:
    if not WORKFLOW.exists():
        print(f"FAIL: workflow file not found at {WORKFLOW}")
        return 1

    parsed = load_workflow()
    if parsed is None:
        return 1
    data = as_dict(parsed)
    if data is None:
        print("FAIL: workflow root must be a JSON object")
        return 1

    errors: list[str] = []
    check_top_level(data, errors)

    nodes = as_list(data.get("nodes"))
    if nodes is None:
        nodes = []
    for index, item in enumerate(nodes):
        node = as_dict(item)
        if node is None:
            errors.append(f"node #{index} must be an object")
            continue
        check_node(node, index, errors)

    check_trigger(nodes, errors)
    node_names = check_unique(nodes, errors)

    connections = as_dict(data.get("connections"))
    if connections is not None:
        check_connections(connections, node_names, errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print(f"OK: {WORKFLOW.name} is a valid workflow with {len(nodes)} nodes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
