"""Isolated browser screenshots for source evidence and local report review."""

from __future__ import annotations

from shared.syscmd import which_tool

from .common import InputError, local_file, new_output, public_url


def screenshot_worker(arguments: dict) -> dict:
    from playwright.sync_api import sync_playwright

    source = arguments["source"]
    url = public_url(source) if source.startswith(("https://", "http://")) else local_file(source).as_uri()
    output = new_output(arguments["output_path"])
    if output.suffix.lower() != ".png":
        raise InputError("Screenshot output must use .png.")
    executable = which_tool("chromium") or which_tool("chromium-browser") or which_tool("google-chrome")
    with sync_playwright() as playwright:
        options = {"headless": True}
        if executable:
            options["executable_path"] = executable
        try:
            browser = playwright.chromium.launch(**options)
        except Exception as exc:
            detail = str(exc)
            if "Operation not permitted" in detail or "No usable sandbox" in detail:
                return {
                    "status": "failed",
                    "error": "Browser launch was blocked by the host sandbox. Use an authorized browser environment.",
                }
            if "Executable doesn't exist" in detail:
                return {"status": "failed", "error": "Chromium is missing. Run playwright install chromium."}
            raise
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda _: errors.append("A page script raised an error."))
            page.goto(url, wait_until="load", timeout=45000)
            page.screenshot(path=str(output), full_page=True, timeout=30000)
            return {
                "status": "captured",
                "path": str(output),
                "page_errors": errors,
                "next_step": "Inspect the screenshot; a saved image alone does not establish visual correctness.",
            }
        finally:
            browser.close()
