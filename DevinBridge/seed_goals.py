"""Owner-directed seed of the two durable ForeverRoute goals.
Idempotent — add_goal() no-ops when the id already exists.
Provenance: owner directive 2026-11-11 (session lydian-crepe)."""
from __future__ import annotations

WT = (r"C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\autonomy_scope"
      r"\workspaces\foreverroute-route-audit")

GOAL_WP = dict(
    goal_id="GOAL-FR-WP-1TO60",
    title="Waypoint coverage 1-60: vsechna pasma/profily "
          "(728 sekc, 56 profilu)",
    worktree=WT,
    contract=[
        {"type": "file_exists",
         "path": "tools/recalc_full_1to60_report.json"},
        {"type": "file_contains",
         "path": "tools/recalc_full_1to60_report.json",
         "pattern": '"ungrounded_rows": 0'}],
    stages=[
        {"title": "Inventar licencovanych zdroju + verze klienta",
         "kind": "analyze",
         "prompt": ("Vytvor docs/autonomy/source_inventory.md: seznam "
                    "licencovanych zdroju quest/waypoint dat (jmeno, "
                    "licence, verze, povolene pouziti), cilova verze "
                    "klienta, a ktere existujici audit artefakty lze "
                    "znovu pouzit. Nevymyslej data."),
         "acceptance": [{"type": "file_exists",
                         "path": "docs/autonomy/source_inventory.md"}]},
        {"title": "Evidence mapa quest/lokaci per pasmo a profil",
         "kind": "analyze",
         "prompt": ("Vytvor tools/evidence_map_1to60.json: pro kazdou "
                    "z 13 leveling band a 56 profilu kolik "
                    "quest/objective/NPC/turnin bodu ma overitelny "
                    "zdrojovy dukaz (zdroj+id) a kolik chybi. Jen "
                    "dukazy, zadne odhady souradnic."),
         "acceptance": [{"type": "file_exists",
                         "path": "tools/evidence_map_1to60.json"}]},
        {"title": "Deterministicka integrace waypointu z dukazu",
         "kind": "repair-small",
         "prompt": ("Dopln waypointy POUZE pro quest/objective s "
                    "overitelnym dukazem v tools/evidence_map_1to60."
                    "json. Zapis do generovaneho souboru — nikdy "
                    "DB/forever/quest.lua ani xp.lua. Radius +-3 yardy "
                    "je prichodovy radius, NE presnost zdroje."),
         "acceptance": [{"type": "file_exists",
                         "path": "tools/waypoints_1to60.json"}]},
        {"title": "Plna 728-sekcni / 56-profilova rekalkulace",
         "kind": "repair-small",
         "prompt": ("Spust plnou rekalkulaci vsech 728 sekci a 56 "
                    "profilu; zapis tools/recalc_full_1to60_report.json "
                    "s metrikami prereq violations, ordering "
                    "violations, gate inversions, ungrounded_rows."),
         "acceptance": [{"type": "file_exists",
                         "path": "tools/recalc_full_1to60_report.json"}]},
        {"title": "Automaticke kontroly pokryti", "kind": "test-add",
         "prompt": ("Pridaj test assertujici: 0 prereq violations, 0 "
                    "unresolved ordering violations, 0 gate "
                    "inversions, ungrounded_rows == 0 v "
                    "tools/recalc_full_1to60_report.json."),
         "acceptance": [{"type": "test", "runner": "unittest",
                         "args": ["discover", "-s", "tests",
                                  "-p", "test_coverage_*.py"]}]},
        {"title": "In-game lidska validace", "kind": "analyze",
         "human_gate": True,
         "prompt": ("Clovek ve WoW klientu overi reprezentativni "
                    "vzorek tras."),
         "needs_evidence": "SavedVariables snapshot + in-game QA"},
        {"title": "Release gate", "kind": "analyze", "human_gate": True,
         "prompt": "Release vzdy na vlastnika po splnene smlouve.",
         "needs_evidence": "vlastnikuv release souhlas"}],
    provenance="owner directive 2026-11-11",
    evidence_request="in-game QA snapshot (SavedVariables)")

GOAL_HYJAL = dict(
    goal_id="GOAL-FR-HYJAL",
    title="Mount Hyjal: zjistitelne questy s overenymi NPC/objective/"
          "souradnicemi + travel graf",
    worktree=WT,
    contract=[
        {"type": "file_exists", "path": "tools/hyjal_evidence.json"},
        {"type": "file_contains", "path": "tools/hyjal_evidence.json",
         "pattern": '"quests_fully_sourced"'}],
    stages=[
        {"title": "Licencovane zdroje pro Hyjal quest data",
         "kind": "analyze",
         "prompt": ("Vytvor docs/autonomy/hyjal_sources.md: "
                    "licencovane zdroje pro Mount Hyjal 55-60 "
                    "Alliance questy, licence, povolene pouziti."),
         "acceptance": [{"type": "file_exists",
                         "path": "docs/autonomy/hyjal_sources.md"}]},
        {"title": "Hyjal quest/NPC/objective/spawn/turnin evidence",
         "kind": "analyze",
         "prompt": ("Vytvor tools/hyjal_evidence.json: pro kazdy "
                    "zjistitelny Hyjal quest — quest id, NPC id+jmeno, "
                    "objectives, spawn/turn-in souradnice SE ZDROJEM, "
                    "taxi durations, walkable edges. Jen overitelne "
                    "dukazy, zadne vymyslene souradnice."),
         "acceptance": [{"type": "file_exists",
                         "path": "tools/hyjal_evidence.json"}]},
        {"title": "Hyjal waypointy + travel edges integrace",
         "kind": "repair-small",
         "prompt": ("Integruj overene Hyjal waypointy a travel edges "
                    "podle tools/hyjal_evidence.json do generovaneho "
                    "vystupu. Nikdy DB/forever/quest.lua ani xp.lua."),
         "acceptance": [{"type": "file_exists",
                         "path": "tools/hyjal_sections.json"}]},
        {"title": "Hyjal supplement sekce + kontroly",
         "kind": "test-add",
         "prompt": ("Generuj supplement sekce pro questy s kompletni "
                    "evidenci a pridaj automatizovane kontroly "
                    "(NPC/objective/turnin pritomne, hrany spojite)."),
         "acceptance": [{"type": "test", "runner": "unittest",
                         "args": ["discover", "-s", "tests",
                                  "-p", "test_hyjal_*.py"]}]},
        {"title": "In-game lidska validace Hyjal", "kind": "analyze",
         "human_gate": True, "prompt": "In-game overeni Hyjal tras.",
         "needs_evidence": "in-game QA Hyjal"},
        {"title": "Release gate Hyjal", "kind": "analyze",
         "human_gate": True,
         "prompt": "Release jen po dokazane smlouve + souhlas.",
         "needs_evidence": "vlastnikuv release souhlas"}],
    provenance="owner directive 2026-11-11",
    evidence_request="in-game QA Hyjal")


def seed(root):
    from . import goals
    out = []
    for g in (GOAL_WP, GOAL_HYJAL):
        out.append(goals.add_goal(root, **g))
    return out


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from DevinBridge.daemon import make_coordinator, load_config
    from DevinBridge import goals
    c = make_coordinator(load_config())
    for r in seed(c.root):
        print(r.get("added"), "|", r["goal"]["id"])
    print(goals.tick(c))
