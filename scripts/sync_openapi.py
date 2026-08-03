#!/usr/bin/env python3
"""Sync the public v2 OpenAPI document and apply docs-only annotations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.request import urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = "https://api.hedra.com/public/openapi.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument(
        "--overrides",
        type=Path,
        default=REPOSITORY_ROOT / "openapi-overrides.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "openapi.json",
    )
    return parser.parse_args()


def load_source(source: str) -> dict[str, Any]:
    if source.startswith(("https://", "http://")):
        with urlopen(source, timeout=30) as response:
            document = json.load(response)
    else:
        with Path(source).open() as source_file:
            document = json.load(source_file)

    if not isinstance(document, dict):
        raise ValueError("OpenAPI source must contain a JSON object")
    if not str(document.get("openapi", "")).startswith("3."):
        raise ValueError("OpenAPI source must use OpenAPI 3")
    if not isinstance(document.get("paths"), dict) or not document["paths"]:
        raise ValueError("OpenAPI source must contain at least one path")
    return document


def merge(target: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge(target[key], value)
        else:
            target[key] = value


def apply_tag_order(document: dict[str, Any], order: list[str]) -> None:
    """Reorder the top-level tags array without pinning upstream tag content.

    Tags named in ``order`` come first, in that order; tags the source adds
    later keep their relative order after them.
    """
    tags = document.get("tags")
    if not isinstance(tags, list):
        return
    rank = {name: index for index, name in enumerate(order)}
    tags.sort(key=lambda tag: rank.get(tag.get("name"), len(order)))


def main() -> None:
    args = parse_args()
    document = load_source(args.source)

    with args.overrides.open() as overrides_file:
        overrides = json.load(overrides_file)
    if not isinstance(overrides, dict):
        raise ValueError("OpenAPI overrides must contain a JSON object")

    tag_order = overrides.pop("x-tag-order", None)
    merge(document, overrides)
    if tag_order is not None:
        if not isinstance(tag_order, list) or not all(
            isinstance(name, str) for name in tag_order
        ):
            raise ValueError("x-tag-order must be a list of tag names")
        apply_tag_order(document, tag_order)
    args.output.write_text(json.dumps(document, indent=2) + "\n")


if __name__ == "__main__":
    main()
