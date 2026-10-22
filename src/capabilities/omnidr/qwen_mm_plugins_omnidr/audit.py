"""Delivery checks for the research requirements; recorded review is not proof of truth."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from .project import contained_file, frame_metadata_path, probe, sha256


def claim_records(data, *, include_payload=False):
    records = []
    groups = [("insights", data.get("insights", []))]
    groups += [
        (f"segments/{i}/insights", segment.get("insights", []))
        for i, segment in enumerate(data.get("segments", []))
        if isinstance(segment, dict)
    ]
    for prefix, insights in groups:
        for index, claim in enumerate(insights):
            if not isinstance(claim, dict) or claim.get("kind") not in {"compare", "timeliness"}:
                continue
            payload = {
                key: claim.get(key)
                for key in ("kind", "title", "body", "table", "videoClaim", "currentFact", "sources")
            }
            digest = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            records.append(
                {"location": f"{prefix}/{index}", "claim_sha256": digest, "sources": claim.get("sources", [])}
            )
            if include_payload:
                records[-1]["claim"] = payload
    return records


def read_json(root, relative):
    path = contained_file(root, relative) if isinstance(relative, str) else None
    if path is None:
        raise ValueError()
    return json.loads(path.read_text())


def coverage(intervals, duration):
    cursor = 0.0
    for start, end in sorted(intervals):
        if not (0 <= start < end <= duration + 0.1) or abs(start - cursor) > 0.1:
            return False
        cursor = end
    return abs(cursor - duration) <= 0.1


def reading_complete(root, paths, digest, duration, has_audio):
    """Verify successful visual + ASR artifacts for every 300s interval, without gaps or duplicate ASR."""
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, list) or not paths:
        return False
    intervals = []
    try:
        for relative in paths:
            manifest = read_json(root, relative)
            if (
                manifest.get("status") != "read"
                or manifest.get("source_sha256") != digest
                or manifest.get("errors")
                or manifest.get("has_audio") is not has_audio
            ):
                return False
            parent = Path(relative).parent
            for clip in manifest["clips"]:
                start, end = clip["start"], clip["end"]
                if end - start > 300.01:
                    return False
                visual = read_json(root, str(parent / clip["visual"]))
                audio = read_json(root, str(parent / clip["transcript"]))
                from .reading import visual_interval

                visual_span = clip.get("visual_interval", [start, end])
                allowed_span = visual_interval(clip, manifest.get("source_interval", [0, duration]))
                if visual_span not in ([start, end], allowed_span):
                    return False
                for record, span in [(visual, visual_span), (audio, [start, end])]:
                    if record.get("source_sha256") != digest or record.get("source_interval") != span:
                        return False
                if (
                    visual.get("mode") not in {"frames", "video"}
                    or visual.get("status") != "observed"
                    or not visual.get("text")
                ):
                    return False
                expected = "transcribed" if has_audio else "no_audio"
                if audio.get("status") != expected or not isinstance(audio.get("segments"), list):
                    return False
                intervals.append((start, end))
        return coverage(intervals, duration)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def delivery_errors(root, manifest, data):
    errors = []
    sources = data.get("research", [])
    by_id = {s.get("id"): s for s in sources}
    videos = [s for s in sources if s.get("type") == "video"]
    if len(sources) < 25:
        errors.append("Research floor: open and consume at least 25 external sources, including focused requests.")
    platforms = {
        (
            "youtube.com"
            if (urlsplit(s.get("url", "")).hostname or "").removeprefix("www.")
            in {"youtube.com", "youtu.be", "m.youtube.com"}
            else (urlsplit(s.get("url", "")).hostname or "").removeprefix("www.")
        )
        for s in videos
    }
    if len(videos) < 5 or len(platforms) < 2:
        errors.append("Research floor: watch at least five related videos across at least two platforms.")
    for source in sources:
        parsed = urlsplit(source.get("url", ""))
        if parsed.path.rstrip("/").endswith(("/search", "/results")) or (parsed.hostname or "").startswith("search."):
            errors.append("Use canonical source/watch URLs, never search-results pages.")
        if not source.get("publisher"):
            errors.append("Record each source's independent publisher/author in research[].publisher.")
    for anchor in data.get("anchors", []):
        linked = [
            s for s in sources if s.get("anchorId") == anchor.get("id") or anchor.get("id") in s.get("anchorIds", [])
        ]
        if len(linked) < 3 or len({s.get("publisher") for s in linked if s.get("publisher")}) < 3:
            errors.append("Each research anchor needs at least three independently produced external sources.")
    try:
        audit = read_json(root, "_work/research-review.json")
        if not isinstance(audit, dict):
            raise ValueError()
    except (OSError, ValueError, TypeError):
        return errors + [
            "Complete _work/research-review.json with source reading, primary documents, crop and fact-check records."
        ]
    main_readings = audit.get("source_readings")
    main_media = contained_file(root, "media/source.mp4")
    if main_media is None:
        return errors + ["Source media is missing; reading coverage cannot be checked."]
    main_has_audio = any(s.get("codec_type") == "audio" for s in probe(main_media)["streams"])
    # Reading either the original file or the remuxed browser copy preserves source seconds.
    if not any(
        reading_complete(root, main_readings, digest, manifest["duration"], main_has_audio)
        for digest in {manifest["source_sha256"], manifest["media_sha256"]}
    ):
        errors.append(
            "Source video needs complete 300-second visual + ASR readings without gaps or duplicate intervals."
        )
    for source in videos:
        media = contained_file(root, source.get("media", ""))
        try:
            if media is None:
                raise ValueError()
            info = probe(media)
            if not reading_complete(
                root,
                source.get("perception"),
                sha256(media),
                info["duration"],
                any(s.get("codec_type") == "audio" for s in info["streams"]),
            ):
                raise ValueError()
        except (OSError, ValueError, TypeError):
            errors.append(
                "Every related video needs full visual + ASR coverage; a transcript, thumbnail or partial visual pass is insufficient."
            )
    primary_ids = set()
    for index, reading in enumerate(audit.get("primary_readings", [])):
        try:
            source = by_id[reading["source_id"]]
            media = contained_file(root, source["media"])
            notes = contained_file(root, reading["notes"])
            if reading.get("scope") != "full":
                errors.append(f"primary_readings[{index}].scope must be exactly 'full'; put reading details in notes.")
                continue
            if (
                source.get("type") not in {"web", "report"}
                or not source.get("primary")
                or not reading.get("reader")
                or media is None
                or sha256(media) != reading.get("source_sha256")
                or notes is None
                or notes.stat().st_size < 80
            ):
                raise ValueError()
            if media.suffix.lower() == ".pdf":
                pages = set()
                total = None
                for relative in reading.get("page_reads", []):
                    record = read_json(root, relative)
                    if record.get("source_sha256") != sha256(media) or record.get("status") != "read":
                        raise ValueError()
                    total = record["total_pages"]
                    pages.update(p["page"] for p in record["pages"])
                if not total or pages != set(range(1, total + 1)):
                    raise ValueError()
            primary_ids.add(source["id"])
        except (OSError, ValueError, TypeError, KeyError):
            errors.append(
                f"primary_readings[{index}] needs full-source notes and matching hashes; PDF records must cover every page."
            )
    if len(primary_ids) < 3:
        errors.append("Research floor: read at least three primary/authoritative text sources end-to-end.")
    crops = audit.get("visual_anchors", [])
    if not crops and not audit.get("no_identifiable_objects_reason"):
        errors.append(
            "Record an inspected, used object crop, or explain why the video contains no identifiable objects."
        )
    segment_text = json.dumps(data.get("segments", []), ensure_ascii=False)
    for index, crop in enumerate(crops):
        try:
            image = contained_file(root, crop["crop"])
            if image is None:
                raise ValueError()
            metadata = read_json(root, str(frame_metadata_path(image).relative_to(root)))
            if (
                image is None
                or metadata.get("output_sha256") != sha256(image)
                or metadata.get("source_sha256") not in {manifest["source_sha256"], manifest["media_sha256"]}
                or not metadata.get("box")
                or crop["crop"] not in segment_text
                or not crop.get("inspected")
            ):
                raise ValueError()
            if not crop.get("identification_sources") or not all(
                sid in by_id and by_id[sid].get("type") == "image" for sid in crop["identification_sources"]
            ):
                errors.append(f"visual_anchors[{index}]: identification_sources must reference consumed image sources.")
        except (OSError, ValueError, TypeError, KeyError):
            errors.append(
                f"visual_anchors[{index}]: preserve an inspected source crop, matching tool metadata and segment image reference."
            )
    if not isinstance(audit.get("subagents_available"), bool) or not audit.get("main_reader"):
        errors.append("Record main_reader and whether the host actually supports independent subagents.")
    reviewers = {r.get("location"): r for r in audit.get("claims", []) if isinstance(r, dict)}
    for claim in claim_records(data):
        review = reviewers.get(claim["location"], {})
        if (
            review.get("claim_sha256") != claim["claim_sha256"]
            or review.get("verdict") != "SUPPORTED"
            or not set(claim["sources"]).issubset(set(review.get("opened_sources", [])))
            or not review.get("notes")
            or contained_file(root, review["notes"]) is None
        ):
            errors.append(
                "Every comparison/correction needs a current SUPPORTED review that reopens all cited sources and saves its findings."
            )
        if audit.get("subagents_available"):
            if (
                review.get("method") != "independent"
                or not review.get("reviewer")
                or review.get("reviewer") == audit.get("main_reader")
            ):
                errors.append(
                    "Use a separate reviewer for every comparison/correction; pass the claim, source URLs and "
                    "mandatory constraints, without the author's rationale."
                )
        elif review.get("method") != "self-check" or not audit.get("review_limitation"):
            errors.append(
                "Hosts without subagents must record strict source reopening as self-check and disclose the independence limitation."
            )
    insights = list(data.get("insights", [])) + [i for s in data.get("segments", []) for i in s.get("insights", [])]
    if not any(i.get("kind") in {"compare", "cause"} for i in insights):
        errors.append("Include a substantive externally supported comparison or causal insight.")
    dated = [
        i
        for i in insights
        if i.get("kind") == "timeliness"
        and re.search(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", json.dumps(i, ensure_ascii=False))
    ]
    if not dated:
        errors.append(
            "Include a dated timeliness check; an unchanged claim can be confirmed as current without inventing a correction."
        )
    visual = audit.get("render_review", {})
    if (
        not all(
            visual.get(k) is True for k in ("images", "playback", "bidirectional_seeking", "citations", "legibility")
        )
        or contained_file(root, visual.get("screenshot", "")) is None
    ):
        errors.append(
            "Inspect a saved report screenshot and record playback, bidirectional seeking, citations, images and legibility checks."
        )
    return sorted(set(errors))
