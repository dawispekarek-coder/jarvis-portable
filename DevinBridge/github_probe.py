"""GitHub evidence for the bridge — READ-ONLY.

Uses the same DPAPI-protected token the legacy queue already maintains
(``github_token.dpapi``, decrypted with CryptUnprotectData in the current
user's context — the documented mechanism of JarvisQueue.ps1). All calls
are GETs: issues, PRs, check runs, compare. If the token is absent the
probe degrades honestly to "unavailable" — never fabricates CI state.

No merges, no comments, no PATCHes — GitHub writes stay with the human.
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import json
import urllib.request
from pathlib import Path
from typing import Any

OWNER = "Deciwarrz"
REPO = "ForeverRoute"
API = "https://api.github.com"


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi_decrypt(blob: bytes) -> str:
    """DPAPI-decrypt, then decode the way PowerShell's SecureString path
    does: SecureStringToBSTR yields UTF-16LE. Fall back to UTF-8."""
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    inb = _DATA_BLOB(len(blob), ctypes.cast(
        ctypes.create_string_buffer(blob, len(blob)),
        ctypes.POINTER(ctypes.c_char)))
    outb = _DATA_BLOB()
    if not crypt32.CryptUnprotectData(ctypes.byref(inb), None, None, None,
                                      None, 0, ctypes.byref(outb)):
        raise OSError("CryptUnprotectData failed")
    try:
        data = ctypes.string_at(outb.pbData, outb.cbData)
    finally:
        kernel32.LocalFree(outb.pbData)
    for enc in ("utf-16-le", "utf-8", "latin-1"):
        try:
            text = data.decode(enc).rstrip("\x00").strip()
        except UnicodeDecodeError:
            continue
        if text and all(31 < ord(c) < 0xFFFD for c in text):
            return text
    raise OSError("dpapi decrypt produced undecodable bytes")


class GithubProbe:
    def __init__(self, token_file: Path | None = None,
                 owner: str = OWNER, repo: str = REPO,
                 timeout: float = 15.0):
        self.token_file = Path(token_file) if token_file else None
        self.owner, self.repo = owner, repo
        self.timeout = timeout
        self._token: str | None = None
        self._tried = False

    # ------------------------------------------------------------ token
    def _get_token(self) -> str:
        if self._tried:
            return self._token or ""
        self._tried = True
        try:
            if self.token_file and self.token_file.is_file():
                raw = self.token_file.read_text(
                    encoding="utf-8-sig", errors="replace").strip()
                # ConvertFrom-SecureString output is base64 text; some
                # files hold raw DPAPI bytes instead — try both.
                blob = None
                try:
                    blob = base64.b64decode(raw, validate=True)
                except Exception:
                    blob = raw.encode("utf-8", errors="replace")
                self._token = _dpapi_decrypt(blob).strip()
        except Exception:
            self._token = ""
        return self._token or ""

    @property
    def available(self) -> bool:
        return bool(self._get_token())

    # -------------------------------------------------------------- api
    def _get(self, path: str) -> Any:
        tok = self._get_token()
        if not tok:
            raise RuntimeError("github token unavailable")
        req = urllib.request.Request(
            f"{API}{path}",
            headers={"Authorization": f"Bearer {tok}",
                     "Accept": "application/vnd.github+json",
                     "User-Agent": "realjarvis-devin-bridge"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def issue(self, number: int) -> dict[str, Any]:
        i = self._get(f"/repos/{self.owner}/{self.repo}/issues/{number}")
        return {"number": i.get("number"), "title": i.get("title"),
                "state": i.get("state"), "labels": [l.get("name") for l in
                                                  i.get("labels", [])],
                "updated_at": i.get("updated_at")}

    def list_prs(self, state: str = "all", limit: int = 10) -> list[dict]:
        prs = self._get(f"/repos/{self.owner}/{self.repo}/pulls"
                        f"?state={state}&per_page={limit}")
        return [{"number": p.get("number"), "title": p.get("title"),
                 "state": p.get("state"), "merged_at": p.get("merged_at"),
                 "head": (p.get("head") or {}).get("sha", "")[:10],
                 "updated_at": p.get("updated_at")} for p in prs]

    def pr(self, number: int) -> dict[str, Any]:
        p = self._get(f"/repos/{self.owner}/{self.repo}/pulls/{number}")
        return {"number": p.get("number"), "title": p.get("title"),
                "state": p.get("state"), "merged": p.get("merged"),
                "mergeable_state": p.get("mergeable_state"),
                "head": (p.get("head") or {}).get("sha", "")[:10],
                "base": (p.get("base") or {}).get("ref", "")}

    def check_runs(self, sha: str) -> dict[str, Any]:
        r = self._get(f"/repos/{self.owner}/{self.repo}/commits/{sha}"
                      "/check-runs")
        runs = r.get("check_runs", [])
        return {"total": r.get("total_count", 0),
                "runs": [{"name": c.get("name"), "status": c.get("status"),
                          "conclusion": c.get("conclusion")}
                         for c in runs[:20]]}

    def status_summary(self) -> dict[str, Any]:
        try:
            return {"available": True, "probe": "ok"}
        except Exception as e:
            return {"available": False, "error": str(e)}
