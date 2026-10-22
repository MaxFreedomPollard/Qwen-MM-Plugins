"""Bounded public fallback and direct video-platform search."""

import html
import json
import re
import sys

from .common import public_session, run

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"


def bing(query, kind, count, market=None):
    from .sources import readable_html

    results = []
    for first in range(1, 61, 10):
        params = {"q": query, "count": min(35, count), "first": first}
        if market:
            params["mkt"] = market
        with public_session() as session:
            response = session.get(
                "https://www.bing.com/" + ("images/search" if kind == "image" else "search"),
                params=params,
                headers={"User-Agent": UA},
                timeout=(15, 30),
            )
            response.raise_for_status()
            content = response.text
        if kind == "image":
            for block in re.findall(r'class="iusc"[^>]*\sm="([^"]+)"', content):
                item = json.loads(html.unescape(block))
                if item.get("murl") and item.get("purl"):
                    results.append(
                        {
                            "title": item.get("t") or item.get("desc", ""),
                            "url": item["purl"],
                            "image_url": item["murl"],
                            "thumbnail": item.get("turl"),
                        }
                    )
        else:
            for block in re.split(r'<li class="b_algo"', content)[1:]:
                heading = re.search(r"<h2\b[^>]*>(.*?)</h2>", block, re.S)
                anchor = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', heading[1], re.S) if heading else None
                if anchor and anchor[1].startswith("http"):
                    snippet = re.search(r"<p\b[^>]*>(.*?)</p>", block, re.S)
                    results.append(
                        {
                            "title": readable_html(anchor[2]),
                            "url": html.unescape(anchor[1]),
                            "snippet": readable_html(snippet[1]) if snippet else "",
                        }
                    )
        results = list({r["url"]: r for r in results}.values())
        if len(results) >= count or not results:
            break
    return results[:count]


def platform(query, site, count):
    site = {
        "youtube.com": "youtube",
        "www.youtube.com": "youtube",
        "bilibili.com": "bilibili",
        "www.bilibili.com": "bilibili",
    }.get(site, site)
    from .common import InputError

    if site not in {"youtube", "bilibili"}:
        raise InputError("Direct platform search needs site=youtube or site=bilibili.")
    target = f"{'ytsearch' if site == 'youtube' else 'bilisearch'}{count}:{query}"
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--ignore-config",
        "--no-cache-dir",
        "--flat-playlist",
        "-J",
        "--no-warnings",
        "--socket-timeout",
        "30",
        "--retries",
        "2",
        "--user-agent",
        UA,
    ]
    if site == "bilibili":
        command += ["--referer", "https://www.bilibili.com/"]
    data = json.loads(run([*command, "--", target], timeout=120).stdout)
    results = []
    for item in (data.get("entries") or [])[:count]:
        identity = item.get("id")
        url = item.get("webpage_url") or item.get("url", "")
        if not url.startswith("http") and identity:
            url = (
                f"https://www.youtube.com/watch?v={identity}"
                if site == "youtube"
                else f"https://www.bilibili.com/video/{identity}/"
            )
        if url.startswith("http"):
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "duration": item.get("duration"),
                    "uploader": item.get("uploader") or item.get("channel"),
                }
            )
    return results
