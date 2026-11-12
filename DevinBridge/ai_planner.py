"""ai_planner — real SWE-2 High planning layer for the LangGraph supervisor.

When the deterministic scorer finds no concrete issue (model_consult),
this module asks Devin SWE-2 High — in an isolated read-only ACP
`plan`-mode session — to propose the next most valuable task for
GOAL-FOREVERROUTE-PLAYABLE-1TO60, as strict JSON.

Guards (never bypassed):
- runs in a background thread: the daemon tick is never blocked by a
  long model call;
- cooldown 20 min between consults; 2 h if project context unchanged;
- daily consult budget (12/day);
- prompt + session timeouts;
- proposal schema + scope validation vs CDP_PROGRAM allowed kinds /
  paths before it can become a proposal;
- dedupe via cdp fingerprint and existing task/proposal titles;
- NO_ACTION and invalid proposals never create work;
- all authority still flows through cdp.new_issue_proposal +
  handoff_tick (program, budget, holds, approvals).
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path

from .bridge_store import read_json, atomic_write_json
from . import learner

BRIDGE = Path(__file__).resolve().parent
STATE = BRIDGE / "ai_planner_state.json"
COOLDOWN_S = 20 * 60          # min between consults
UNCHANGED_S = 2 * 3600        # if context identical, need 2h
CONSULT_TIMEOUT_S = 15 * 60   # a pending consult older than this is dead
MAX_CALLS_PER_DAY = 12
PROMPT_TIMEOUT = 420          # model may take a while; bounded
REQ_TIMEOUT = 60
MODEL = "swe-2-high"

_lock = threading.Lock()
_thread: threading.Thread | None = None


def _load() -> dict:
    return read_json(STATE, {}) or {}


def _save(d: dict) -> None:
    atomic_write_json(STATE, d)


def _ctx_hash(ctx: dict) -> str:
    return hashlib.sha256(json.dumps(
        ctx, sort_keys=True, default=str).encode()).hexdigest()[:16]


def build_context(coord, obs: dict) -> dict:
    """Structured, evidence-only context for the planner — never the
    last chat line."""
    st = coord._load()
    tasks = st.get("tasks", {})
    recent_done = [t["id"] for t in sorted(
        tasks.values(), key=lambda t: str(t.get("completed_at") or ""),
        reverse=True) if t["status"] == "COMPLETE"][:8]
    failed = [{"id": t["id"], "error": str(t.get("last_error") or "")[:200]}
              for t in tasks.values() if t["status"] == "FAILED"][-8:]
    def _dispatchable(t):
        """Work that can actually run NOW — a READY task held by
        not_before, a human gate, or a non-production scope does not
        count as queue content."""
        if t["status"] in ("DISPATCHED", "RUNNING", "VERIFYING",
                           "NEEDS_APPROVAL"):
            return True
        if t["status"] != "READY":
            return False
        if float(t.get("not_before") or 0) > time.time():
            return False
        if t.get("human_gate"):
            return False
        return t.get("scope") == "production"
    open_t = [t["id"] for t in tasks.values() if _dispatchable(t)]
    prog = read_json(
        coord.root / "autonomy_scope" / "CDP_PROGRAM.json", {})
    return {
        "master_goal": "GOAL-FOREVERROUTE-PLAYABLE-1TO60 — genuinely "
                       "playable 1-60 leveling addon, 56 profiles, "
                       "728 V3 sections, verified data only",
        "obs": {k: obs.get(k) for k in (
            "unresolved", "gate_inversions", "coverage",
            "hyjal_horde_research", "hyjal_horde_build")},
        "route_gate": obs.get("route_gate"),
        "open_tasks": open_t[:10],
        "queue_empty": not open_t,
        "recent_completed": recent_done,
        "recent_failed": failed,
        "route_standard": "docs/route_engineering/"
                          "FOREVERROUTE_ROUTE_CONSTRUCTION_STANDARD_v1.md "
                          "(mandatory construction rules: eligibility, "
                          "prereqs, NPC identity, travel feasibility, "
                          "no zone ping-pong)",
        "learned_lessons": learner.lessons(
            coord.root,
            hints=[*open_t[:3], "route", "waypoint", "quest"]),
        "known_gaps": [
            "real travel times / transport edges unverified",
            "Hidden Enemies fix lacks in-game verification",
            "objective rows unlocated at row level",
            "Hyjal sections built but not proven in-client",
            "56-profile regression not yet run end-to-end",
        ],
        "allowed_kinds": prog.get("kinds", []),
        "allowed_paths": prog.get("allowed_paths", []),
        "worktree": prog.get("worktrees", [""])[0],
    }


_PROMPT_TMPL = """You are the planning brain of Jarvis supervising the ForeverRoute WoW addon project (master goal: playable 1-60 leveling routes).
You are in READ-ONLY plan mode: no tools, no writes, no commands.

CURRENT PROJECT STATE (evidence only, do not invent facts):
{ctx}

MANDATORY: any task touching routes/quests/waypoints MUST instruct the worker to read and follow docs/route_engineering/FOREVERROUTE_ROUTE_CONSTRUCTION_STANDARD_v1.md inside the worktree — routes violating it get rejected by the validator gate.
Also instruct the worker to end its report with one or more "LEARNED: <rule>" lines — a reusable rule distilled from what it did (why this approach, what failed and why). Check learned_lessons in context and build on them instead of re-learning.
Decide the SINGLE most valuable next engineering task that advances the master goal. It may be a kind of work never done before.
If recent_failed is non-empty, read each "error": never re-propose the same approach that already failed — either propose a diagnostic task to find the root cause, or a materially different approach, and say in "why" how this avoids the recorded failure.
IMPORTANT: the master goal is not release-ready until proven. If queue_empty is true, you MUST propose work from the known gaps or discover a new one — NO_ACTION is allowed only for a hard external blocker (permissions, credentials, account actions), never for "nothing to do".
Return ONLY a JSON object, no prose. If you reason first, the JSON object MUST be the very last thing in your reply — nothing after it. Exactly this schema:
{{"action":"PROPOSE","title":"short task title","priority":0-100,
 "kind":"one of {kinds}","problem":"the real gap you found",
 "evidence_refs":["file/path showing the gap",...],
 "why":"why this matters for the goal",
 "prompt":"concrete instructions for the Devin worker",
 "mutate":["allowed path prefixes it may change"],
 "depends_on":[],
 "acceptance":[{{"type":"file_exists","path":"relative/path/inside/allowed"}},
   {{"type":"test","runner":"unittest","args":["tests.test_route_quality_validator"]}}],
 "improvement_metric":"measurable change expected"}}
or {{"action":"NO_ACTION","why":"concrete blocker"}} if truly blocked.
evidence_refs MUST be real files inside the worktree (e.g. tools/*.json, docs/**/*.md). mutate/acceptance paths must stay inside allowed_paths.
For kind "repair-small" or "test-add" you MUST include at least one
acceptance check of type "test" with runner "unittest" or "pytest" —
otherwise the program gate refuses the proposal."""


def _extract_json(text: str) -> dict | None:
    """Robust JSON extraction: plan-mode models often wrap the object in
    prose or code fences. Try fenced block first, then every balanced
    {...} candidate (longest first) until one parses."""
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    cands = [m.group(1)] if m else []
    # balanced-brace candidates: each '{' start, its matching '}'
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for s in starts:
        depth = 0
        for e in range(s, len(text)):
            if text[e] == "{":
                depth += 1
            elif text[e] == "}":
                depth -= 1
                if depth == 0:
                    cands.append(text[s:e + 1])
                    break
    for c in sorted(cands, key=len, reverse=True):
        try:
            d = json.loads(c)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and ("action" in d or "title" in d):
            return d
    return None


def _consult_thread(context: dict) -> None:
    """Runs in daemon thread; writes outcome into ai_planner_state."""
    st = _load()
    try:
        from .acp_client import DevinAcpClient
        cli = DevinAcpClient(request_timeout=REQ_TIMEOUT)
        sid = ""
        try:
            cli.start()
            ses = cli.session_new(context["worktree"], model=MODEL,
                                  mode="plan", timeout=180)
            sid = ses.get("sessionId", "")
            kinds = ", ".join(context["allowed_kinds"])
            res = cli.session_prompt(
                sid, _PROMPT_TMPL.format(ctx=json.dumps(
                    context, ensure_ascii=False, indent=1), kinds=kinds),
                timeout=PROMPT_TIMEOUT)
            proposal = _extract_json(res.text or "")
            st.update({"pending_result": proposal,
                       "last_stop_reason": res.stop_reason,
                       "last_raw_tail": (res.text or "")[-400:],
                       "consult_status": "DONE" if proposal else "PARSE_FAIL"})
        finally:
            if sid:
                try:
                    cli.session_close(sid)
                except Exception:
                    pass
            try:
                cli.stop()
            except Exception:
                pass
    except Exception as e:  # noqa: BLE001 — record, never crash daemon
        st["consult_status"] = f"ERROR {type(e).__name__}"
        st["last_error"] = str(e)[:200]
    st["pending"] = False
    _save(st)


def maybe_consult(coord, context: dict) -> dict:
    """Start an AI consult if guards allow. Non-blocking."""
    global _thread
    st = _load()
    now = time.time()
    day = time.strftime("%Y-%m-%d")
    if st.get("pending"):
        # watchdog: a consult pending longer than CONSULT_TIMEOUT_S means
        # its thread died or hung on ACP I/O — recover instead of
        # idling forever (observed: 43 min stuck, queue starved)
        if now - float(st.get("last_call_ts") or 0) > CONSULT_TIMEOUT_S:
            st.update({"pending": False,
                       "consult_status": "TIMEOUT_RECOVERED"})
            _save(st)
        else:
            return {"status": "AI_REASONING",
                    "why": "consult in flight"}
    if st.get("day") != day:
        st.update({"day": day, "calls_today": 0})
    if (st.get("calls_today") or 0) >= MAX_CALLS_PER_DAY:
        return {"status": "IDLE_NO_ACTION", "why": "daily consult budget"}
    last = float(st.get("last_call_ts") or 0)
    h = _ctx_hash(context)
    gap = COOLDOWN_S if h != st.get("last_ctx_hash") else UNCHANGED_S
    # owner rule: an empty queue while the master goal is unproven must
    # never idle for the full unchanged-context cooldown — retry on the
    # short cooldown so the planner keeps inventing release work
    if context.get("queue_empty") and gap > COOLDOWN_S:
        gap = COOLDOWN_S
    # a failed consult (timeout/parse/error) produced no work — retry
    # soon instead of burning the full cooldown on nothing
    if str(st.get("consult_status", "")).startswith(
            ("ERROR", "PARSE_FAIL", "TIMEOUT")):
        gap = min(gap, 300)
    if now - last < gap:
        return {"status": "IDLE_NO_ACTION",
                "why": f"cooldown {int(gap - (now - last))}s "
                       f"({'ctx changed' if h != st.get('last_ctx_hash') else 'ctx same'})"}
    st.update({"last_call_ts": now, "last_ctx_hash": h,
               "calls_today": (st.get("calls_today") or 0) + 1,
               "pending": True, "consult_status": "RUNNING",
               "pending_result": None})
    _save(st)
    with _lock:
        _thread = threading.Thread(target=_consult_thread,
                                   args=(context,), daemon=True)
        _thread.start()
    return {"status": "AI_REASONING", "why": "SWE-2 High consult started"}


def validate_proposal(d: dict, coord, obs: dict) -> tuple[bool, str]:
    """Schema + scope validation; rejects invented/unsafe proposals."""
    if not isinstance(d, dict):
        return False, "not a JSON object"
    if d.get("action") == "NO_ACTION":
        return False, f"NO_ACTION: {d.get('why', '')[:120]}"
    if d.get("action") != "PROPOSE":
        return False, "missing action field"
    prog = read_json(
        coord.root / "autonomy_scope" / "CDP_PROGRAM.json", {})
    kinds = set(prog.get("kinds") or [])
    if d.get("kind") not in kinds:
        return False, f"kind {d.get('kind')} not in program {sorted(kinds)}"
    allowed = [str(x).replace("\\", "/").rstrip("/")
               for x in prog.get("allowed_paths", [])]
    def _in_scope(p):
        p = str(p).replace("\\", "/")
        return not Path(p).is_absolute() and ".." not in Path(p).parts \
            and any(p == a or p.startswith(a + "/") for a in allowed)
    if not d.get("evidence_refs"):
        return False, "no evidence_refs — unverifiable proposal"
    acc = d.get("acceptance") or []
    if not acc or not all(
            c.get("type") == "test" and c.get("runner")
            in ("pytest", "unittest", "python")
            or _in_scope(c.get("path", ""))
            for c in acc):
        return False, "acceptance missing or out of allowed_paths"
    if d.get("kind") in ("repair-small", "test-add") and not any(
            c.get("type") == "test" for c in acc):
        return False, ("kind needs a {'type':'test'} acceptance — "
                       "program gate refuses without it")
    if not all(_in_scope(m) for m in (d.get("mutate") or allowed[:1])):
        return False, "mutate paths out of allowed_paths"
    if not d.get("title") or not d.get("prompt") \
            or len(str(d["prompt"])) < 60:
        return False, "title/prompt missing or too thin"
    # dedupe: existing task with same title or same fingerprint source
    st = coord._load()
    t = str(d["title"]).lower()
    for task in st.get("tasks", {}).values():
        if task.get("status") in ("READY", "RUNNING", "DISPATCHED",
                                  "VERIFYING", "NEEDS_APPROVAL") \
                and str(task.get("title", "")).lower() == t:
            return False, "duplicate of open task"
    return True, ""


def consume(coord, obs: dict) -> dict | None:
    """Pick up a finished AI proposal; returns validated proposal or
    None (with rejection recorded)."""
    st = _load()
    if st.get("pending") or st.get("pending_result") is None:
        return None
    d = st["pending_result"]
    st["pending_result"] = None
    ok, why = validate_proposal(d, coord, obs)
    st["last_validation"] = {"ok": ok, "why": why,
                             "title": str(d.get("title", ""))[:80]}
    _save(st)
    if not ok:
        return {"rejected": True, "why": why,
                "title": str(d.get("title", ""))[:80]}
    sig_src = f"{d.get('kind')}|{d.get('title')}|{d.get('problem')}"
    return {
        "kind": d["kind"], "title": str(d["title"])[:160],
        "prompt": str(d["prompt"]),
        "signature": hashlib.sha256(sig_src.encode()).hexdigest()[:24],
        "evidence_refs": list(d.get("evidence_refs") or [])[:6],
        "acceptance": list(d["acceptance"]),
        "priority": max(0, min(100, int(d.get("priority") or 60)))}


def status() -> dict:
    st = _load()
    return {"pending": bool(st.get("pending")),
            "consult_status": st.get("consult_status"),
            "calls_today": st.get("calls_today"),
            "last_validation": st.get("last_validation"),
            "last_error": st.get("last_error")}
