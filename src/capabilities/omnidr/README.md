# Omni Deep Research

Research a video with Claude Code or Codex: understand visuals and speech, investigate external documents and related videos, and produce an interactive report with timestamps, images, and citations.

## Setup

Requires Python 3.10+, FFmpeg with `libx264`, ffprobe, Node.js 22+, and a configured Claude Code or Codex host. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[omnidr]'
.venv/bin/playwright install chromium
```

Add the following to `~/.qwen-mm-plugins/config`. These settings control media understanding and transcription; the host's main model is configured separately. Public search needs no API key.

```dotenv
DASHSCOPE_API_KEY=<your-api-key>
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MM_API_OMNI_MODEL=qwen3.8-omni-flash
```

## Claude Code

Generate a local plugin copy, then launch Claude Code:

```bash
.venv/bin/python src/capabilities/omnidr/qwen_mm_plugins_omnidr/local_plugin.py \
  --python "$PWD/.venv/bin/python" --output /tmp/qwen-omnidr-plugin
claude --plugin-dir /tmp/qwen-omnidr-plugin
```

Use a new output directory for each plugin copy. Regenerate it after Skill edits; keep the checkout and Python environment in place.

## Codex

Register the tools and link the Skill from the repository root:

```bash
codex mcp add qwen-mm-plugins-omnidr -- \
  "$PWD/.venv/bin/python" "$PWD/src/capabilities/omnidr/qwen_mm_plugins_omnidr"
mkdir -p .agents/skills
ln -s "$PWD/src/capabilities/omnidr/skill" .agents/skills/qwen-mm-plugins-omnidr
codex
```

## Usage

Provide a local video or downloadable video URL, a question, and a new report directory:

```text
Use qwen-mm-plugins-omnidr to research /path/to/video.mp4.
Explain the demonstrated method, compare alternatives, and verify its main claims.
Write an English report in /path/to/report/.
```

To resume, provide the existing report directory and original question. See the [research Skill](skill/SKILL.md) for the workflow and completion requirements. Unavailable sources and incomplete readings remain explicit gaps.
