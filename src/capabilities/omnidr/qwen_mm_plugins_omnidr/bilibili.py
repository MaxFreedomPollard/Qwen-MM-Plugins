"""Download Bilibili videos through public APIs and merge DASH streams."""

from __future__ import annotations

import http.cookiejar
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .common import InputError, local_file, new_output, public_session, public_url, run
from .public_search import UA

LIMIT = 500 * 1024 * 1024


def api(session, path, params=None):
    response = session.get("https://api.bilibili.com" + path, params=params, timeout=(15, 30))
    response.raise_for_status()
    data = response.json()
    if data.get("code") != 0:
        code = data.get("code")
        raise InputError(
            f"Bilibili API rejected this request (code {code if isinstance(code, int) else 'unknown'}). Check video access and cookie configuration."
        )
    return data.get("data") or {}


def download_stream(session, url, path, remaining):
    public_url(url)
    size = 0
    with session.get(url, stream=True, timeout=(15, 60)) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                size += len(chunk)
                if size > remaining:
                    raise InputError("Bilibili source exceeds the 500 MiB download limit.")
                handle.write(chunk)
    if not size:
        raise InputError("Bilibili returned an empty media stream.")
    return size


def download(url: str, output_path: str, cookies_file: str | None, page: int = 1, quality: int = 64):
    from .project import probe

    output = new_output(output_path)
    if output.suffix.lower() != ".mp4":
        raise InputError("Video output must use .mp4.")
    with (
        public_session() as session,
        tempfile.TemporaryDirectory(prefix="omnidr-bili-", dir=output.parent) as directory,
    ):
        session.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
        if cookies_file:
            jar = http.cookiejar.MozillaCookieJar()
            jar.load(str(local_file(cookies_file)), ignore_discard=True, ignore_expires=False)
            session.cookies.update(jar)  # Memory only; never rewrite the caller's jar.
        if urlsplit(url).hostname == "b23.tv":
            response = session.get(url, timeout=(15, 30))
            response.raise_for_status()
            url = response.url
        if urlsplit(url).hostname not in {"bilibili.com", "www.bilibili.com"}:
            raise InputError("The short link did not resolve to a Bilibili video page.")
        match = re.search(r"BV[0-9A-Za-z]{10}|av[0-9]+", url)
        if not match:
            raise InputError("A Bilibili watch URL with a BV or av identifier is required.")
        identity = match[0]
        id_key, value = ("bvid", identity) if identity.startswith("BV") else ("aid", identity[2:])
        if not session.cookies.get("buvid3", domain=".bilibili.com"):
            try:
                token = api(session, "/x/frontend/finger/spi").get("b_3")
                if token:
                    session.cookies.set("buvid3", token, domain=".bilibili.com", path="/")
            except Exception:
                pass  # Optional server-issued anonymous identifier; no forged credentials.
        view = api(session, "/x/web-interface/view", {id_key: value})
        requested = parse_qs(urlsplit(url).query).get("p", [page])[0]
        try:
            number = int(requested)
        except (ValueError, TypeError):
            raise InputError("Bilibili part number must be an integer.") from None
        selected = next((p for p in view.get("pages", []) if p.get("page") == number), None)
        if selected is None:
            raise InputError("The requested Bilibili part does not exist.")
        data = api(
            session,
            "/x/player/playurl",
            {
                "avid" if id_key == "aid" else id_key: value,
                "cid": selected["cid"],
                "qn": quality,
                "fnval": 4048,
                "fourk": 1,
            },
        )
        work = Path(directory)
        artifact = work / "result.mp4"
        remaining = LIMIT
        dash = data.get("dash")
        if dash:
            videos = sorted(dash.get("video") or [], key=lambda s: s.get("id", 0))
            acceptable = [v for v in videos if v.get("id", 0) <= quality]
            if not videos:
                raise InputError("Bilibili returned no accessible video stream.")
            video = acceptable[-1] if acceptable else videos[0]
            remaining -= download_stream(
                session, video.get("baseUrl") or video["base_url"], work / "video.m4s", remaining
            )
            command = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(work / "video.m4s")]
            audio = max(dash.get("audio") or [], key=lambda s: s.get("id", 0), default=None)
            if audio:
                download_stream(session, audio.get("baseUrl") or audio["base_url"], work / "audio.m4s", remaining)
                command += ["-i", str(work / "audio.m4s"), "-map", "0:v:0", "-map", "1:a:0"]
            run([*command, "-c", "copy", "-movflags", "+faststart", str(artifact)], timeout=300)
        else:
            parts = data.get("durl") or []
            if not parts:
                raise InputError("Bilibili returned no accessible DASH or durl stream.")
            for i, part in enumerate(parts):
                remaining -= download_stream(session, part["url"], work / f"part-{i}.bin", remaining)
            listing = work / "concat.txt"
            listing.write_text("".join(f"file 'part-{i}.bin'\n" for i in range(len(parts))))
            run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(listing),
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(artifact),
                ],
                timeout=300,
            )
        info = probe(artifact)
        shutil.copyfile(artifact, output)
    bvid = view.get("bvid") or identity
    return {
        "status": "downloaded",
        "path": str(output),
        "canonical_url": f"https://www.bilibili.com/video/{bvid}/?p={number}",
        "title": view.get("title", ""),
        "part_title": selected.get("part", ""),
        "uploader": (view.get("owner") or {}).get("name", ""),
        "duration": info["duration"],
        "backend": "bilibili-api",
        "next_step": "Check the platform title and selected part against the search result, then run omnidr_read_video and preserve its reading manifest before citing this source.",
    }
