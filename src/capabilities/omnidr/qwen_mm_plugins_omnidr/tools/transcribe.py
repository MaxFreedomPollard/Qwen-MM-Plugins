"""Transcribe one audio interval with source timestamps using the configured Omni model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..common import guarded, result_blocks


class TranscribeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str
    output_path: str
    start_time: float = Field(default=0, ge=0, allow_inf_nan=False)
    end_time: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    engine: Literal["auto", "shared"] = "auto"
    language: str | None = None
    initial_prompt: str | None = None


TOOL = {"name": "omnidr_transcribe", "args": TranscribeArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Transcribe one audio interval with source timestamps using the configured Omni model.

    Do not transcribe an interval already processed by omnidr_read_video; reuse its saved transcript.

    Args:
        file_path: Local audio or video source.
        output_path: New JSON evidence path; an adjacent .txt transcript is also written.
        start_time: First source second to transcribe.
        end_time: Last source second; each call is limited to 300 seconds.
        engine: Both auto and shared use the configured QWEN_MM_API_OMNI_MODEL.
        language: Optional language code.
        initial_prompt: Domain names and terms to preserve in the transcript.
    """
    from ..transcription import transcribe

    return result_blocks(transcribe(**TranscribeArgs.model_validate(arguments).model_dump()))
