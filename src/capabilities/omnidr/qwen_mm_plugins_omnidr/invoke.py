"""Run registered tools from the command line."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError


def main():
    from . import SPECS, get_handler

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=[s.name for s in SPECS])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--schema", action="store_true", help="Print the MCP input schema without running the tool")
    mode.add_argument(
        "--arguments-file",
        type=Path,
        help="JSON object containing tool arguments; credentials stay in external config",
    )
    args = parser.parse_args()
    spec = next(s for s in SPECS if s.name == args.tool)
    if args.schema:
        print(json.dumps(spec.meta, ensure_ascii=False))
        return 0
    arguments = json.loads(args.arguments_file.read_text())
    if not isinstance(arguments, dict):
        parser.error("arguments must be a JSON object")
    try:
        arguments = spec.args_model.model_validate(arguments).model_dump(exclude_none=True)
    except ValidationError as exc:
        fields = spec.args_model.model_fields
        errors = [
            {"field": e["loc"][0] if e["loc"] and e["loc"][0] in fields else "<unknown>", "error": e["type"]}
            for e in exc.errors(include_input=False, include_context=False, include_url=False)
        ]
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": "invalid_arguments",
                    "fields": errors,
                    "hint": "Use " + args.tool + " --schema to inspect argument names and types.",
                }
            )
        )
        return 1
    blocks = get_handler(args.tool)(arguments)
    failed = False
    for block in blocks:
        if block.get("type") == "text":
            print(block["text"])
            try:
                failed |= json.loads(block["text"]).get("status") in {"failed", "incomplete"}
            except (ValueError, AttributeError):
                pass
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
