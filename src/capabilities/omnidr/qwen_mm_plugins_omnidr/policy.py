"""Persist provider refusals across tools, output folders and equivalent media copies.

The private journal contains hashes, modalities and intervals, never credentials,
service addresses or media. This prevents accidental resubmission by independent
readers; it is not a sandbox against a host deliberately bypassing the plugin.
"""

from __future__ import annotations

import json
import math
import re
import uuid
from pathlib import Path

from .common import InputError, ProviderPolicyError

STATE_ROOT = Path.home() / ".local/state/qwen-mm-plugins/omnidr-policy"


def journal():
    STATE_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    return STATE_ROOT


def register_aliases(first, second):
    for value in (first, second):
        valid_digest(value)
    if first == second:
        return
    folder = journal() / "aliases"
    folder.mkdir(exist_ok=True, mode=0o700)
    target = folder / ("-".join(sorted((first, second))) + ".json")
    try:
        with target.open("x") as stream:
            target.chmod(0o600)
            json.dump([first, second], stream)
    except FileExistsError:
        pass


def linked(digest):
    valid_digest(digest)
    result, pending = {digest}, [digest]
    folder = journal() / "aliases"
    while pending:
        current = pending.pop()
        for pattern in (current + "-*.json", "*-" + current + ".json"):
            for path in folder.glob(pattern):
                for other in path.stem.split("-"):
                    if len(other) == 64 and other not in result:
                        result.add(other)
                        pending.append(other)
    return result


def subjects(path, mode, interval):
    from .project import frame_metadata_paths, sha256

    digest = sha256(path)
    result = [(digest, interval)]
    for sidecar in frame_metadata_paths(path) if mode == "image" else []:
        if sidecar.is_file():
            try:
                data = json.loads(sidecar.read_text())
                if data.get("output_sha256") == digest and data.get("source_sha256") and "timestamp" in data:
                    valid_digest(data["source_sha256"])
                    result.append((data["source_sha256"], [data["timestamp"], data["timestamp"]]))
            except (OSError, ValueError, TypeError, AttributeError):
                raise InputError(
                    "Cannot verify the image's provenance; preserve its metadata before reading."
                ) from None
    return result


def modalities(mode):
    return {"audio", "visual"} if mode == "video" else {"audio" if mode == "audio" else "visual"}


def valid_digest(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise InputError("Invalid source hash in media provenance.")


def valid_span(value):
    if value is not None and not (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(v, (int, float)) and math.isfinite(v) for v in value)
        and value[0] <= value[1]
    ):
        raise InputError("Invalid interval in the provider-refusal journal or media provenance.")


def overlaps(first, second):
    valid_span(first)
    valid_span(second)
    if first is None or second is None:
        return True
    if first[0] == first[1]:
        return second[0] <= first[0] < second[1] or first == second
    if second[0] == second[1]:
        return first[0] <= second[0] < first[1]
    return max(first[0], second[0]) < min(first[1], second[1])


def check(path, mode, interval):
    root = journal()
    for digest, span in subjects(Path(path), mode, interval):
        for identity in linked(digest):
            valid_digest(identity)
            for record in (root / identity).glob("*.json"):
                try:
                    data = json.loads(record.read_text())
                    if not data["modalities"] or not set(data["modalities"]) <= {"audio", "visual"}:
                        raise ValueError()
                    blocked = bool(modalities(mode) & set(data["modalities"])) and overlaps(span, data["interval"])
                except (OSError, ValueError, KeyError, TypeError):
                    raise InputError(
                        "The provider-refusal journal is unreadable; stop reading until it is restored."
                    ) from None
                if blocked:
                    raise ProviderPolicyError(
                        {
                            "source_sha256": identity,
                            "modalities": sorted(set(data["modalities"])),
                            "interval": data["interval"],
                        }
                    )


def remember(path, mode, interval):
    root = journal()
    for digest, span in subjects(Path(path), mode, interval):
        valid_span(span)
        folder = root / digest
        folder.mkdir(exist_ok=True, mode=0o700)
        temporary = folder / (uuid.uuid4().hex + ".tmp")
        with temporary.open("x") as stream:
            temporary.chmod(0o600)
            json.dump(
                {
                    "code": "provider_policy_rejection",
                    "modalities": sorted(modalities(mode)),
                    "interval": span,
                    "retry_allowed": False,
                },
                stream,
            )
        temporary.replace(temporary.with_suffix(".json"))
