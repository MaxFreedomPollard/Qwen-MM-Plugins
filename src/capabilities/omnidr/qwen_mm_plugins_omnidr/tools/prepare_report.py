"""Initialize a new portable video research report without overwriting an existing project."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..common import guarded, result_blocks


class PrepareArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_path: str
    output_dir: str
    title: str = "Omni Deep Research"
    language: Literal["zh", "en"] = "zh"
    theme: str = Field(default="t05", pattern=r"^t(?:0[1-9]|1[0-9]|20)$")


TOOL = {"name": "prepare_omnidr_report", "args": PrepareArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Initialize a new portable video research report without overwriting an existing project.

    Args:
        video_path: Existing local source video.
        output_dir: New report directory; it must not already exist.
        title: Display title for the report.
        language: Report language.
        theme: Bundled visual theme t01 through t20.
    """
    from ..project import prepare

    args = PrepareArgs.model_validate(arguments)
    return result_blocks(prepare(**args.model_dump()))
