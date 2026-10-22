"""Generate a local plugin that uses this checkout and Python environment."""

import argparse
import json
import os
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python", required=True, type=Path, help="Python executable in the environment with .[omnidr] installed"
    )
    parser.add_argument("--output", required=True, type=Path, help="New local plugin directory outside the checkout")
    args = parser.parse_args()
    cap = Path(__file__).resolve().parents[1]
    python = args.python.expanduser().absolute()  # Preserve the venv symlink, not its base interpreter.
    output = args.output.expanduser().absolute()
    if not python.is_file() or not os.access(python, os.X_OK):
        parser.error("--python must be an existing executable")
    if output.exists() or output.is_symlink():
        parser.error("--output already exists; choose a new directory")
    if output.resolve().is_relative_to(cap.parents[2]):
        parser.error("--output must be outside the repository")
    server = {"qwen-mm-plugins-omnidr": {"command": str(python), "args": [str(cap / "qwen_mm_plugins_omnidr")]}}
    output.mkdir(parents=True)
    for folder in ("skill", "agents", ".claude-plugin", ".codex-plugin", ".qoder-plugin"):
        shutil.copytree(cap / folder, output / folder)
    (output / ".mcp.json").write_text(json.dumps({"mcpServers": server}, indent=2) + "\n")
    manifest = output / ".claude-plugin/plugin.json"
    data = json.loads(manifest.read_text())
    data["mcpServers"] = server
    manifest.write_text(json.dumps(data, indent=2) + "\n")
    print(
        json.dumps(
            {
                "plugin_dir": str(output),
                "server": server,
                "note": "Keep this checkout and Python environment at their current paths; regenerate this copy after Skill/agent edits.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
