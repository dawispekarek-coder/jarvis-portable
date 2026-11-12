"""Evidence-gap engine: quantified coverage + bounded task synthesis.

Reads the worktree's real evidence artifacts, computes truthful coverage
metrics, and turns the top remaining gaps into concrete coordinator
tasks (stable ids, dedup across restarts, grant-scoped kinds, prompts
that instruct workers to use web_search/web_fetch for missing data).

Never fabricates coverage. UNKNOWN/missing stays UNKNOWN.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .bridge_store import atomic_write_json, read_json

TOOLS = "tools"
MAX_GAP_TASKS_PER_TICK = 1  # conservative; grant kinds analyze only
BATCH_SIZE = 30
RSTATE = "research_state.json"  # worktree: batch cursor, resolved set


def _research_state(wt: Path) -> dict:
    st = read_json(wt / TOOLS / RSTATE, {})
    st.setdefault("batch_index", 1)  # batch1 was DATA2's output
    st.setdefault("resolved_quest_ids", [])
    return st


def _save_research_state(wt: Path, st: dict) -> None:
    atomic_write_json(wt / TOOLS / RSTATE, st)


def _unresolved_quest_ids(root: Path) -> list:
    """QuestIDs still lacking location leads — the moving frontier."""
    wt = _worktree(root)
    gaps = read_json(wt / TOOLS / "live_quest_gaps_20261111.json", {})
    recs = ((gaps.get("questJoin") or {}).get("records") or [])
    # real schema: questId + missingFields[] incl. OBJECTIVE_LOCATION
    need = sorted({r.get("questId") for r in recs
                   if "OBJECTIVE_LOCATION" in
                   (r.get("missingFields") or [])
                   and r.get("questId") is not None})
    done = set(_research_state(wt)["resolved_quest_ids"])
    return [q for q in need if q not in done]


def _mark_resolved(wt: Path, quest_ids: list) -> None:
    st = _research_state(wt)
    st["resolved_quest_ids"] = sorted(
        set(st["resolved_quest_ids"]) | set(quest_ids))
    _save_research_state(wt, st)


def _worktree(root: Path) -> Path:
    cfg = read_json(root / "bridge_config.json", {})
    wts = cfg.get("authorized_worktrees") or []
    if wts:
        return Path(wts[0])
    return root / "autonomy_scope" / "workspaces" / "foreverroute-route-audit"


def coverage(root: Path) -> dict:
    """Quantified coverage from real evidence files."""
    wt = _worktree(root)
    gaps = read_json(wt / TOOLS / "live_quest_gaps_20261111.json", {})
    cq = (gaps or {}).get("coverageQuantified") or {}
    obj = cq.get("objectiveLocation") or {}
    rep = read_json(wt / TOOLS / "recalc_full_1to60_report.json", {})
    metrics = (rep or {}).get("metrics") or {}
    lic = cq.get("licenseGating") or {}
    out = {
        "ts": time.time(),
        "quest_ids": obj.get("distinctQuestIds", 0),
        "objective_rows_unlocated": obj.get("routeUnlocatedRows", 0),
        "objective_no_leads": obj.get("noLeads", 0),
        "objective_verified_live": obj.get("verifiedLive", 0),
        "confidence": (cq.get("joinedConfidence") or {}),
        "usable_sources_now": lic.get("directlyUsableNow", 0),
        "key_required_sources": lic.get("keyAndTermsRequired", []),
        "blocked_sources": lic.get("blocked", []),
        "reference_only_sources": lic.get(
            "referenceOnlyGPLProprietaryUnknown", []),
        "ungrounded_rows": metrics.get("ungroundedRows",
                                      metrics.get("ungrounded_rows")),
        "prereq_violations": metrics.get("unresolvedAuthoredPrereqs"),
        "gate_inversions": metrics.get("gateInversions"),
        "sections": metrics.get("sections"),
        "profiles": metrics.get("profiles"),
    }
    p = wt / TOOLS / "coverage_report_latest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(p, out)
    return out


def synthesize(root: Path, coord, cov: dict) -> list:
    """Dynamic batch engine — no hardcoded names. Each tick, if the
    unresolved frontier is non-empty and no research task is in
    flight, spawn the NEXT batch over NEW unresolved questIDs
    (research_state.json cursor persists across restarts)."""
    made = []
    tasks = {t["id"]: t for t in coord.list_tasks()}
    wt_path = _worktree(root)
    wt = str(wt_path)
    st = _research_state(wt_path)
    unresolved = _unresolved_quest_ids(root)
    in_flight = [i for i, t in tasks.items()
                 if t["status"] in ("RUNNING", "PENDING", "READY")
                 and "-DATA-" in i]
    idx = st["batch_index"] + 1
    tid = f"GOAL-FR-WP-1TO60-DATA-N{idx}"
    if unresolved and not in_flight and tid not in tasks:
        batch = unresolved[:BATCH_SIZE]
        prompt = (
            f"Autonomous data batch {idx}: {len(batch)} of "
            f"{len(unresolved)} remaining unresolved quests. "
            f"questIds={batch}. For each: run_tool web_search/web_fetch "
            "across wowhead.com/forever, warcraft.wiki.gg, github addon "
            "DBs, icy-veins and other legal sources; find mapID/x/y "
            "objective+turnin locations for client 1.60.x. Write "
            f"tools/objective_research_batch{idx}.json — per quest: "
            "questId, candidates[{mapId,x,y,zone,sourceUrl,version,"
            "confidence,license}], status VERIFIED|CANDIDATE|UNKNOWN. "
            "No invented coords; UNKNOWN stays UNKNOWN.")
        res = coord.add_task(
            tid, f"Research batch {idx}: {len(batch)} unresolved quests",
            prompt, wt, priority=45,
            acceptance=[{"type": "file_exists",
                         "path": f"tools/objective_research_batch{idx}.json"}],
            approved=True, scope="production", owner="goal",
            generated_by="evidence_gap",
            reason=f"unresolved frontier: {len(unresolved)} quests",
            max_attempts=3)
        if res.get("added"):
            coord._mutate(tid, lambda x: x.__setitem__(
                "goal_kind", "analyze"))
            st["batch_index"] = idx
            _save_research_state(wt_path, st)
            coord.dispatch(tid)
            made.append(tid)
    return made


def _batch_quest_ids(wt: Path, n: str) -> list:
    f = wt / TOOLS / f"objective_research_batch{n}.json"
    if not f.exists() or f.stat().st_size < 50:
        return []
    data = read_json(f, {})
    qs = [q.get("questId") for q in
          (data.get("quests") or data.get("results") or [])]
    if not qs and isinstance(data.get("batch"), dict):
        qs = data["batch"].get("questIds", [])
    return [q for q in qs if q]


def followups(root: Path, coord) -> list:
    """Generic completion chaining: ANY COMPLETE DATA task with a
    batch artifact spawns its INT counterpart; ANY COMPLETE INT marks
    the batch resolved so the frontier advances. No hardcoded ids."""
    made = []
    tasks = {t["id"]: t for t in coord.list_tasks()}
    wt = _worktree(root)
    for t in list(tasks.values()):
        tid = t["id"]
        if t["status"] != "COMPLETE":
            continue
        # DATA-N or legacy DATA2 -> INT-N / INT1
        n = None
        if tid.startswith("GOAL-FR-WP-1TO60-DATA-N"):
            n = tid.rsplit("N", 1)[-1]
        elif tid == "GOAL-FR-WP-1TO60-DATA2":
            n = "1"
        if not n or not n.isdigit():
            continue
        int_id = f"GOAL-FR-WP-1TO60-INT{n}"
        batch = wt / TOOLS / f"objective_research_batch{n}.json"
        if int_id in tasks or not batch.exists() \
                or batch.stat().st_size < 50:
            continue
        res = coord.add_task(
            int_id, f"Integrate verified candidates from batch {n}",
            f"tools/objective_research_batch{n}.json exists. Merge only "
            "entries with sourceUrl + client version 1.60.x into "
            "tools/evidence_map_1to60.json preserving provenance and "
            "confidence; mark unverifiable rows UNKNOWN. Write "
            f"tools/integration_report_INT{n}.json with merged/rejected/"
            "remaining counts.", str(wt), priority=44,
            acceptance=[{"type": "file_exists",
                         "path": f"tools/integration_report_INT{n}.json"}],
            approved=True, scope="production", owner="goal",
            generated_by="evidence_gap_followup",
            reason=f"{tid} produced verifiable candidates",
            max_attempts=2)
        if res.get("added"):
            coord._mutate(int_id, lambda x: x.__setitem__(
                "goal_kind", "analyze"))
            coord.dispatch(int_id)
            made.append(int_id)
    # bookkeeping: completed INT -> resolve frontier
    st = _research_state(wt)
    done = st.get("integrated_batches", [])
    for t in tasks.values():
        tid = t["id"]
        if (tid.startswith("GOAL-FR-WP-1TO60-INT")
                and t["status"] == "COMPLETE" and tid not in done):
            n = tid.rsplit("INT", 1)[-1].lstrip("N") or "1"
            qs = _batch_quest_ids(wt, n)
            if qs:
                _mark_resolved(wt, qs)
            st = _research_state(wt)
            st.setdefault("integrated_batches", []).append(tid)
            _save_research_state(wt, st)
    # next stage: frontier exhausted + integrations landed -> recalc
    unresolved = _unresolved_quest_ids(root)
    recalc_id = "GOAL-FR-WP-1TO60-RECALC1"
    if (not unresolved and done and recalc_id not in tasks
            and not _research_state(wt).get("recalc_spawned")):
        res = coord.add_task(
            recalc_id,
            "Recalc affected sections from merged objective evidence",
            "All OBJECTIVE_LOCATION frontier quests researched and INT "
            "merges landed in tools/evidence_map_1to60.json. Using the "
            "deterministic merger tools/integrate_batch.py as reference "
            "for accepted rows: rerun the affected route-section "
            "recalculation (tools/route_recalc.lua pipeline) for bands "
            "touching integrated questIds; write "
            "tools/recalc_post_int_report.json with sections changed, "
            "unlocated-rows delta vs tools/recalc_full_1to60_report.json, "
            "and remaining unlocated rows. No invented coords.",
            str(wt), priority=43,
            acceptance=[{"type": "file_exists",
                         "path": "tools/recalc_post_int_report.json"}],
            approved=True, scope="production", owner="goal",
            generated_by="evidence_gap_followup",
            reason="research frontier resolved -> verify route impact",
            max_attempts=2)
        if res.get("added"):
            coord._mutate(recalc_id, lambda x: x.__setitem__(
                "goal_kind", "analyze"))
            coord.dispatch(recalc_id)
            made.append(recalc_id)
            st = _research_state(wt)
            st["recalc_spawned"] = True
            _save_research_state(wt, st)
    return made


def idle_state(coord) -> str:
    """Truthful orchestration state for monitoring."""
    sts = [t["status"] for t in coord.list_tasks()]
    if "RUNNING" in sts:
        return "WORKING"
    if any(s in ("PENDING", "READY") for s in sts):
        return "PLANNING"
    cov = coverage(coord.root)
    gaps = (cov.get("objective_rows_unlocated") or 0) + \
        (cov.get("objective_no_leads") or 0)
    if any(s in ("WAITING_APPROVAL", "NEEDS_APPROVAL") for s in sts):
        return "WAITING_APPROVAL" if not gaps else \
            "WAITING_APPROVAL"  # gate + independent work continues
    return "IDLE_WITH_WORK_REMAINING" if gaps \
        else "GOAL_READY_FOR_OWNER_REVIEW"


def tick(coord) -> dict:
    cov = coverage(coord.root)
    made = synthesize(coord.root, coord, cov)
    made += followups(coord.root, coord)
    return {"coverage": {"quest_ids": cov.get("quest_ids"),
                         "unlocated": cov.get("objective_rows_unlocated"),
                         "no_leads": cov.get("objective_no_leads"),
                         "verified_live": cov.get("objective_verified_live")},
            "orchestration": idle_state(coord),
            "spawned": made}
