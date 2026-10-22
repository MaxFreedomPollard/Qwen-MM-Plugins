"""Bounded, read-only authoring diagnostics; no media/model calls or evidence repairs."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from itertools import chain
from pathlib import Path

from .audit import claim_records
from .project import contained_file, frame_metadata_path, sha256


def objects(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def strings(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def saved_json(root, relative):
    if not isinstance(relative, str):
        return {}
    path = contained_file(root, relative)
    if path is None or path.stat().st_size > 1024 * 1024:
        return {}
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def visible_strings(value):
    """Exclude source catalog summaries, evidence quotes and planning-only metadata."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from visible_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in {
                "title",
                "text",
                "body",
                "videoClaim",
                "currentFact",
                "cap",
                "table",
                "steps",
                "root",
                "branches",
                "label",
                "items",
                "headers",
                "rows",
            }:
                yield from visible_strings(item)


def evidence_handoffs(root: Path) -> dict:
    """Index saved reader notes; recorded handling never proves factual support."""
    records = {
        item.get("path"): item
        for item in objects(saved_json(root, "_work/synthesis.json").get("handoffs"))
        if isinstance(item.get("path"), str)
    }
    notes, scanned, truncated = [], 0, False
    for folder in ("anchors", "docs", "videos", "source"):
        directory = root / "_work" / folder
        if directory.is_symlink() or not directory.resolve().is_relative_to(root):
            continue
        for candidate in chain(directory.rglob("*notes.*"), directory.rglob("*findings.*")):
            if scanned >= 200:
                truncated = True
                break
            scanned += 1
            if candidate.suffix not in {".md", ".txt", ".json"} or not re.search(
                r"(?:^|[-_])(?:notes|findings)$", candidate.stem
            ):
                continue
            relative = str(candidate.relative_to(root))
            path = contained_file(root, relative)
            if path is None or path.stat().st_size > 1024 * 1024:
                continue
            digest = sha256(path)
            record = records.get(relative, {})
            disposition = record.get("disposition")
            status = "unrecorded"
            if disposition in {"integrated", "out_of_scope", "blocked"}:
                status = "recorded" if record.get("notes_sha256") == digest else "notes_changed"
            notes.append(
                {
                    "path": relative,
                    "notes_sha256": digest,
                    "bytes": path.stat().st_size,
                    "handling_status": status,
                    "declared_disposition": disposition,
                    "report_locations": strings(record.get("report_locations")),
                    "reason": record.get("reason") if isinstance(record.get("reason"), str) else None,
                }
            )
    return {
        "notes": notes,
        "scanned": scanned,
        "limit": 200,
        "truncated": truncated,
        "scope": "Saved reader handoffs, excluding independent review notes. Handling is author-declared; neither citations nor a recorded disposition prove evidence integration or factual support.",
    }


def report_health(root: Path, manifest: dict, data: dict) -> dict:
    ledger = saved_json(root, "_work/research-review.json")
    segments = objects(data.get("segments"))
    sources = objects(data.get("research"))
    insights = objects(data.get("insights")) + [i for s in segments for i in objects(s.get("insights"))]
    authored = [data.get("summary", ""), *insights]
    authored += [block for segment in segments for block in objects(segment.get("caption"))]
    inline = {sid for text in visible_strings(authored) for sid in re.findall(r"\[(S\d+)\]", text)}
    linked = inline | {sid for item in [*segments, *insights] for sid in strings(item.get("sources"))}
    ids = {s["id"] for s in sources if isinstance(s.get("id"), str)}
    reviews = {r.get("location"): r for r in objects(ledger.get("claims"))}
    review_tasks = []
    claim_data = {
        "insights": objects(data.get("insights")),
        "segments": [{**s, "insights": objects(s.get("insights"))} for s in segments],
    }
    for claim in claim_records(claim_data):
        review = reviews.get(claim["location"], {})
        reasons = []
        if review.get("claim_sha256") != claim["claim_sha256"]:
            reasons.append("missing_or_stale_claim_hash")
        if review.get("verdict") != "SUPPORTED":
            reasons.append("missing_supported_verdict")
        opened = review.get("opened_sources", [])
        if not isinstance(claim["sources"], list) or not set(strings(claim["sources"])).issubset(strings(opened)):
            reasons.append("cited_sources_not_all_reopened")
        notes = review.get("notes")
        if not isinstance(notes, str) or contained_file(root, notes) is None:
            reasons.append("missing_saved_review_notes")
        if ledger.get("subagents_available") is True and (
            review.get("method") != "independent"
            or not review.get("reviewer")
            or review.get("reviewer") == ledger.get("main_reader")
        ):
            reasons.append("missing_independent_reviewer")
        elif ledger.get("subagents_available") is False and (
            review.get("method") != "self-check" or not ledger.get("review_limitation")
        ):
            reasons.append("missing_self_check_disclosure")
        review_tasks.append({**claim, "record_current": not reasons, "issues": reasons})

    frame_uses = defaultdict(list)
    missing_images, frame_issues, missing_times = [], [], []
    diagram_count = 0
    source_hashes = {manifest.get("source_sha256"), manifest.get("media_sha256")} - {None}
    for index, segment in enumerate(segments):
        sid = segment.get("id", str(index))
        images = []
        if isinstance(segment.get("keyframe"), str) and segment["keyframe"]:
            images.append((segment["keyframe"], None))
        for block in objects(segment.get("caption")):
            if block.get("type") in {"flow", "mindmap", "svg"}:
                diagram_count += 1
            if block.get("type") == "image" and isinstance(block.get("src"), str):
                images.append((block["src"], block.get("cap", "")))
        if not images:
            missing_images.append(sid)
        for relative, _ in images:
            frame_uses[relative].append(sid)
        for relative in dict.fromkeys(path for path, _ in images):
            image = contained_file(root, relative)
            meta = saved_json(root, str(frame_metadata_path(image).relative_to(root))) if image else {}
            if meta.get("source_sha256") not in source_hashes:
                continue  # External diagrams/photos do not have a source-video timestamp.
            timestamp, start, end = meta.get("timestamp"), segment.get("start"), segment.get("end")
            if all(isinstance(v, (int, float)) and math.isfinite(v) for v in (timestamp, start, end)):
                if not start <= timestamp < end:
                    frame_issues.append(
                        {
                            "segment_id": sid,
                            "image": relative,
                            "recorded_time": timestamp,
                            "segment_interval": [start, end],
                        }
                    )
            captions = [cap for path, cap in images if path == relative and cap is not None]
            if captions and not any(re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", str(cap)) for cap in captions):
                missing_times.append({"segment_id": sid, "image": relative})

    referenced = set()
    for source in sources:
        paths = source.get("perception", [])
        referenced.update(
            [paths]
            if isinstance(paths, str)
            else [p for p in paths if isinstance(p, str)]
            if isinstance(paths, list)
            else []
        )
    source_readings = ledger.get("source_readings", [])
    if isinstance(source_readings, list):
        referenced.update(p for p in source_readings if isinstance(p, str))
    unintegrated = []
    scanned = 0
    truncated = False
    for work in (root / "_work", root / "_assets"):
        if not work.is_dir() or work.is_symlink():
            continue
        for path in work.rglob("reading.json"):
            if scanned >= 200:
                truncated = True
                break
            scanned += 1
            relative = str(path.relative_to(root))
            if relative in referenced:
                continue
            record = saved_json(root, relative)
            if record.get("status") == "read" and record.get("source_sha256") not in source_hashes:
                unintegrated.append(
                    {
                        "reading": relative,
                        "recorded_status": "read",
                        "source_sha256": record.get("source_sha256"),
                        "integration_verified": False,
                    }
                )

    acquired = []
    integrated = {s.get("media") for s in sources if isinstance(s.get("media"), str)}
    for index, receipt in enumerate((root / "_assets").rglob("*.source.json")):
        if index >= 200:
            break
        relative = str(receipt.relative_to(root))
        record = saved_json(root, relative)
        artifact = relative.removesuffix(".source.json")
        if record.get("status") == "acquired" and artifact not in integrated and contained_file(root, artifact):
            acquired.append(
                {"media": artifact, "url": record.get("url"), "record": relative, "reading_verified": False}
            )

    primary = {r.get("source_id"): r for r in objects(ledger.get("primary_readings"))}
    primary_issues = []
    for source in sources:
        if not source.get("primary"):
            continue
        reading = primary.get(source.get("id"), {})
        media = source.get("media")
        path = contained_file(root, media) if isinstance(media, str) else None
        reasons = []
        if not reading:
            reasons.append("missing_primary_reading_record")
        elif (
            path is not None
            and path.stat().st_size <= 64 * 1024 * 1024
            and sha256(path) != reading.get("source_sha256")
        ):
            reasons.append("saved_source_hash_mismatch")
        notes = reading.get("notes")
        if not isinstance(notes, str) or contained_file(root, notes) is None:
            reasons.append("missing_reader_notes")
        if reasons:
            primary_issues.append({"source_id": source.get("id"), "issues": reasons})

    displayed = list(frame_uses) + [
        value.get(key) for value in objects([data.get("meta"), data.get("video")]) for key in ("background", "poster")
    ]
    displayed += [s.get(key) for s in sources for key in ("media", "thumb")]
    used = {contained_file(root, p) for p in displayed if isinstance(p, str)}
    unused_images, image_scanned, image_truncated = [], 0, False
    for folder in ("img", "anchors", "_assets/images"):
        directory = root / folder
        if directory.is_symlink() or not directory.resolve().is_relative_to(root):
            continue
        for path in directory.rglob("*"):
            if image_scanned >= 200:
                image_truncated = True
                break
            image_scanned += 1
            relative = str(path.relative_to(root))
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}:
                resolved = contained_file(root, relative)
                if resolved and resolved not in used:
                    unused_images.append(relative)

    return {
        "scope": "Authoring diagnostics only; no research, media analysis, repairs or delivery approval performed.",
        "sources": {
            "total": len(sources),
            "inline_cited": sorted(ids & inline),
            "without_inline_citations": sorted(ids - inline),
            "not_linked_to_findings": sorted(ids - linked),
        },
        "claims": review_tasks,
        "primary_reading_issues": primary_issues,
        "unintegrated_readings": unintegrated,
        "unintegrated_acquisitions": acquired,
        "evidence_handoffs": evidence_handoffs(root),
        "reading_inventory": {
            "scanned": scanned,
            "limit": 200,
            "truncated": truncated,
            "note": "Recorded read status is not proof of complete reading, relevance or distinct sources.",
        },
        "presentation": {
            "unplaced_image_assets": sorted(unused_images),
            "image_inventory": {"scanned": image_scanned, "limit": 200, "truncated": image_truncated},
            "generic_segment_titles": [
                s.get("id", str(i))
                for i, s in enumerate(segments)
                if re.fullmatch(
                    r"(?:intro(?:duction)?|outro|conclusion|summary|overview|(?:part|segment)\s*\d+|"
                    r"开场|开头|片尾|结尾|总结|概述|第[\d一二三四五六七八九十]+[段章节])",
                    str(s.get("title", "")).strip(),
                    re.I,
                )
            ],
            "segments_without_images": missing_images,
            "images_reused_across_segments": [
                {"image": p, "segment_ids": list(dict.fromkeys(ids))}
                for p, ids in frame_uses.items()
                if len(set(ids)) > 1
            ],
            "images_repeated_within_segments": [
                {"image": p, "segment_ids": [sid for sid in dict.fromkeys(ids) if ids.count(sid) > 1]}
                for p, ids in frame_uses.items()
                if len(ids) > len(set(ids))
            ],
            "source_frames_outside_segment": frame_issues,
            "source_image_captions_without_time": missing_times,
            "structured_diagram_blocks": diagram_count,
        },
        "next_step": "Use saved evidence to fix the listed locations. Reopen sources for changed claims; do not relabel stale reviews, invent citations, or retry refused media to satisfy diagnostics.",
    }
