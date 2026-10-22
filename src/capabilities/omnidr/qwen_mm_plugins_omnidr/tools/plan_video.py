"""Plan source-aligned jobs of at most 300 seconds, avoiding orphan subsecond tails."""

from pydantic import BaseModel, ConfigDict, Field

from ..common import guarded, result_blocks


class PlanArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str
    start_time: float = Field(default=0, ge=0, allow_inf_nan=False)
    end_time: float | None = Field(default=None, gt=0, allow_inf_nan=False)


TOOL = {"name": "omnidr_plan_video", "args": PlanArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Plan source-aligned jobs of at most 300 seconds, avoiding orphan subsecond tails.

    Args:
        file_path: Local source or related video.
        start_time: First source second to inspect.
        end_time: Last source second; defaults to the whole video.
    """
    from ..reading import plan

    return result_blocks(plan(**PlanArgs.model_validate(arguments).model_dump()))
