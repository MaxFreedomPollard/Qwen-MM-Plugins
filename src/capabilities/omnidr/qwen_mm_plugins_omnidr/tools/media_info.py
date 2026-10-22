"""Probe local video or audio before planning research ranges."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..common import guarded, result_blocks


class InfoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str


TOOL = {"name": "omnidr_media_info", "args": InfoArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Probe local video or audio before planning research ranges.

    Args:
        file_path: Existing local audio or video file.
    """
    from ..common import local_file
    from ..project import probe

    return result_blocks(probe(local_file(InfoArgs.model_validate(arguments).file_path)))
