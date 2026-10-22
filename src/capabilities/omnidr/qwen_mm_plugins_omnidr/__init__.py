"""Omni Deep Research: evidence tools and an interactive video report workflow."""

from mcp_framework import build_registry

__version__ = "1.0.0"

SPECS, get_handler, list_tools = build_registry(__name__, ["tools"])

SYSTEM_DEPS = [
    {"label": "video probing and extraction", "tools": ["ffmpeg"], "hint": "apt install ffmpeg | brew install ffmpeg"},
    {"label": "media metadata", "tools": ["ffprobe"], "hint": "apt install ffmpeg | brew install ffmpeg"},
    {"label": "report validation", "tools": ["node"], "hint": "Install Node.js 22 or newer"},
    {
        "label": "browser screenshots",
        "tools": ["__playwright_chromium__"],
        "hint": "playwright install chromium (or install system Chromium)",
        "startup": False,
    },
]

USAGE_NOTE = (
    "The host agent conducts the research; tools return evidence and manage local reports. "
    "Configure DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, and QWEN_MM_API_OMNI_MODEL for media and page understanding. "
    "Public web and platform search need no additional API keys."
)
