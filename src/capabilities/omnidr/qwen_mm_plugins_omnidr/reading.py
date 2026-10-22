"""Resumable 300-second visual/ASR fan-out shared by native readers and serial hosts."""

from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .common import InputError, ProviderPolicyError, local_file
from .project import MANIFEST, probe, sha256

DENSE_PROMPT = """You are a video reader preparing dense, illustrated notes and research anchors.
These frames carry ABSOLUTE SOURCE timestamps. Return text only, with these sections:
1. Timeline: one concrete visual event/action/scene change every 10–20 seconds.
2. On-screen text: transcribe titles, subtitles, chart labels, UI, papers/authors/DOIs,
   product names and visible quantities verbatim, each with its source timestamp.
3. Key visible facts: preserve numbers, names and units; distinguish observation from inference.
4. Visual anchor candidates: timestamp, object, region (3x3 grid), and why it deserves research.
5. Uncertainties: what is illegible or not established by the sampled frames. Do not guess.
6. Representative timestamps: distinct, useful frames for the report, avoiding transitions.
Speech is handled separately. Do not invent dialogue from silent frames."""


def _clips(start, end, *, avoid_short_tail=True):
    clips = []
    cursor = start
    while cursor < end:
        stop = min(cursor + 300, end)
        clips.append({"id": f"clip-{len(clips):04d}", "start": cursor, "end": stop})
        cursor = stop
    if avoid_short_tail and len(clips) > 1 and clips[-1]["end"] - clips[-1]["start"] < 1:
        # Avoid a subsecond tail beyond the final decodable video frame.
        boundary = end - 1
        clips[-2]["end"] = boundary
        clips[-1]["start"] = boundary
    return clips


def visual_interval(clip, source_interval):
    """Give a saved orphan tail real preceding frames without changing its ASR job."""
    start, end = clip["start"], clip["end"]
    if end - start < 1 and start > source_interval[0]:
        start = max(source_interval[0], end - 1)
    return [start, end]


def plan(file_path, start_time=0.0, end_time=None):
    source = local_file(file_path)
    info = probe(source)
    end = min(end_time if end_time is not None else info["duration"], info["duration"])
    if not (0 <= start_time < end):
        raise InputError("The reading interval is outside the source video.")
    if not any(s.get("codec_type") == "video" for s in info["streams"]):
        raise InputError("Video reading needs a video stream; use omnidr_transcribe for audio-only media.")
    return {
        "source_sha256": sha256(source),
        "duration": info["duration"],
        "has_audio": any(s.get("codec_type") == "audio" for s in info["streams"]),
        "source_interval": [start_time, end],
        "clips": _clips(start_time, end),
    }


def prevent_repeat_asr(output, digest, start, end):
    report = next((p for p in output.parents if (p / MANIFEST).is_file()), None)
    if report is None:
        return
    from .policy import linked

    aliases = linked(digest)
    for path in (report / "_work").rglob("*.tr.json"):
        if not path.resolve().is_relative_to(report):
            continue
        try:
            saved = json.loads(path.read_text())
            a, b = map(float, saved["source_interval"])
            overlaps = (
                saved.get("status") == "transcribed"
                and saved.get("source_sha256") in aliases
                and isinstance(saved.get("segments"), list)
                and math.isfinite(a)
                and math.isfinite(b)
                and 0 <= a < b
                and max(a, start) < min(b, end)
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        if overlaps:
            raise InputError(
                f"ASR already overlaps this interval: {path.relative_to(report)}. "
                "Reuse the saved transcript; use omnidr_read_media(mode='frames') for missing visuals. "
                "Changing output directories must not repeat successful ASR."
            )


def read_video(
    file_path,
    output_dir,
    start_time=0.0,
    end_time=None,
    question="",
    language=None,
    jobs=8,
    frames=32,
    frame_height=320,
):
    from .media import perceive
    from .transcription import transcribe

    if not 16 <= frames <= 48 or frame_height not in (320, 480):
        raise InputError("Dense reading requires 16–48 frames at 320 or 480px; use a narrow follow-up for 720px.")
    source = local_file(file_path)
    planned = plan(str(source), start_time, end_time)
    root = Path(output_dir).expanduser().absolute()
    plan_path = root / "reading-plan.json"
    if root.is_symlink():
        raise InputError("Reading output must be a regular directory, not a symlink.")
    if root.exists():
        try:
            previous = json.loads(plan_path.read_text())
        except (OSError, ValueError):
            raise InputError("Existing reading directory has no matching plan; choose a new directory.") from None
        legacy = {**planned, "clips": _clips(*planned["source_interval"], avoid_short_tail=False)}
        if previous not in (planned, legacy):
            raise InputError(
                "Existing reading plan belongs to a different source or interval. Resume with the exact same "
                "input file: the original video and a transcoded report copy have different hashes. "
                "Preserve successful passes; do not mix their provenance or repeat completed ASR."
            )
        # Resume the saved plan without repeating successful passes.
        planned = previous
    else:
        root.mkdir(parents=True)
        plan_path.write_text(json.dumps(planned, indent=2) + "\n")
    errors = []
    blocked = {}
    manifest = root / "reading.json"
    if manifest.is_file():
        for error in json.loads(manifest.read_text()).get("errors", []):
            if error.get("code") == "provider_policy_rejection":
                blocked[(error["clip"], error["pass"])] = error
    tasks = []
    records = []
    for clip in planned["clips"]:
        record = {**clip, "visual": clip["id"] + ".visual.json", "transcript": clip["id"] + ".tr.json"}
        visual_span = visual_interval(clip, planned["source_interval"])
        if visual_span != [clip["start"], clip["end"]]:
            record["visual_interval"] = visual_span
        records.append(record)
        for kind, field in [("visual", "visual"), ("audio", "transcript")]:
            output = root / record[field]
            if output.exists():
                try:
                    saved = json.loads(output.read_text())
                    expected = (
                        {"observed"} if kind == "visual" else {"transcribed" if planned["has_audio"] else "no_audio"}
                    )
                    allowed_spans = [[clip["start"], clip["end"]]]
                    if kind == "visual":
                        allowed_spans.append(visual_span)
                    if (
                        saved.get("source_sha256") != planned["source_sha256"]
                        or saved.get("source_interval") not in allowed_spans
                        or saved.get("status") not in expected
                    ):
                        raise ValueError()
                    if kind == "visual" and not saved.get("text"):
                        raise ValueError()
                    if kind == "visual" and saved["source_interval"] == [clip["start"], clip["end"]]:
                        record.pop("visual_interval", None)
                    if kind == "audio" and not isinstance(saved.get("segments"), list):
                        raise ValueError()
                except (ValueError, OSError, AttributeError):
                    raise InputError(
                        "A saved reading is invalid; preserve it for diagnosis and use a new output directory."
                    ) from None
                continue
            if (clip["id"], kind) in blocked:
                errors.append(blocked[(clip["id"], kind)])
            else:
                if kind == "audio" and planned["has_audio"]:
                    prevent_repeat_asr(output, planned["source_sha256"], clip["start"], clip["end"])
                tasks.append((kind, clip, output))

    def execute(task):
        kind, clip, output = task
        if kind == "visual":
            start, end = visual_interval(clip, planned["source_interval"])
            return perceive(
                {
                    "file_path": str(source),
                    "mode": "frames",
                    "frames": frames,
                    "frame_height": frame_height,
                    "start_time": start,
                    "end_time": end,
                    "prompt": DENSE_PROMPT + "\nResearch focus: " + question,
                    "output_path": str(output),
                }
            )
        return transcribe(str(source), str(output), clip["start"], clip["end"], language=language)

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        pending = {executor.submit(execute, task): task for task in tasks}
        for future in as_completed(pending):
            kind, clip, _ = pending[future]
            try:
                future.result()
            except Exception as exc:
                error = {
                    "clip": clip["id"],
                    "pass": kind,
                    "error": str(exc) if isinstance(exc, InputError) else type(exc).__name__,
                }
                if isinstance(exc, ProviderPolicyError):
                    error.update(
                        code="provider_policy_rejection", retry_allowed=False, journal_persisted=not exc.journal_failed
                    )
                    if exc.recorded_stop is not None:
                        error.update(recorded_stop=exc.recorded_stop, provider_request_sent=False)
                errors.append(error)
    transcript = []
    for record in records:
        path = root / record["transcript"]
        if path.is_file():
            transcript.extend(json.loads(path.read_text()).get("segments", []))
    transcript.sort(key=lambda s: s["start"])
    (root / "transcript.txt").write_text(
        "\n".join(f"[{s['start']:.3f}-{s['end']:.3f}] {s['text']}" for s in transcript) + "\n"
    )
    result = {
        "status": "incomplete" if errors else "read",
        **planned,
        "clips": records,
        "errors": errors,
        "question": question,
        "timestamp_origin_seconds": 0,
        "review_required": "Reconcile visual captions and ASR, correct names/numbers against visible text, and return the reader's structured synthesis. Raw passes do not establish factual conclusions.",
    }
    (root / "reading.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return {
        "status": result["status"],
        "manifest_path": str(root / "reading.json"),
        "source_interval": planned["source_interval"],
        "clips": len(records),
        "errors": errors,
        "transcript_path": str(root / "transcript.txt"),
        "next_step": result["review_required"],
    }
