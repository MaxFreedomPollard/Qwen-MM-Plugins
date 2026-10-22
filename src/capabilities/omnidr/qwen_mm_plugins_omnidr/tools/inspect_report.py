"""Inspect saved report data and evidence counts without making model calls."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..common import InputError, guarded, result_blocks


class InspectArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_dir: str
    review_location: str | None = None


TOOL = {"name": "inspect_omnidr_report", "args": InspectArgs}


@guarded
def handle(arguments: dict) -> list[dict]:
    """Inspect saved report data and evidence counts without making model calls.

    Args:
        project_dir: Existing OmniDR report directory.
        review_location: Return only this claim and cited URLs for an isolated reviewer, e.g. insights/0.
    """
    from ..audit import claim_records
    from ..project import load_project
    from ..report_health import report_health

    root, manifest, data = load_project(arguments["project_dir"])
    if (location := arguments.get("review_location")) is not None:
        record = next((c for c in claim_records(data, include_payload=True) if c["location"] == location), None)
        if record is None:
            raise InputError("No compare/timeliness claim exists at review_location; inspect current claim locations.")
        urls = {s.get("id"): s.get("url") for s in data.get("research", []) if isinstance(s, dict)}
        return result_blocks(
            {
                "status": "review_brief",
                **record,
                "cited_urls": [{"id": sid, "url": urls.get(sid)} for sid in record["sources"]],
            }
        )
    return result_blocks(
        {
            "status": "inspected",
            "validation": "not_run",
            "claims_for_review": claim_records(data),
            "project_dir": str(root),
            "duration": manifest["duration"],
            "segments": len(data.get("segments", [])),
            "sources": len(data.get("research", [])),
            "authoring_diagnostics": report_health(root, manifest, data),
            "next_step": "Inspect does not determine completion. Run validate_omnidr_report on the current files.",
        }
    )
