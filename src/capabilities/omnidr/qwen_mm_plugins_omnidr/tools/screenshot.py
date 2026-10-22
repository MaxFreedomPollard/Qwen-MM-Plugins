"""Capture page evidence or inspect the rendered local report."""

from pydantic import BaseModel, ConfigDict

from shared.isolated_worker import run_isolated

from ..common import InputError, guarded, local_file, new_output, public_url, result_blocks


class ScreenshotArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    output_path: str


TOOL = {"name": "omnidr_screenshot", "args": ScreenshotArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Capture an HTTP(S) page or local HTML report using an isolated browser.

    Requires installed Chromium, either system-wide or through playwright install chromium.
    It uses a fresh browser context without importing cookies or browser profiles.

    Args:
        source: Public page URL or local HTML file path.
        output_path: New PNG path for visual evidence or report review.
    """
    args = ScreenshotArgs.model_validate(arguments)
    # Validate before RPC replaces input errors with IsolatedWorkerError.
    if args.source.startswith(("https://", "http://")):
        public_url(args.source)
    else:
        local_file(args.source)
    output = new_output(args.output_path)
    if output.suffix.lower() != ".png":
        raise InputError("Screenshot output must use .png.")
    return result_blocks(
        run_isolated("qwen_mm_plugins_omnidr.browser", "screenshot_worker", args.model_dump(), timeout=120)
    )
