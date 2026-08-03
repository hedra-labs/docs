#!/usr/bin/env python3
"""Regenerate the v3 API Reference navigation in docs.json from openapi-v3.json.

Mintlify's OpenAPI auto-population sorts tag groups alphabetically, so the
reference navigation is written out explicitly instead. Groups follow the order
of the spec's top-level ``tags`` array (which ``sync_openapi.py`` orders via
the ``x-tag-order`` override); operations keep the spec's path order.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
HTTP_METHODS = ("get", "post", "put", "patch", "delete")
OPENAPI_SOURCE = "/openapi-v3.json"
OPENAPI_DIRECTORY = "api-reference/v3"
PRODUCT_NAME = "Developer platform"
GROUP_NAME = "API Reference"
WEBHOOK_TAG = "Webhooks"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=REPOSITORY_ROOT / "openapi-v3.json")
    parser.add_argument("--docs", type=Path, default=REPOSITORY_ROOT / "docs.json")
    return parser.parse_args()


def build_reference_group(spec: dict[str, Any]) -> dict[str, Any]:
    pages_by_tag: dict[str, list[str]] = {}
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method not in HTTP_METHODS:
                continue
            tags = operation.get("tags")
            if not tags:
                raise ValueError(f"Untagged operation: {method.upper()} {path}")
            pages_by_tag.setdefault(tags[0], []).append(f"{method.upper()} {path}")

    for name in spec.get("webhooks", {}):
        pages_by_tag.setdefault(WEBHOOK_TAG, []).append(f"WEBHOOK {name}")

    ordered_names = [tag["name"] for tag in spec.get("tags", [])]
    ordered_names += sorted(set(pages_by_tag) - set(ordered_names))

    return {
        "group": GROUP_NAME,
        "openapi": {"source": OPENAPI_SOURCE, "directory": OPENAPI_DIRECTORY},
        "pages": [
            {"group": name, "pages": pages_by_tag[name]}
            for name in ordered_names
            if name in pages_by_tag
        ],
    }


def main() -> None:
    args = parse_args()
    spec = json.loads(args.spec.read_text())
    docs = json.loads(args.docs.read_text())

    for product in docs["navigation"]["products"]:
        if product.get("product") != PRODUCT_NAME:
            continue
        for index, group in enumerate(product["groups"]):
            if group.get("group") == GROUP_NAME:
                product["groups"][index] = build_reference_group(spec)
                break
        else:
            raise ValueError(f"No {GROUP_NAME!r} group in {PRODUCT_NAME!r}")
        break
    else:
        raise ValueError(f"No {PRODUCT_NAME!r} product in docs.json")

    args.docs.write_text(json.dumps(docs, indent=2) + "\n")


if __name__ == "__main__":
    main()
