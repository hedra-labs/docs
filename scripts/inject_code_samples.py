#!/usr/bin/env python3
"""Inject SDK code samples into the v3 OpenAPI document as x-codeSamples.

Sources, per operation:
  - cURL        synthesized from the spec (server, method, path, minimal body)
  - Python      parsed from hedra-python's Fern-generated reference.md
  - TypeScript  parsed from hedra-node's Fern-generated reference.md
  - CLI         command + flags parsed from hedra-cli's reference.md (its
                `METHOD /path` lines join directly to spec operations), with
                JSON bodies synthesized from the spec

Mintlify renders x-codeSamples in place of its auto-generated examples, which
is why cURL is re-injected explicitly. An operation missing from an SDK's
reference.md (e.g. the SDK regen PR lags a model launch) just skips that
language — the spec sync must never be blocked on SDK freshness.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_SOURCES = {
    "python": "https://raw.githubusercontent.com/hedra-labs/hedra-python/main/reference.md",
    "node": "https://raw.githubusercontent.com/hedra-labs/hedra-node/main/reference.md",
    "cli": "https://raw.githubusercontent.com/hedra-labs/hedra-cli/main/reference.md",
}
NODE_PREAMBLE = (
    'import { HedraClient } from "hedra-node";\n'
    "\n"
    'const client = new HedraClient({ apiKey: "YOUR_API_KEY" });\n'
    "\n"
)
HTTP_METHODS = ("get", "put", "post", "delete", "patch")

SUMMARY_PATTERN = re.compile(
    r'<details><summary><code>client\.([\w.]+)\.<a href="[^"]*">(\w+)</a>'
)
CLI_COMMAND_PATTERN = re.compile(r"^#### `(hedra [^`]+)`$")
CLI_OPERATION_PATTERN = re.compile(r"^`([A-Z]+) (/\S+)`$")
CLI_FLAG_PATTERN = re.compile(r"^\| `(--[\w-]+)` \| `([^`]*)` \| (Yes|No) \|")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec",
        type=Path,
        default=REPOSITORY_ROOT / "openapi-v3.json",
    )
    for language, source in REFERENCE_SOURCES.items():
        parser.add_argument(
            f"--{language}-ref",
            default=source,
            help=f"Path or URL of the {language} SDK reference.md",
        )
    return parser.parse_args()


def load_text(source: str) -> str:
    if source.startswith(("https://", "http://")):
        with urlopen(source, timeout=30) as response:
            return response.read().decode("utf-8")
    return Path(source).read_text()


def normalize(name: str) -> str:
    return name.replace("_", "").replace(".", "").lower()


def parse_fern_reference(markdown: str, fence: str) -> dict[str, str]:
    """Map normalized `<group><method>` (and bare `<method>`) to snippets.

    Each Fern reference.md entry is a <details> block whose <summary> names the
    client accessor and method, followed by one usage snippet in a ```<fence>
    code block. Bare-method keys are registered because per-model submit
    operationIds (`submit_dreamina_31`) carry no group prefix; group-qualified
    keys win on collision.
    """
    snippets: dict[str, str] = {}
    bare: dict[str, str] = {}
    fence_open = f"```{fence}"
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        match = SUMMARY_PATTERN.search(lines[index])
        index += 1
        if not match:
            continue
        group, method = match.groups()
        while index < len(lines) and lines[index].strip() != fence_open:
            if SUMMARY_PATTERN.search(lines[index]):
                break
            index += 1
        if index >= len(lines) or lines[index].strip() != fence_open:
            continue
        index += 1
        code_lines: list[str] = []
        while index < len(lines) and lines[index].strip() != "```":
            code_lines.append(lines[index])
            index += 1
        code = "\n".join(code_lines).strip() + "\n"
        snippets.setdefault(normalize(group + method), code)
        bare.setdefault(normalize(method), code)
    for key, code in bare.items():
        snippets.setdefault(key, code)
    return snippets


def transform_python(code: str) -> str:
    code = code.replace("from hedra.environment import HedraEnvironment\n", "")
    code = code.replace(
        'client = Hedra(\n    api_key="<token>",\n    environment=HedraEnvironment.PRODUCTION,\n)',
        'client = Hedra(api_key="YOUR_API_KEY")',
    )
    # Fallback if the constructor shape ever changes upstream.
    code = code.replace("\n    environment=HedraEnvironment.PRODUCTION,", "")
    return code.replace('"<token>"', '"YOUR_API_KEY"')


def transform_node(code: str) -> str:
    return NODE_PREAMBLE + code.replace('"<token>"', '"YOUR_API_KEY"')


def parse_cli_reference(markdown: str) -> dict[tuple[str, str], dict[str, Any]]:
    """Map (METHOD, path) to the CLI command and its required flags."""
    commands: dict[tuple[str, str], dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    for line in markdown.splitlines():
        command_match = CLI_COMMAND_PATTERN.match(line)
        if command_match:
            current = {"command": command_match.group(1), "flags": []}
            continue
        if current is None:
            continue
        operation_match = CLI_OPERATION_PATTERN.match(line)
        if operation_match and "key" not in current:
            current["key"] = (operation_match.group(1), operation_match.group(2))
            commands[current["key"]] = current
            continue
        flag_match = CLI_FLAG_PATTERN.match(line)
        if flag_match and flag_match.group(3) == "Yes":
            current["flags"].append((flag_match.group(1), flag_match.group(2)))
    return commands


def resolve_ref(schema: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        target: Any = document
        for part in schema["$ref"].lstrip("#/").split("/"):
            target = target[part]
        schema = target
    return schema


def example_from_schema(
    schema: dict[str, Any], document: dict[str, Any], depth: int = 0, hint: str = ""
) -> Any:
    """Minimal example value: required fields only, first enum/oneOf option."""
    if depth > 8:
        return None
    schema = resolve_ref(schema, document)
    if "example" in schema:
        return schema["example"]
    if "default" in schema and schema["default"] is not None:
        return schema["default"]
    if "const" in schema:
        return schema["const"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    # Combinators can sit beside plain properties (e.g. an allOf carrying an
    # if/then conditional), so their contribution merges with the object branch
    # below rather than short-circuiting it.
    combined: dict[str, Any] = {}
    for combinator in ("allOf", "oneOf", "anyOf"):
        if combinator in schema and schema[combinator]:
            options = schema[combinator] if combinator == "allOf" else schema[combinator][:1]
            for option in options:
                value = example_from_schema(option, document, depth + 1, hint)
                if isinstance(value, dict):
                    combined.update(value)
                elif value is not None and "properties" not in schema:
                    return value
    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema or combined:
        properties = schema.get("properties", {})
        # Required fields only; a body with none required falls back to every
        # top-level property so the sample is never an unhelpful bare `{}`.
        names = schema.get("required") or (list(properties) if depth == 0 else [])
        own = {
            name: example_from_schema(properties[name], document, depth + 1, name)
            for name in names
            if name in properties
        }
        return {**combined, **own}
    if schema_type == "array":
        item = example_from_schema(schema.get("items", {}), document, depth + 1, hint)
        return [item] if item is not None else []
    if schema_type == "integer":
        return schema.get("minimum", 1)
    if schema_type == "number":
        return schema.get("minimum", 1.0)
    if schema_type == "boolean":
        return True
    if schema_type == "string":
        string_format = schema.get("format")
        if string_format == "date-time":
            return "2026-01-01T00:00:00Z"
        if string_format == "uri":
            return "https://example.com"
        return hint or "..."
    return None


def json_body_example(operation: dict[str, Any], document: dict[str, Any]) -> str | None:
    content = operation.get("requestBody", {}).get("content", {})
    if "application/json" not in content:
        return None
    schema = content["application/json"].get("schema", {})
    example = example_from_schema(schema, document)
    if not isinstance(example, dict):
        return None
    return json.dumps(example, indent=2)


def build_curl(
    method: str, path: str, operation: dict[str, Any], document: dict[str, Any]
) -> str:
    server = document.get("servers", [{}])[0].get("url", "https://api.hedra.com/v3")
    lines = [f'curl "{server}{path}"' if method == "get" else f'curl -X {method.upper()} "{server}{path}"']
    lines.append('  -H "Authorization: Bearer $HEDRA_API_KEY"')
    content = operation.get("requestBody", {}).get("content", {})
    if "multipart/form-data" in content:
        schema = resolve_ref(content["multipart/form-data"].get("schema", {}), document)
        for name in schema.get("required", []):
            field = resolve_ref(schema.get("properties", {}).get(name, {}), document)
            if field.get("format") == "binary":
                lines.append(f'  -F "{name}=@/path/to/{name}"')
            else:
                lines.append(f'  -F "{name}=..."')
    else:
        body = json_body_example(operation, document)
        if body is not None:
            lines.append('  -H "Content-Type: application/json"')
            lines.append(f"  -d '{body}'")
    return " \\\n".join(lines) + "\n"


def build_cli(
    entry: dict[str, Any], operation: dict[str, Any], document: dict[str, Any]
) -> str:
    parts = [entry["command"]]
    content = operation.get("requestBody", {}).get("content", {})
    multipart = "multipart/form-data" in content
    if multipart:
        # The generated flag table says `--json`, but the CLI takes the form
        # fields directly (`hedra files upload --file ./headshot.png`).
        schema = resolve_ref(content["multipart/form-data"].get("schema", {}), document)
        for name in schema.get("required", []):
            field = resolve_ref(schema.get("properties", {}).get(name, {}), document)
            value = f"./path/to/{name}" if field.get("format") == "binary" else "..."
            parts.append(f"--{name.replace('_', '-')} {value}")
    for flag, _flag_type in entry["flags"]:
        if flag == "--json":
            if multipart:
                continue
            body = json_body_example(operation, document) or "{}"
            parts.append(f"--json '{body}'")
        else:
            parts.append(f"{flag} {flag.lstrip('-').replace('-', '_')}")
    return " \\\n  ".join(parts) + "\n"


def main() -> None:
    args = parse_args()
    document = json.loads(args.spec.read_text())

    references: dict[str, Any] = {}
    for language in REFERENCE_SOURCES:
        source = getattr(args, f"{language}_ref")
        try:
            references[language] = load_text(source)
        except Exception as error:  # noqa: BLE001 - sync must survive SDK-repo hiccups
            print(f"warning: could not load {language} reference ({error}); "
                  f"skipping {language} samples", file=sys.stderr)
            references[language] = None

    python_snippets = (
        parse_fern_reference(references["python"], "python")
        if references["python"] else {}
    )
    node_snippets = (
        parse_fern_reference(references["node"], "typescript")
        if references["node"] else {}
    )
    cli_commands = (
        parse_cli_reference(references["cli"]) if references["cli"] else {}
    )

    counts = {"curl": 0, "python": 0, "node": 0, "cli": 0}
    missing: dict[str, list[str]] = {"python": [], "node": [], "cli": []}
    for path, path_item in document.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            operation_id = operation.get("operationId", "")
            key = normalize(operation_id)
            samples = [
                {
                    "lang": "bash",
                    "label": "cURL",
                    "source": build_curl(method, path, operation, document),
                }
            ]
            counts["curl"] += 1
            if key in python_snippets:
                samples.append({
                    "lang": "python",
                    "label": "hedra-python",
                    "source": transform_python(python_snippets[key]),
                })
                counts["python"] += 1
            elif references["python"]:
                missing["python"].append(operation_id)
            if key in node_snippets:
                samples.append({
                    "lang": "typescript",
                    "label": "hedra-node",
                    "source": transform_node(node_snippets[key]),
                })
                counts["node"] += 1
            elif references["node"]:
                missing["node"].append(operation_id)
            cli_entry = cli_commands.get((method.upper(), path))
            if cli_entry:
                samples.append({
                    "lang": "bash",
                    "label": "Hedra CLI",
                    "source": build_cli(cli_entry, operation, document),
                })
                counts["cli"] += 1
            elif references["cli"]:
                missing["cli"].append(operation_id)
            operation["x-codeSamples"] = samples

    args.spec.write_text(json.dumps(document, indent=2) + "\n")
    print(f"x-codeSamples injected: {counts}")
    for language, operations in missing.items():
        if operations:
            print(
                f"warning: no {language} sample for {len(operations)} operation(s): "
                + ", ".join(operations),
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
