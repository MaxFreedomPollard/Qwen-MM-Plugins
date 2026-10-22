"""Extract a sharp representative video frame and optionally crop a visual research anchor."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..common import guarded, result_blocks


class FrameArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_path: str
    timestamp: float = Field(ge=0, allow_inf_nan=False)
    output_path: str
    box: list[float] | None = Field(default=None, min_length=4, max_length=4)
    window: float | None = Field(default=None, ge=0, le=10)
    candidates: int = Field(default=9, ge=1, le=25)
    exact: bool = False
    box_units: Literal["normalized", "pixels"] = "normalized"


TOOL = {"name": "omnidr_extract_frame", "args": FrameArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Extract a sharp frame/crop; preserve the returned metadata_path with the report.

    Args:
        video_path: Local source video.
        timestamp: Source timestamp in seconds.
        output_path: New PNG or JPEG path inside the report.
        box: Optional [left, top, right, bottom] crop on the displayed image; crops default to an exact frame.
        window: Candidate time span, default 0.8 seconds for whole frames and zero for crops.
        candidates: Frames to score for sharpness and fading inside the time window.
        exact: Force the requested timestamp, disabling the search window.
        box_units: Normalized uses 0–1000 coordinates; pixels uses native image coordinates.
    """
    from ..media import extract_frame

    return result_blocks(extract_frame(**FrameArgs.model_validate(arguments).model_dump()))
