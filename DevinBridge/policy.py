"""Permission policy for ACP ``session/request_permission`` requests.

Every approval request the agent sends is classified:

    ALLOW_ONCE — answer immediately, work continues.
    DENY       — refuse outright (forbidden category: publishing,
                 destructive ops, credential access, protected paths).
    ASK_HUMAN  — cannot safely decide → the worker persists
                 NEEDS_APPROVAL, notifies the user, answers reject-once,
                 and releases. Human approval is recorded in
                 approvals.jsonl and replayed on resume.

Fail closed: anything not provably safe is ASK_HUMAN or DENY.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ALLOW, DENY, ASK = "allow_once", "deny", "ask_human"

# --- never auto-approve, ever ---------------------------------------------
DENY_CMD_RE = re.compile(
    r"(?i)\b("
    r"npm\s+publish|yarn\s+publish|pip\s+upload|twine\s+upload|"
    r"curseforge|wago|"
    r"git\s+push\b|git\s+reset\s+--hard|git\s+clean\b|"
    r"gh\s+(?:release|pr\s+(?:create|merge|close)|auth|secret)|"
    r"rm\s+-[rf]+\b|del\s+/[sq]|rmdir\s+/s|Remove-Item\b.*-Recurse|"
    r"format\s+[a-z]:|diskpart|reg\s+(?:add|delete)|"
    r"Set-ExecutionPolicy|certutil|cipher\s+/w|"
    r"net\s+(?:user|localgroup)|takeown|icacls|"
    r"schtasks\s+/(?:create|delete|change)|sc\s+(?:create|delete|config)|"
    r"curl\b.*\b(?:-X\s*(?:POST|PUT|DELETE|PATCH)|--data|-d\b)|"
    r"Invoke-(?:RestMethod|WebRequest)\b.*-Method\s+(?:Post|Put|Delete|Patch)"
    r")")

CREDENTIAL_PATH_RE = re.compile(
    r"(?i)(credentials\.toml|\.env\b|\.env\.|\.dpapi\b|id_rsa|id_ed25519|"
    r"\.pem\b|\.key\b|\.pfx\b|\.p12\b|\.aws\b|\.ssh\b|\.gnupg\b|"
    r"netrc|cookies\.|Login Data|token|secret|password|passwd)")

PROTECTED_REPO_PATH_RE = re.compile(
    r"(?i)(ForeverRoute-db70338|ForeverRoute\\+(?:Data|DB|db)|"
    r"SavedVariables|\.github\\+workflows|"
    r"DB[\\/]+forever[\\/]+(?:quest|xp)\.lua)")

SAFE_CMD_RE = re.compile(
    r"(?i)^\s*(?:"
    r"git\s+(?:status|diff|log|show|branch|add|commit|rev-parse|"
    r"ls-files|blame|tag\b(?!.*-d))|"
    r"python(?:\.exe)?\b|py(?:thon)?\s|pytest\b|"
    r"node\b|npm\s+(?:test|run|exec|ci\b(?!.*publish))|"
    r"dir\b|ls\b|type\b|cat\b|find\b|fd\b|grep\b|rg\b|"
    r"echo\b|printf\b|where\b|whoami\b|hostname\b|"
    r"mkdir\b|copy\b|xcopy\b|robocopy\b|move\b|ren\b|"
    r"luacheck\b|luac\b|lua\b|lupa\b"
    r")\b")

EDIT_KINDS = {"edit", "read", "search", "think", "fetch", "other",
              "switch_mode", "move"}
EXEC_KINDS = {"execute"}


def action_fingerprint(payload: dict[str, Any]) -> str:
    """Stable id for a permission request — used to match a human
    approval to the same action when the agent retries after resume."""
    tc = payload.get("toolCall") or {}
    kind = str(tc.get("kind") or "")
    title = str(tc.get("title") or "")
    locs = ",".join(sorted(
        str(l.get("path") or l) for l in (tc.get("locations") or [])))
    raw = json.dumps(tc.get("rawInput") or {}, sort_keys=True)[:400]
    h = hashlib.sha256()
    for part in (kind, title, locs, raw):
        h.update(part.encode("utf-8", "replace"))
        h.update(b"|")
    return h.hexdigest()[:20]


def _paths_in_scope(tc: dict, worktree: str, extra_roots: list[str]) -> bool:
    locs = [str(l.get("path") or "") for l in (tc.get("locations") or [])]
    locs = [l for l in locs if l]
    if not locs:
        return True
    roots = [str(Path(worktree)).lower().rstrip("\\/")]
    roots += [str(Path(r)).lower().rstrip("\\/") for r in extra_roots]
    for loc in locs:
        ll = loc.lower()
        if not any(ll == r or ll.startswith(r + "\\") or
                   ll.startswith(r + "/") for r in roots):
            return False
    return True


def classify_request(payload: dict[str, Any], worktree: str,
                     extra_roots: list[str] | None = None) -> dict:
    """Return {decision, reason, fingerprint, summary}."""
    tc = payload.get("toolCall") or {}
    kind = str(tc.get("kind") or "")
    title = str(tc.get("title") or "")
    raw = tc.get("rawInput") or {}
    raw_text = json.dumps(raw)[:2000]
    haystack = f"{title} {raw_text}"
    fp = action_fingerprint(payload)
    summary = (title or kind or "action")[:160]

    extra_roots = extra_roots or []

    # 1) credentials / protected paths — hard DENY anywhere in the request
    locs = " ".join(str(l.get("path") or "") for l in
                    (tc.get("locations") or []))
    path_hay = f"{locs} {raw_text}"
    if CREDENTIAL_PATH_RE.search(path_hay):
        return {"decision": DENY, "fingerprint": fp, "summary": summary,
                "reason": "credential/secret path — never auto-approved"}
    if PROTECTED_REPO_PATH_RE.search(path_hay):
        return {"decision": DENY, "fingerprint": fp, "summary": summary,
                "reason": "protected project path — never auto-approved"}
    if DENY_CMD_RE.search(haystack):
        return {"decision": DENY, "fingerprint": fp, "summary": summary,
                "reason": "denied action class (publish/destructive/"
                          "system mutation)"}

    # 2) in-scope file edits/reads — allow
    if kind in EDIT_KINDS or not kind:
        if kind == "delete":
            return {"decision": ASK, "fingerprint": fp, "summary": summary,
                    "reason": "delete operations need human approval"}
        # Writes with undisclosed targets can't be proven in-scope → ask.
        if kind in ("edit", "move") and not (tc.get("locations") or
                                            raw.get("path") or
                                            raw.get("file") or
                                            raw.get("filename")):
            return {"decision": ASK, "fingerprint": fp, "summary": summary,
                    "reason": "write target not disclosed — cannot "
                              "verify it stays in the workspace"}
        if _paths_in_scope(tc, worktree, extra_roots):
            return {"decision": ALLOW, "fingerprint": fp,
                    "summary": summary,
                    "reason": "in-workspace file operation"}
        return {"decision": ASK, "fingerprint": fp, "summary": summary,
                "reason": "path outside approved workspace"}

    # 3) command execution — allowlist only
    if kind in EXEC_KINDS or "command" in raw or "cmd" in raw:
        cmd = str(raw.get("command") or raw.get("cmd") or title)
        if SAFE_CMD_RE.search(cmd) and not DENY_CMD_RE.search(cmd):
            return {"decision": ALLOW, "fingerprint": fp,
                    "summary": summary,
                    "reason": "routine safe command"}
        return {"decision": ASK, "fingerprint": fp, "summary": summary,
                "reason": "command not on the safe list"}

    return {"decision": ASK, "fingerprint": fp, "summary": summary,
            "reason": f"unclassified action kind '{kind}'"}
