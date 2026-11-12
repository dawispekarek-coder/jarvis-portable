"""Bounded web research for the autonomy loop — allowlisted game-data
sources only. Returns readable text; no cookies, no JS, no code exec.

Policy: HTTPS GET only, size-capped, domain allowlist of legitimate
quest/NPC/route data sources + archive mirrors. Robots/license respect
is documented per-domain; results are CANDIDATES for verification —
never treated as proven Forever facts."""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.parse

ALLOWED_DOMAINS = {
    "www.wowhead.com", "wowhead.com", "classic.wowhead.com",
    "warcraft.wiki.gg", "wowpedia.fandom.com",
    "wowwiki-archive.fandom.com", "wow.gamepedia.com",
    "www.wowdb.com", "wowdb.com",
    "db.wowforever.com", "api.wowforever.com",
    "github.com", "raw.githubusercontent.com",
    "web.archive.org", "duckduckgo.com", "html.duckduckgo.com",
    "lite.duckduckgo.com", "tbc.wowhead.com", "www.wowhead.com",
    "thottbot.com", "webcache.googleusercontent.com",
}
_UA = {"User-Agent": "ForeverRouteResearch/1.0 (read-only data audit)"}
_MAX_BYTES = 400_000


def _fetch(url: str, cap: int = _MAX_BYTES) -> dict:
    if not re.match(r"^https://", url or ""):
        return {"ok": False, "error": "https_only"}
    host = urllib.parse.urlparse(url).netloc.lower()
    if host not in ALLOWED_DOMAINS:
        return {"ok": False, "error": f"domain_not_allowed:{host}",
                "allowed": sorted(ALLOWED_DOMAINS)}
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read(cap + 1)
        if len(raw) > cap:
            return {"ok": False, "error": "too_large"}
        text = raw.decode("utf-8", errors="replace")
        # strip markup to readable text (bounded)
        text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return {"ok": True, "url": url, "chars": len(text),
                "text": text[:30000],
                "provenance": f"{host} via HTTPS GET, license/terms apply — CANDIDATE evidence only"}
    except Exception as exc:
        return {"ok": False, "error": f"fetch:{type(exc).__name__}:{exc}"[:200],
                "url": url}


def _search(query: str) -> dict:
    q = urllib.parse.quote_plus((query or "")[:300])
    url = f"https://lite.duckduckgo.com/lite/?q={q}"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent":
                          "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read(200_000).decode("utf-8", errors="replace")
    except Exception as exc:
        return {"ok": False,
                "error": f"search:{type(exc).__name__}:{exc}"[:200]}
    links = re.findall(
        r'<a[^>]{0,160}href="([^"]*uddg=[^"]+)"[^>]*>(.*?)</a>',
        html, flags=re.S)
    out = []
    seen = set()
    for u, t in links:
        m = re.search(r"uddg=([^&\"']+)", u)
        if not m:
            continue
        real = urllib.parse.unquote(m.group(1))
        if real in seen:
            continue
        seen.add(real)
        out.append({"url": real,
                    "title": re.sub(r"<[^>]+>", "", t).strip()[:200]})
        if len(out) >= 12:
            break
    return {"ok": True, "query": query, "results": out,
            "note": "search hits are leads, not verified facts"}


def web_fetch(args: dict | None = None, **kw) -> str:
    a = dict(args or {}, **kw)
    return json.dumps(_fetch(str(a.get("url", ""))),
                      ensure_ascii=False)


def web_search(args: dict | None = None, **kw) -> str:
    a = dict(args or {}, **kw)
    return json.dumps(_search(str(a.get("query", ""))),
                      ensure_ascii=False)
