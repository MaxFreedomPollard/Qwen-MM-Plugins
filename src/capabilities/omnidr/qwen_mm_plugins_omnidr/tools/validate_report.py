"""Check report structure, citations, saved evidence, renderer integrity and accidental secret files."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..common import guarded, result_blocks


class ValidateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_dir: str
    stage: Literal["structure", "delivery"] = "delivery"


TOOL = {"name": "validate_omnidr_report", "args": ValidateArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Check report structure, citations, saved evidence, renderer integrity and accidental secret files.

    Args:
        project_dir: Report directory to validate; validation does not establish factual correctness.
        stage: Structure checks incremental edits; delivery also checks the research requirements, complete readings and review records.
    """
    from ..project import load_project, validate
    from ..report_health import report_health

    args = ValidateArgs.model_validate(arguments).model_dump()
    result = validate(**args)
    root, manifest, data = load_project(args["project_dir"])
    result["authoring_diagnostics"] = report_health(root, manifest, data)
    return result_blocks(result)
