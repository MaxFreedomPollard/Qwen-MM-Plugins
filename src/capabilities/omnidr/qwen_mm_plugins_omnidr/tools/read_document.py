"""Extract PDF text or render a bounded page range for visual inspection."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..common import guarded, result_blocks


class DocumentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str
    output_path: str
    start_page: int = Field(default=1, ge=1)
    end_page: int | None = Field(default=None, ge=1)
    render: bool = False


TOOL = {"name": "omnidr_read_document", "args": DocumentArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Extract PDF text or render a bounded page range for visual inspection.

    Args:
        file_path: Local PDF; download it first if it is remote.
        output_path: New text evidence file; rendered pages use this filename stem.
        start_page: First page, one-based.
        end_page: Last page; omitted reads remaining text pages, or ten pages with render=true.
        render: Also save page PNGs; inspect scanned text and figures with omnidr_read_media.
    """
    from shared.isolated_worker import run_isolated

    from ..common import InputError

    args = DocumentArgs.model_validate(arguments)
    if args.end_page is not None and (
        args.end_page < args.start_page or (args.render and args.end_page - args.start_page >= 20)
    ):
        raise InputError("Use ascending page ranges; render at most twenty pages per call.")
    return result_blocks(
        run_isolated("qwen_mm_plugins_omnidr.media", "read_pdf_worker", args.model_dump(), timeout=120)
    )
