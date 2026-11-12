"""LangGraph supervisor — Jarvis's project-lead brain over DevinBridge.

Graph: OBSERVE -> REASON -> PLAN -> DISPATCH -> MONITOR -> VERIFY
       -> REFLECT -> (next tick: OBSERVE ...)

Deterministic reasoner ranks REAL issues from measured artifacts —
no hardcoded task ids. When no deterministic issue exists, the
existing planner/proposal path is flagged for a model consult.
All dispatch goes through the SAME coordinator (grant-scoped).
Checkpoint: SQLite via langgraph-checkpoint-sqlite (restart-proof).
Single-writer: .supervisor.lock so two graphs never write the queue.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from . import evidence_gap
from .bridge_store import atomic_write_json, file_lock, read_json

BRIDGE = Path(__file__).resolve().parent
CKPT = BRIDGE / "supervisor_checkpoints.sqlite"
SLOCK = BRIDGE / ".supervisor.lock"
LOG = BRIDGE / "supervisor_log.jsonl"
STATE_OUT = BRIDGE / "supervisor_state.json"
MASTER_GOAL = "GOAL-FOREVERROUTE-PLAYABLE-1TO60"
MAX_SPAWN_PER_CYCLE = 1


class SupState(TypedDict, total=False):
    obs: dict
    issues: list
    decision: dict
    plan: dict
    spawned: list
    monitor: dict
    verified: list
    route_gate: dict
    reflect: dict
    cycles: int
    ai: dict


# ------------------------------------------------------------- nodes
def n_observe(state: SupState, ctx) -> dict:
    coord = ctx["coord"]
    tasks = coord.list_tasks()
    cov = evidence_gap.coverage(coord.root)
    wt = evidence_gap._worktree(coord.root)
    rs = evidence_gap._research_state(wt)
    hyjal_supp = wt / "Generated" / "ForeverRoute_Hyjal_Supplement.lua"
    goals = read_json(coord.root / "goals.json", {})
    obs = {
        "ts": time.time(),
        "goal_open": (goals.get(MASTER_GOAL) or {}).get("status") != "COMPLETE",
        "counts": {s: sum(1 for t in tasks if t["status"] == s)
                   for s in ("RUNNING", "PENDING", "READY", "FAILED",
                             "COMPLETE", "NEEDS_APPROVAL",
                             "WAITING_APPROVAL")},
        "coverage": cov,
        "research": {"batch_index": rs.get("batch_index"),
                     "resolved": len(rs.get("resolved_quest_ids", [])),
                     "recalc_spawned": rs.get("recalc_spawned")},
        "unresolved": len(evidence_gap._unresolved_quest_ids(coord.root)),
        "hyjal_supp_exists": hyjal_supp.exists(),
        "hyjal_horde_research": (wt / "tools" /
                                "hyjal_horde_research.json").exists(),
        "hyjal_horde_build": (wt / "tools" /
                              "hyjal_horde_build_report.json").exists(),
        "gate_inversions": cov.get("gate_inversions"),
        "ungrounded": cov.get("ungrounded_rows"),
        "task_ids": {t["id"]: t["status"] for t in tasks},
    }
    return {"obs": obs}


def n_reason(state: SupState, ctx) -> dict:
    """Rank issues from measured reality — largest unproven gap first.
    Deterministic scorer; model-consult flag when nothing concrete."""
    obs = state["obs"]
    cov = obs["coverage"]
    tids = obs["task_ids"]
    issues = []

    def have(prefix, statuses=("COMPLETE", "RUNNING", "PENDING", "READY")):
        return any(i.startswith(prefix) and tids[i] in statuses
                   for i in tids)

    # 0) route-quality standard gate: validator FAIL => reject work,
    # spawn bounded repair with the exact failing assertions
    if (state.get("route_gate") or {}).get("verdict") == "FAIL" \
            and not have("GOAL-FR-ROUTE-VQFIX"):
        issues.append({"kind": "route_quality_regression",
                       "priority": 500,
                       "why": "route-construction standard suite FAILED "
                              "— validator rejects generated routes"})
    # 1) Hyjal: research done -> build running/pending -> else research
    if not obs["hyjal_horde_research"] and not have("GOAL-FR-HYJAL-DATA"):
        issues.append({"kind": "hyjal_horde_research", "priority": 90,
                       "why": "Hyjal supplement is Alliance-only; Horde "
                              "quest/coord evidence missing"})
    if (obs["hyjal_horde_research"] and not obs["hyjal_horde_build"]
            and not have("GOAL-FR-HYJAL-BUILD")):
        issues.append({"kind": "hyjal_horde_build", "priority": 88,
                       "why": "Horde research landed; sections not built"})
    # 2) research frontier
    if obs["unresolved"] > 0 and not have("GOAL-FR-WP-1TO60-DATA-N"):
        issues.append({"kind": "objective_batch", "priority": 70,
                       "why": f"{obs['unresolved']} objective quests "
                              "still lack leads"})
    # 3) gate inversions (real metric)
    if obs["gate_inversions"] and not have("GOAL-FR-WP-1TO60-GATE"):
        issues.append({"kind": "gate_inversions", "priority": 65,
                       "why": f"{obs['gate_inversions']} gate inversions "
                              "in recalc need data fixes"})
    # 4) unlocated rows still massive -> deeper evidence task
    if (obs["coverage"].get("objective_rows_unlocated") or 0) > 0 \
            and obs["unresolved"] == 0 \
            and not have("GOAL-FR-WP-1TO60-ROW"):
        issues.append({"kind": "row_level_gaps", "priority": 60,
                       "why": f"{obs['coverage'].get('objective_rows_unlocated')} "
                              "route rows unlocated at row level"})
    issues.sort(key=lambda i: -i["priority"])
    decision = issues[0] if issues else {
        "kind": "model_consult", "priority": 10,
        "why": "no deterministic issue; consult planner/model"}
    return {"issues": issues, "decision": decision}


def n_plan(state: SupState, ctx) -> dict:
    d = state["decision"]
    obs = state["obs"]
    wt = str(evidence_gap._worktree(ctx["coord"].root))
    if d["kind"] == "model_consult":
        # real AI planning: consume a finished SWE-2 consult first,
        # else start one in background (never blocks the daemon tick)
        from . import ai_planner, cdp
        obs_state = dict(state.get("obs") or {})
        obs_state["route_gate"] = state.get("route_gate")
        ctx_dict = ai_planner.build_context(ctx["coord"], obs_state)
        prop = ai_planner.consume(ctx["coord"], obs_state)
        if prop and not prop.get("rejected"):
            res = cdp.new_issue_proposal(
                ctx["coord"], prop["kind"], prop["title"],
                prop["prompt"], wt, prop["signature"],
                prop["evidence_refs"], acceptance=prop["acceptance"],
                priority=prop["priority"])
            return {"plan": None, "ai": {
                "status": "TASK_PROPOSED" if res.get("ok") else "BLOCKED",
                "proposal_id": res.get("proposal_id"),
                "title": prop["title"],
                "deduplicated": res.get("deduplicated", False)}}
        if prop and prop.get("rejected"):
            return {"plan": None, "ai": {
                "status": "BLOCKED",
                "why": f"AI proposal rejected: {prop['why']}",
                "title": prop.get("title")}}
        st = ai_planner.maybe_consult(ctx["coord"], ctx_dict)
        return {"plan": None, "ai": st}
    specs = {
        "route_quality_regression": dict(
            tid="GOAL-FR-ROUTE-VQFIX1",
            title="ROUTE-QUALITY-REGRESSION: standard suite failing",
            prompt="Jarvis route-quality gate rejects generated route "
                   "work (tests.test_route_quality_validator failing). "
                   "Per FOREVERROUTE_ROUTE_CONSTRUCTION_STANDARD_v1 a "
                   "route that fails validation is NOT accepted. Fix the "
                   "route generator/data — do NOT weaken the validator "
                   "or tests. Write tools/route_quality_fix_report.json "
                   "with: failing rule, root cause, fix applied.",
            acceptance=[{"type": "file_exists",
                         "path": "tools/route_quality_fix_report.json"}]),
        "hyjal_horde_research": dict(
            tid="GOAL-FR-HYJAL-DATA2",
            title="Hyjal Horde evidence round 2 (coords+prereqs)",
            prompt="Verify Hyjal Horde quest coords/prereqs for client "
                   "1.60.x via web_search/web_fetch; extend "
                   "tools/hyjal_horde_research.json with VERIFIED "
                   "objective locations; write "
                   "tools/hyjal_coord_verification.json.",
            acceptance=[{"type": "file_exists",
                         "path": "tools/hyjal_coord_verification.json"}]),
        "hyjal_horde_build": dict(
            tid="GOAL-FR-HYJAL-BUILD2",
            title="Rebuild Horde Hyjal sections from verified coords",
            prompt="tools/hyjal_horde_research.json + "
                   "hyjal_coord_verification.json exist: generate Horde "
                   "55-60 sections incl. TAUREN:HUNTER into "
                   "Generated/ForeverRoute_Hyjal_Supplement.lua; write "
                   "tools/hyjal_horde_build_report.json.",
            acceptance=[{"type": "file_exists",
                         "path": "tools/hyjal_horde_build_report.json"}]),
        "gate_inversions": dict(
            tid="GOAL-FR-WP-1TO60-GATE1",
            title="Fix classified gate inversions (bounded)",
            prompt="docs/autonomy/gate_inversion_analysis.md classifies "
                   "the 18 inversions: apply the bounded per-case fixes "
                   "it marks as data errors (prereq level rows only); "
                   "write tools/gate_fix_report.json with before/after "
                   "count. Legal level-gating stays untouched.",
            acceptance=[{"type": "file_exists",
                         "path": "tools/gate_fix_report.json"}]),
        "row_level_gaps": dict(
            tid="GOAL-FR-WP-1TO60-ROW1",
            title="Row-level unlocated gap deep-dive",
            prompt="Objective quests resolved but "
                   f"{obs['coverage'].get('objective_rows_unlocated')} "
                   "route rows still unlocated: identify top 20 rows by "
                   "band; classify which need NPC coords vs object vs "
                   "travel; write tools/row_gap_analysis.json.",
            acceptance=[{"type": "file_exists",
                         "path": "tools/row_gap_analysis.json"}]),
    }
    s = specs.get(d["kind"])
    if not s:
        return {"plan": None}
    if s["tid"] in obs["task_ids"]:
        return {"plan": None}
    s["worktree"] = wt
    return {"plan": s}


def n_dispatch(state: SupState, ctx) -> dict:
    plan = state.get("plan")
    if not plan:
        return {"spawned": []}
    coord = ctx["coord"]
    if coord.global_holds():
        return {"spawned": [], "dispatch_blocked":
                "global holds: " + "; ".join(coord.global_holds())}
    res = coord.add_task(
        plan["tid"], plan["title"], plan["prompt"], plan["worktree"],
        priority=42, acceptance=plan["acceptance"], approved=True,
        scope="production", owner="goal",
        generated_by="supervisor_graph",
        reason=state["decision"]["why"], max_attempts=3)
    if res.get("added"):
        coord._mutate(plan["tid"], lambda x: x.__setitem__(
            "goal_kind", "analyze"))
        coord.dispatch(plan["tid"])
        return {"spawned": [plan["tid"]]}
    return {"spawned": []}


def n_monitor(state: SupState, ctx) -> dict:
    coord = ctx["coord"]
    return {"monitor": {
        "orchestration": evidence_gap.idle_state(coord),
        "counts": state["obs"]["counts"]}}


def n_verify(state: SupState, ctx) -> dict:
    """Spot-check: COMPLETE tasks must have real non-empty artifacts,
    AND the route-quality standard suite must pass (independent gate —
    Jarvis re-runs it, not the worker's own claim)."""
    import subprocess
    coord = ctx["coord"]
    wt = evidence_gap._worktree(coord.root)
    verified = []
    for t in coord.list_tasks():
        if t["status"] != "COMPLETE":
            continue
        acc = t.get("acceptance") or []
        ok_all = True
        for a in acc:
            if a.get("type") == "file_exists":
                f = wt / a["path"]
                if not f.exists() or f.stat().st_size < 40:
                    ok_all = False
        if ok_all and acc:
            verified.append(t["id"])
    # standard gate: route construction quality suite (H1/H2/H3/H5,
    # GATE-NPC, bounce) — independent of any single task's report
    gate = {"verdict": "SKIPPED"}
    try:
        r = subprocess.run(
            [evidence_gap._test_python() if hasattr(
                evidence_gap, "_test_python") else "python",
             "-m", "unittest",
             "tests.test_route_quality_validator"],
            cwd=str(wt), capture_output=True, timeout=120,
            creationflags=0x08000000)
        gate = {"verdict": "PASS" if r.returncode == 0 else "FAIL",
                "exit": r.returncode,
                "tail": r.stdout.decode("utf-8", "replace")[-200:]}
    except Exception as e:
        gate = {"verdict": "BLOCKED", "error": str(e)[:120]}
    return {"verified": verified[-10:], "route_gate": gate}


def n_reflect(state: SupState, ctx) -> dict:
    entry = {"ts": time.time(),
             "cycles": (state.get("cycles") or 0) + 1,
             "decision": state["decision"],
             "spawned": state.get("spawned", []),
             "monitor": state.get("monitor", {}),
             "route_gate": state.get("route_gate"),
             "verified_tail": state.get("verified", [])[-5:]}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    # dashboard-visible state
    atomic_write_json(STATE_OUT, {
        "supervisor": "langgraph",
        "cycles": entry["cycles"],
        "last_decision": state["decision"],
        "last_spawned": state.get("spawned", []),
        "orchestration": (state.get("monitor") or {}).get("orchestration"),
        "route_gate": state.get("route_gate"),
        "ai": state.get("ai"),
        "verified_tail": state.get("verified", [])[-5:],
        "issues_ranked": [i["kind"] for i in state.get("issues", [])],
        "ts": entry["ts"]})
    return {"cycles": entry["cycles"], "reflect": entry}


def build_graph(coord):
    def wrap(fn):
        return lambda s: fn(s, {"coord": coord})
    g = StateGraph(SupState)
    g.add_node("observe", wrap(n_observe))
    g.add_node("reason", wrap(n_reason))
    g.add_node("plan", wrap(n_plan))
    g.add_node("dispatch", wrap(n_dispatch))
    g.add_node("monitor", wrap(n_monitor))
    g.add_node("verify", wrap(n_verify))
    g.add_node("reflect", wrap(n_reflect))
    g.set_entry_point("observe")
    for a, b in (("observe", "reason"), ("reason", "plan"),
                 ("plan", "dispatch"), ("dispatch", "monitor"),
                 ("monitor", "verify"), ("verify", "reflect")):
        g.add_edge(a, b)
    g.add_edge("reflect", END)
    return g


def supervisor_tick(coord) -> dict:
    """One graph cycle per daemon tick; checkpoint survives restarts;
    single-writer lock prevents double-queue writes."""
    with file_lock(SLOCK):
        with SqliteSaver.from_conn_string(str(CKPT)) as saver:
            g = build_graph(coord).compile(checkpointer=saver)
            cfg = {"configurable": {"thread_id": "foreverroute-1to60"}}
            out = g.invoke({}, config=cfg)  # no seed: checkpoint carries cycles
    return {"decision": out.get("decision"),
            "spawned": out.get("spawned"),
            "monitor": out.get("monitor"),
            "cycles": out.get("cycles")}


if __name__ == "__main__":
    from .daemon import make_coordinator
    print(json.dumps(supervisor_tick(make_coordinator()),
                     ensure_ascii=False, indent=1))
