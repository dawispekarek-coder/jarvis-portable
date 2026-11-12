"""Convert independently measured Lua route defects into scoped code tasks.

No source mutation, speculation, fake waypoint coordinates, or docs-only tasks.
Only positive quantified defects produce work. Dedup fingerprints are stable
for a given defect signature. Existing owner worktree grant remains required.
"""
from __future__ import annotations
import json
from pathlib import Path


def discover_route_metrics(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("tool") != "route_recalc" or
            data.get("schemaVersion") != 1 or
            not isinstance(data.get("totals"), dict)):
        return []
    sections = data.get("sections")
    if not isinstance(sections, int) or sections < 1:
        return []
    totals = data["totals"]
    issues = []

    def add(key, count, fp, title, repro, output, test, priority):
        if not isinstance(count, int) or count <= 0:
            return
        issues.append({
            "issue_id": "ISS-" + fp[:16], "fingerprint": fp,
            "kind": "test-add", "priority": priority, "confidence": "high",
            "source_ref": f"{path}:{key}={count}",
            "title": title, "repro": repro,
            "allowed_paths": ["tools/", "tests/", "ForeverRoute_PlannerV4.lua"],
            "test_cmd": f"python -m unittest discover -s tests -p {test}",
            "acceptance": [
                {"type":"file_exists","path":output},
                {"type":"file_exists","path":f"tests/{test}"},
                {"type":"test","runner":"unittest",
                 "args":["discover","-s","tests","-p",test],
                 "expect_exit":0}],
            "detail_rows":count,
        })
    gates = totals.get("gateInversions")
    examples = data.get("gateInversionDetail") or []
    if isinstance(gates, int) and len(examples) == gates:
        add("gateInversions", gates,
            f"gate-inversions-real-lua-{gates}-20261111",
            f"CODE: verify and correct {gates} unsafe pickup level gates",
            (f"Real Lua 5.1 route compiler measured {gates} underlevel "
             f"pickups in {sections} sections. Examples: "
             + "; ".join(str(v)[:145] for v in examples[:3])
             + ". Create runnable tools/verify_route_gate_safety.py, "
             "tests/test_route_gate_safety.py, prove safe V4 minLevel "
             "deferral on real evidence; do not change expected metrics "
             "or fabricate game data."),
            "tools/verify_route_gate_safety.py",
            "test_route_gate_safety.py", 13)

    auth = totals.get("authoredViolations") or {}
    authored, final = auth.get("authored"), auth.get("final")
    if isinstance(authored,int) and isinstance(final,int):
        extra = max(0,final-authored)
        add("authoredViolationDelta",extra,
            f"authored-prereq-regression-real-lua-{extra}-20261111",
            f"CODE: analyze {extra} introduced authored-prereq conflicts",
            (f"Across {sections} real Lua sections, authored ordering violations "
             f"increase {authored}->{final}. Build executable analyzer "
             "tools/route_authored_prereq_audit.py plus tests/" 
             "test_authored_prereq_audit.py; classify conflicts by quest "
             "and section from real catalog/wire. Do not erase the registry "
             "authority or invent prerequisites. Write code, not docs only."),
            "tools/route_authored_prereq_audit.py",
            "test_authored_prereq_audit.py",18)
    ungrounded = totals.get("ungroundedRows")
    if isinstance(ungrounded,int):
        add("ungroundedRows",ungrounded,
            f"ungrounded-route-evidence-{ungrounded}-20261111",
            f"CODE: implement reproducible waypoint coverage audit ({ungrounded} missing)",
            (f"Real Lua 5.1 route compiler over {sections} sections reports "
             f"{ungrounded} ungrounded route rows; the existing "
             "tools/build_waypoint_candidates.py uses limited candidate "
             "evidence. Build a RUNNABLE tools/route_waypoint_coverage.py "
             "and tests/test_route_waypoint_coverage.py. Quantify source "
             "coverage per section and quest with observed provenance. "
             "Never fabricate, interpolate, or grant coordinates from "
             "unknown evidence; preserve user-confirmed +/-3 yard rule "
             "only for measured positions, and report gaps explicitly. "
             "No live WoW/SavedVariables/production DB edits."),
            "tools/route_waypoint_coverage.py",
            "test_route_waypoint_coverage.py",26)
    return issues
