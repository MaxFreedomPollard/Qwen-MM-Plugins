"""One timestamped Omni ASR pass per source interval."""

from __future__ import annotations

import json
import math

from .common import InputError, local_file, new_output
from .project import probe, sha256

PROMPT = """Transcribe speech verbatim in its original spoken language. Return only JSON with keys language, speech_detected,
and segments: [{start: number, end: number, text: string}]. Times are seconds relative
to this clip, starting at 0. Keep segments short (one sentence or roughly 5–10 seconds)
and cover all speech throughout the clip in order. Retain domain terms; do not summarize or invent speech. For silence or
non-speech audio return speech_detected=false and segments=[]."""


class ASRValidationError(InputError):
    """An invalid transcript structure or timestamp."""


def parse_segments(text, duration, *, engine="remote"):
    def invalid(reason, index=None):
        location = f" segment[{index}]" if index is not None else " response"
        error = ASRValidationError(f"ASR ({engine}){location}: {reason}. This interval is not complete.")
        error.constraint, error.segment_index = reason, index
        raise error

    text = text.strip()
    if text.startswith("```"):
        if "\n" not in text:
            invalid("malformed JSON code fence")
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        invalid("invalid JSON")
    segments = data if isinstance(data, list) else data.get("segments") if isinstance(data, dict) else None
    if not isinstance(segments, list):
        invalid("segments must be an array")
    if not segments and (not isinstance(data, dict) or data.get("speech_detected") is not False):
        invalid("empty segments require an explicit speech_detected=false result")
    previous = -1
    for index, item in enumerate(segments):
        if not isinstance(item, dict):
            invalid("segment must be an object", index)
        try:
            a, b = float(item["start"]), float(item["end"])
        except (ValueError, TypeError, KeyError):
            invalid("start and end must be numeric seconds", index)
        if not (math.isfinite(a) and math.isfinite(b)):
            invalid("start and end must be finite", index)
        if not (0 <= a < min(b, duration)):
            invalid("start must precede end and lie inside the clip", index)
        if not (min(b, duration) <= b <= duration + 0.25):
            invalid("end exceeds the clip duration tolerance", index)
        if a < previous:
            invalid("segments must be ordered by start time", index)
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            invalid("text must be a nonempty string", index)
        item.update(start=a, end=min(b, duration))
        previous = a
    return segments, data.get("language") if isinstance(data, dict) else None


def transcribe(
    file_path, output_path, start_time=0.0, end_time=None, engine="auto", language=None, initial_prompt=None
):
    if engine not in {"auto", "shared"}:
        raise InputError("ASR uses the configured Omni model; engine must be auto or shared.")
    source = local_file(file_path)
    info = probe(source)
    end = min(end_time if end_time is not None else info["duration"], info["duration"])
    if not (0 <= start_time < end) or end - start_time > 300.01:
        raise InputError(
            "Transcribe one nonempty interval of at most 300 seconds; use omnidr_read_video for parallel full coverage."
        )
    from .policy import check

    check(source, "audio", [start_time, end])
    output = new_output(output_path)
    text_output = output.with_suffix(".txt")
    if text_output == output or text_output.exists():
        raise InputError("Use a new .json output and preserve its adjacent .txt transcript.")
    if output.suffix != ".json":
        raise InputError("Transcript output must use .json.")
    if not any(s.get("codec_type") == "audio" for s in info["streams"]):
        result = {"status": "no_audio", "segments": [], "language": None, "engine": None}
    else:
        duration = end - start_time
        prompt = (
            f"Transcribe this audio. Clip duration: {duration:.6f} seconds. "
            f"Use clip-relative numeric seconds with 0 <= start < end <= {duration:.6f}; "
            "do not add source-video offsets."
            + ("\nLanguage: " + language if language else "")
            + ("\nDomain terms: " + initial_prompt if initial_prompt else "")
        )
        from .media import perceive

        observed = perceive(
            {
                "file_path": str(source),
                "mode": "audio",
                "prompt": prompt,
                "start_time": start_time,
                "end_time": end,
                "_asr": True,
            }
        )
        segments, detected = parse_segments(observed["text"], duration, engine="shared")
        segments = [
            {**s, "start": round(s["start"] + start_time, 3), "end": round(s["end"] + start_time, 3)} for s in segments
        ]
        result = {
            "status": "transcribed",
            "segments": segments,
            "language": detected or language,
            "engine": "shared",
            "fallback": False,
            "fallback_error": None,
        }
    result.update(source_interval=[start_time, end], source_sha256=sha256(source), timestamp_origin_seconds=0)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    text_output.write_text(
        "\n".join(f"[{s['start']:.3f}-{s['end']:.3f}] {s['text']}" for s in result["segments"]) + "\n"
    )
    return {**result, "evidence_path": str(output), "text_path": str(text_output)}
