"""Download one related video through Bilibili API/DASH or yt-dlp; cookies are optional external files and never bundled."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..common import guarded, result_blocks


class DownloadArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    output_path: str
    cookies_file: str | None = None
    page: int = Field(default=1, ge=1)
    quality: int = Field(default=64, ge=16, le=120)


TOOL = {"name": "omnidr_download_video", "args": DownloadArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Download one related video through Bilibili API/DASH or yt-dlp; cookies are optional external files and never bundled.

    Args:
        url: Canonical video page URL, not a search-results page.
        output_path: New local MP4 path inside the report.
        cookies_file: Optional external Netscape cookie file, used only when explicitly supplied. Contents are never returned.
        page: Bilibili part number; an explicit p= in the URL takes precedence.
        quality: Bilibili target quality code, default 64 (720p), bounded by account access.
    """
    from ..sources import download_video

    return result_blocks(download_video(**DownloadArgs.model_validate(arguments).model_dump()))
