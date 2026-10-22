"""Search and preserve external evidence without bundling connection secrets."""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from .common import InputError, local_file, new_output, public_session, public_url, run


def source_record(result, url, engine):
    from .project import sha256

    path = Path(result["path"])
    receipt = new_output(str(path) + ".source.json")
    canonical = result.get("canonical_url", url)
    parsed = urlsplit(canonical)
    signed = any(
        re.search(r"key|token|auth|sig|credential|cookie|password|passwd|secret|session|jwt|bearer", key, re.I)
        for part in (parsed.query, parsed.fragment)
        for key, _ in parse_qsl(part)
    )
    record = {
        "url": None if signed else canonical,
        "source_url_needs_canonical": signed,
        "artifact": path.name,
        "source_sha256": sha256(path),
        "engine": engine,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "status": "acquired",
    }
    record.update({key: result[key] for key in ("title", "part_title", "uploader", "duration") if key in result})
    if "content_type" in result:
        record["content_type"] = result["content_type"]
    if result.get("readable_path"):
        readable = Path(result["readable_path"])
        record.update(readable_artifact=readable.name, readable_sha256=sha256(readable))
    receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    result = {**result, "source_record_path": str(receipt)}
    if signed:
        result.update(canonical_url=None, source_url_needs_canonical=True)
    return result


def search(
    query: str,
    kind: str,
    count: int,
    site: str | None,
    image_url: str | None,
    backend: str = "auto",
    market: str | None = None,
) -> dict:
    if backend not in {"auto", "bing", "platform"}:
        raise InputError("Search backend must be auto, bing or platform.")
    if kind == "reverse":
        raise InputError(
            "Reverse image search is unavailable with these public search backends. "
            "Use a host reverse-image-search tool, or search an observed description with kind=image."
        )
    requested = "bing" if backend == "auto" else backend
    if requested == "platform":
        if kind != "video":
            raise InputError("The platform backend supports video search only.")
        from .public_search import platform

        return {"status": "found", "backend": "platform", "results": platform(query, site, count)}
    if site:
        domain = {"youtube": "youtube.com", "bilibili": "bilibili.com", "web": ""}.get(site, site)
        if domain:
            query = f"{query} site:{domain}"
    from .public_search import bing

    results = bing(query, "web" if kind == "video" else kind, count, market)
    return {
        "status": "found",
        "backend": "bing",
        "fallback": False,
        "results": results,
        "next_step": "Open and read each source. For video, keep actual watch URLs and download + watch the media.",
    }


def readable_html(content: str) -> str:
    content = re.sub(r"<(script|style|noscript|head)\b.*?</\1>", " ", content, flags=re.S | re.I)
    content = re.sub(r"<!--.*?-->", " ", content, flags=re.S)
    content = re.sub(r"<(?:br|/p|/div|/li|/h[1-6]|/tr)\b[^>]*>", "\n", content, flags=re.I)
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", content))).strip()


def fetch(url: str, output_path: str, max_bytes: int, engine: str = "direct", answer: str | None = None) -> dict:
    public_url(url)
    new_output(str(output_path) + ".source.json")  # Check both names before downloading.
    output = new_output(output_path)
    if engine == "auto":
        engine = "direct"
    if engine != "direct":
        raise InputError("Reader engine must be direct or auto.")
    readable_output = new_output(str(output) + ".readable.txt")
    with (
        public_session() as session,
        session.get(url, stream=True, timeout=(15, 60), headers={"User-Agent": "Qwen-MM-Plugins/OmniDR"}) as response,
    ):
        response.raise_for_status()
        size = 0
        with tempfile.TemporaryDirectory(prefix="omnidr-fetch-", dir=output.parent) as directory:
            stage = Path(directory) / "download"
            with stage.open("wb") as handle:
                for chunk in response.iter_content(64 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise InputError("Source exceeds the download limit; choose a smaller artifact.")
                    handle.write(chunk)
            if not size:
                raise InputError("Source returned an empty body; it cannot support a citation.")
            stage.rename(output)
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        result = {"status": "saved", "path": str(output), "bytes": size, "content_type": content_type}
        is_html = content_type in {"text/html", "application/xhtml+xml"}
        if is_html or content_type.startswith("text/"):
            content = output.read_text(encoding=response.encoding or "utf-8", errors="replace")
            text = readable_html(content) if is_html else content
            if is_html:
                readable_output.write_text(text, encoding="utf-8")
                result["readable_path"] = str(readable_output)
            else:
                result["readable_path"] = str(output)
            result["text"] = text[:12000]
            result["truncated"] = len(text) > 12000
            result["next_step"] = (
                "Read readable_path in bounded chunks, or assign a document reader; text is only a preview. "
                "path preserves original bytes and may contain HTML even with a .md filename. "
                "Save full reading notes and integrate findings before fetching another batch."
            )
        result = source_record(result, url, engine)
        if answer and (is_html or content_type.startswith("text/")):
            result["answer"] = answer_page(text, answer)
        return result


def answer_page(content: str, question: str) -> str:
    from .config import chat

    prompt = (
        "Answer only from the saved page, quote supporting passages, and state missing evidence.\nQuestion: "
        + question
        + "\nPAGE:\n"
        + content[:60000]
    )
    return chat(prompt, mode="text")[0]


def download_failure_hint(stderr: str) -> str:
    """Return fixed diagnostic text without exposing URLs, cookie values or proxy credentials."""
    errors = [line for line in stderr.splitlines() if "ERROR:" in line]
    message = ("\n".join(errors) if errors else stderr).lower()
    reasons = [
        (
            (
                "timed out",
                "network is unreachable",
                "connection refused",
                "connection reset",
                "failed to resolve",
                "name or service not known",
                "temporary failure in name resolution",
            ),
            "The video platform could not be reached (network connection or DNS failure). "
            "Cookies do not fix a network block. Check the configured network route or use reachable sources.",
        ),
        (
            ("sign in", "not a bot", "login required", "members-only", "cookies", "authentication"),
            "The platform requires usable authentication. Configure an existing external cookie file; "
            "it may be expired or lack access to this video.",
        ),
        (
            ("javascript", "signature", "challenge", "js runtime"),
            "The platform's extraction challenge prevented an ordinary download. "
            "Record this source as unavailable and use accessible material.",
        ),
        (("no module named yt_dlp",), "Install yt-dlp in the Python environment running this tool."),
        (("requested format", "no video formats"), "No requested downloadable video format is available."),
        (("http error 403", "http error 429"), "The platform rejected or rate-limited the download request."),
    ]
    for patterns, hint in reasons:
        if any(pattern in message for pattern in patterns):
            return hint + " No video was downloaded."
    return "Video download failed. Check platform availability and the configured download runtime."


def download_video(url: str, output_path: str, cookies_file: str | None, page: int = 1, quality: int = 64) -> dict:
    if re.fullmatch(r"BV[0-9A-Za-z]{10}|av[0-9]+", url):
        url = "https://www.bilibili.com/video/" + url
    public_url(url)
    new_output(str(output_path) + ".source.json")
    if urlsplit(url).hostname in {"www.bilibili.com", "bilibili.com", "b23.tv"}:
        from .bilibili import download

        return source_record(download(url, output_path, cookies_file, page, quality), url, "bilibili-api")
    output = new_output(output_path)
    if output.suffix.lower() != ".mp4":
        raise InputError("Video output must use .mp4.")
    with tempfile.TemporaryDirectory(prefix="omnidr-download-") as directory:
        work = Path(directory)
        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--ignore-config",
            "--no-js-runtimes",
            "--no-remote-components",
            "--no-playlist",
            "--no-progress",
            "--no-warnings",
            "--no-cache-dir",
            "--write-info-json",
            "--max-filesize",
            "500M",
            "--socket-timeout",
            "30",
            "--retries",
            "2",
            "-f",
            "bv*[height<=720]+ba/b[height<=720]/b",
            "--merge-output-format",
            "mp4",
            "--recode-video",
            "mp4",
            "-o",
            str(work / "video.%(ext)s"),
        ]
        if cookies_file:
            # yt-dlp may rewrite its jar; isolate those changes in a temporary copy.
            cookie_copy = work / "cookies.txt"
            shutil.copyfile(local_file(cookies_file), cookie_copy)
            cookie_copy.chmod(0o600)
            command.extend(["--cookies", str(cookie_copy)])
        command.extend(["--", url])
        run(command, timeout=900, failure_hint=download_failure_hint)
        artifact = work / "video.mp4"
        if not artifact.is_file() or not artifact.stat().st_size:
            raise InputError("No video was downloaded. The platform may require an external cookie file or runtime.")
        from .project import probe

        info = probe(artifact)
        metadata_path = work / "video.info.json"
        metadata = json.loads(metadata_path.read_text()) if metadata_path.is_file() else {}
        identity = {key: metadata[key] for key in ("title", "uploader") if isinstance(metadata.get(key), str)}
        shutil.copyfile(artifact, output)
    return source_record(
        {
            "canonical_url": url,
            "status": "downloaded",
            "path": str(output),
            "duration": info["duration"],
            **identity,
            "next_step": "Inspect visual frames and audio before treating this video as researched evidence.",
        },
        url,
        "yt-dlp",
    )
