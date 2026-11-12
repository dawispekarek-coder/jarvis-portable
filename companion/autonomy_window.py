"""24-hour owner-approved auto-approval window for Companion tools.

NOT an infinite auto_approve flag: a file with a hard UTC expiry,
a conservative allowlist of reversible, low-blast-radius actions,
and an append-only audit log. After expiry the previous approval
policy resumes automatically (check() returns False forever).

Owner activation: 2026-11-11, scope = Companion tool approvals only.
Never auto-renews. Irreversible/high-risk ops stay human-gated.
"""
from __future__ import annotations
import json, time, hashlib
from pathlib import Path

BASE = Path(__file__).resolve().parent
WINDOW = BASE / "autonomy_window.json"
AUDIT = BASE / "autonomy_audit.jsonl"

# Only reversible web-page interactions may auto-approve. Real Windows
# UI automation (desktop_*) and everything else stays human-gated.
AUTO_ALLOW = frozenset({"browser_click", "browser_fill"})


def _load():
    try:
        return json.loads(WINDOW.read_text(encoding="utf-8"))
    except Exception:
        return {}


def status():
    w = _load()
    exp = float(w.get("expires_epoch") or 0)
    return {"active": bool(w) and time.time() < exp,
            "activated_at_utc": w.get("activated_at_utc"),
            "expires_utc": w.get("expires_utc"),
            "auto_allow": sorted(AUTO_ALLOW)}


def check(name, args):
    """True only inside the window AND for allowlisted tool names.
    Every decision (grant/deny) is appended to the audit log."""
    w = _load()
    exp = float(w.get("expires_epoch") or 0)
    inside = bool(w) and time.time() < exp
    grant = inside and name in AUTO_ALLOW
    sig = hashlib.sha256(json.dumps(
        [name, args], sort_keys=True, default=str).encode()).hexdigest()[:16]
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "tool": name,
                            "args_sig": sig, "decision": "auto_approved" if grant else "human_gate",
                            "window_active": inside},
                           ensure_ascii=False) + "\n")
    return grant
