"""Tool results, input validation, and subprocess helpers."""

from __future__ import annotations

import functools
import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from shared.content import text
from shared.syscmd import find_tool


class InputError(ValueError):
    """A public input or operation error."""


class ProviderPolicyError(InputError):
    """A provider refusal must remain distinct from a retryable transport error."""

    def __init__(self, recorded_stop=None, *, journal_failed=False):
        self.recorded_stop = recorded_stop
        self.journal_failed = journal_failed
        if recorded_stop is not None:
            super().__init__(
                "Preflight blocked this request because it overlaps a recorded stop: "
                + json.dumps(recorded_stop, sort_keys=True)
                + ". No provider request was sent. This does not expand the stop to the requested batch. "
                "Other stops may also apply; preserve unresolved scope. Do not retry or reconstruct stopped outcomes."
            )
            return
        super().__init__(
            "The media provider rejected this material under its content-safety policy. "
            "Preserve the reading gap; do not automatically retry it through splitting, crops, "
            "other models/backends or other interfaces."
            + (" The refusal journal is unwritable; stop all readers until it is restored." if journal_failed else "")
        )


def is_provider_policy_error(exc):
    """Identify refusals from structured provider error codes."""
    body = getattr(exc, "body", None)
    codes = [getattr(exc, "code", None)]
    if isinstance(body, dict):
        codes.append(body.get("code"))
        if isinstance(body.get("error"), dict):
            codes.append(body["error"].get("code"))
    return any(
        isinstance(code, str)
        and code.lower() in {"content_policy_violation", "content_filter", "responsibleaipolicyviolation"}
        for code in codes
    )


def result_blocks(value: dict) -> list[dict]:
    return [text(json.dumps(value, ensure_ascii=False, allow_nan=False))]


def error_metadata(exc):
    status = getattr(exc, "status_code", None)
    return {
        "error": type(exc).__name__,
        "http_status": status if isinstance(status, int) else None,
        "errno": exc.errno if isinstance(exc, OSError) and isinstance(exc.errno, int) else None,
    }


def guarded(fn):
    """Keep upstream exception bodies, request URLs and credentials out of MCP output."""

    @functools.wraps(fn)
    def handle(arguments):
        try:
            return fn(arguments)
        except InputError as exc:
            return [text(json.dumps({"status": "failed", "error": str(exc)}))]
        except Exception as exc:
            return [
                text(
                    json.dumps(
                        {
                            "status": "failed",
                            **error_metadata(exc),
                            "hint": "Check inputs, installed dependencies and the matching service configuration. "
                            "Provider response bodies and connection details are intentionally omitted.",
                        }
                    )
                )
            ]

    return handle


def local_file(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise InputError("Input must be an existing local file.")
    return path


def new_output(value: str) -> Path:
    path = Path(value).expanduser().absolute()
    if path.exists() or path.is_symlink():
        raise InputError("Output already exists; choose a new path to preserve existing evidence.")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def public_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise InputError("Supply an HTTP(S) URL without embedded credentials.")
    return value


def public_session():
    """Retain proxy/CA settings without borrowing .netrc credentials for sources."""
    import requests

    class SourceSession(requests.Session):
        def rebuild_auth(self, prepared_request, response):
            prepared_request.headers.pop("Authorization", None)

    session = SourceSession()
    session.auth = lambda request: request  # Explicit no-auth prevents initial .netrc lookup.
    return session


def run(command: list[str], *, timeout: int = 120, failure_hint=None) -> subprocess.CompletedProcess:
    executable = find_tool(command[0])
    if not executable:
        raise InputError(f"Required executable is unavailable: {command[0]}.")
    result = subprocess.run(
        [executable, *command[1:]], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=timeout
    )
    if result.returncode:
        if failure_hint is not None:
            raise InputError(failure_hint(result.stderr))
        raise InputError(f"{command[0]} failed; check the input and installed codecs/dependencies.")
    return result
