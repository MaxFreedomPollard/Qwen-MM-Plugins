"""Save a web page, PDF or image as local evidence; readable pages also return bounded text."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..common import guarded, result_blocks


class FetchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    output_path: str
    engine: Literal["direct", "auto"] = "direct"
    answer: str | None = None
    max_bytes: int = Field(default=32 * 1024 * 1024, ge=1, le=128 * 1024 * 1024)


TOOL = {"name": "omnidr_fetch_source", "args": FetchArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Save a web page, PDF or image as local evidence; readable pages also return bounded text.

    Args:
        url: HTTP(S) source URL; model/search credentials are never forwarded to this website.
        output_path: New evidence path; direct HTML also saves full text at readable_path. Original bytes stay at path.
        engine: Direct and auto save original bytes; HTML also produces a full readable text file.
        answer: Optional question answered from the saved text through the configured model.
        max_bytes: Download size limit; oversized and failed downloads do not leave partial evidence.
    """
    from ..sources import fetch

    return result_blocks(fetch(**FetchArgs.model_validate(arguments).model_dump()))
