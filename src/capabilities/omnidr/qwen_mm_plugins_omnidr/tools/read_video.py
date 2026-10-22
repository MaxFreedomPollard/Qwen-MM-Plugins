"""Read every 300-second interval with concurrent dense visual captions and one ASR pass."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..common import guarded, result_blocks


class VideoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str
    output_dir: str
    start_time: float = Field(default=0, ge=0, allow_inf_nan=False)
    end_time: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    question: str = ""
    language: str | None = None
    jobs: int = Field(default=8, ge=1, le=16)
    frames: int = Field(default=32, ge=16, le=48)
    frame_height: Literal[320, 480] = 320


TOOL = {"name": "omnidr_read_video", "args": VideoArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Read every 300-second interval with concurrent dense visual captions and one ASR pass.

    Successful saved passes are reused on resume; failed passes leave explicit gaps.
    Returns artifact paths, not raw frames or complete transcripts. A reader must reconcile the results.

    Args:
        file_path: Local video to inspect visually and transcribe.
        output_dir: Dedicated evidence directory inside the report; reuse it only for the same source/range.
        start_time: Source start, for one job from omnidr_plan_video or a full-video pass.
        end_time: Source end; omission covers the full remainder.
        question: Visual research focus. ASR transcribes independently of this question.
        language: Optional ASR language hint; otherwise detect it.
        jobs: Maximum concurrent visual/ASR requests; lower for provider quotas.
        frames: Samples per new visual pass; use up to 48 for fast cuts. Saved passes are reused.
        frame_height: Maximum height; use 480 for OCR. Saved passes keep their original detail.
    """
    from ..reading import read_video

    return result_blocks(read_video(**VideoArgs.model_validate(arguments).model_dump()))
