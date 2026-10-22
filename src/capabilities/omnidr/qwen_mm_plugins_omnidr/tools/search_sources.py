"""Discover external sources through public search pages or video platforms; snippets are not verified findings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..common import guarded, result_blocks


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = ""
    kind: Literal["web", "video", "image", "reverse"] = "web"
    count: int = Field(default=8, ge=1, le=20)
    site: str | None = None
    image_url: str | None = None
    backend: Literal["auto", "bing", "platform"] = "auto"
    market: str | None = None


TOOL = {"name": "omnidr_search", "args": SearchArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Discover external sources through public search pages or video platforms; snippets are not verified findings.

    Args:
        query: Search text describing the source or observed image contents.
        kind: Web, video or image keyword search. Reverse image search returns an unsupported-operation error.
        count: Maximum results.
        site: Optional public domain restriction, for example youtube.com or bilibili.com.
        image_url: Reserved for reverse image search, which is unavailable. Images are never uploaded implicitly.
        backend: Auto uses Bing; platform searches YouTube/Bilibili directly. No search API key is needed.
        market: Optional locale such as zh-CN or en-US.
    """
    from ..common import InputError
    from ..sources import search

    args = SearchArgs.model_validate(arguments)
    if args.kind != "reverse" and not args.query.strip():
        raise InputError("A nonempty search query is required.")
    return result_blocks(search(**args.model_dump()))
