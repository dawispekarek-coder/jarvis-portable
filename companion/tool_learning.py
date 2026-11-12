"""RealJarvis V2: learn the tools you ACTUALLY have, with bounded exercises.

This trains operational know-how (verified recipes stored in local SQLite),
NOT neural network weights. This module NEVER accepts model-generated commands.
There is no repo write, OS shell mutation, social posting, or paid AI API call.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Callable
from contextlib import contextmanager

from capability_inventory import BASE, CATALOG, normalize

DEFAULT_DB = BASE / "tool_skills.sqlite"
_LOCK = threading.Lock()
GROUPS = {
    "tts": ("Hlas TTS", "GET /api/tts/status", "voice bridge check", "ready"),
    "stt": ("Mikrofon STT", "prohlížeč / mikrofon", "needs interactive permission", "restricted"),
    "web": ("Internet a web", "Najdi ... /web ...", "read-only HTTPS & search", "safe"),
    "browser": ("Prohlížeč", "Otevři prohlížeč", "command parsing only; no window opened", "ready"),
    "code": ("Git a Lua", "Zkontroluj Git ForeverRoute /code FR_NowNavRepeatsTitle", "read-only real repo", "safe"),
    "memory": ("Místní paměť", "Zapamatuj si: ...", "temporary isolated SQLite fixture", "safe"),
    "files": ("Soubory", "Přečti existující zdroj projektu", "bounded approved checkout read", "safe"),
    "models": ("Lokální model", "Lokálně: ...", "Ollama model listing only; no inference", "ready"),
    "media": ("Média", "Najdi obrázky ...", "image-search intent only; no generation", "ready"),
    "agents": ("Kontrolní agent", "Prověř chyby ForeverRoute v Lua funkci ...", "planner classifier only; no write", "ready"),
    "knowledge": ("Znalostní báze", "Znalosti: planner v4", "real local index lookup", "safe"),
    "system": ("Diagnostika", "/api/stats", "real local system measurement", "safe"),
    "external_ai": ("Externí AI", "Silnější AI: ...", "not called in autonomous learning (cost/privacy)", "restricted"),
}
MODULES = {
    "tts": "capability_inventory.py",
    "stt": "ui_compat.py",
    "web": "public_search.py",
    "browser": "browser_commands.py",
    "code": "project_tools.py",
    "memory": "knowledge_store.py",
    "files": "project_tools.py",
    "models": "local_chat.py",
    "media": "in_app_media.py",
    "agents": "inspect_agent.py",
    "knowledge": "knowledge.py",
    "system": "ui_compat.py",
    "external_ai": "strong_brain_router.py",
}
STATUSES = ("VERIFIED", "READY", "LIMITED", "UNAVAILABLE", "FAILED", "NEEDS_APPROVAL", "UNTESTED")


def training_intent(text: str) -> str | None:
    """Only explicit self-tool-learning commands. Don't steal ordinary requests."""
    if not isinstance(text, str) or not (3 <= len(text) <= 350):
        return None
    q = normalize(text).strip()
    for prefix in ("jarvis ", "jarvisi ", "prosim "):
        if q.startswith(prefix):
            q = q[len(prefix):]
    if q in ("uc se nastroje", "nauc se svoje nastroje", "naucse", "nauc", "learn tools"):
        return "run"
    learn = ("nauc se", "naucit se", "prostuduj si", "osvoj si", "procvic si", "vyzkousej si")
    own_tools = ("co mas k dispozici", "se vsim co mas", "vsechny sve nastroje",
                 "svoje nastroje", "vlastni nastroje", "s tim co umis", "s dostupnymi nastroji",
                 "vsechny schopnosti", "se vsemi nastroji", "s kazdym nastrojem")
    if q.startswith(learn) and any(t in q for t in own_tools):
        return "run"
    if q in ("/uceni", "/learn-status", "stav uceni nastroju") or (
        ("co ses naucil" in q or "jak ses naucil" in q or "co uz umis") and
        any(x in q for x in ("nastroje", "nastroji", "pouzivat", "schopnosti"))
    ):
        return "status"
    return None


def _source_digest(key: str) -> str:
    file = BASE / MODULES[key]
    if not file.is_file():
        return "MISSING"
    return hashlib.sha256(file.read_bytes()).hexdigest()[:16]


def _safe_loopback_json(url: str, timeout=2.5):
    import urllib.request
    if not url.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise ValueError("only loopback probes supported")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as r:
        if r.status != 200:
            raise OSError("unexpected_http_status")
        data = r.read(300000)
    return json.loads(data)


def discover(advertised_tools=()):
    """Use actual local files + externally-advertised V2 tools; never auto-execute unknowns."""
    entries = []
    for key, (name, example, exercise, risk) in GROUPS.items():
        file = BASE / MODULES[key]
        entries.append({
            "id": key, "name": name, "example": example,
            "exercise": exercise, "risk": risk,
            "installed": file.is_file(), "source_hash": _source_digest(key),
        })
    known = set(GROUPS)
    for tool in advertised_tools or ():
        if not isinstance(tool, dict):
            continue
        name = tool.get("name", "")
        if not isinstance(name, str) or len(name) > 80 or not name.replace("_", "").isalnum():
            continue
        key = "advertised:" + name
        if key in known:
            continue
        known.add(key)
        entries.append({
            "id": key, "name": name,
            "example": "Použití je popsané v /api/tools; čeká na schválený bezpečný test.",
            "exercise": "no unreviewed tool invocation", "risk": "unreviewed",
            "installed": True, "source_hash": "api_advertised",
        })
    return entries


def _probe_skill(key: str):
    """Every call here is explicitly allowlisted, scoped, and read-only or disposable."""
    if key == "tts":
        from capability_inventory import voice_backend, tts_bridge_wired
        speech = voice_backend()
        ready = bool(tts_bridge_wired() and speech.get("ready"))
        return (
            "READY" if ready else "LIMITED",
            {"api_configured": bool(tts_bridge_wired()), "backend_reachable": bool(speech.get("reachable")),
             "backend_ready": bool(speech.get("ready"))},
            "Ověřený stav API, nikoliv úspěšné přehrání zvuku.",
        )
    if key == "stt":
        return ("NEEDS_APPROVAL", {"requires_microphone_permission": True},
                "Zachycení mikrofonu vyžaduje výslovnou akci a oprávnění uživatele.")
    if key == "web":
        from internet_access import https_probe
        result = https_probe()
        online = bool(result.get("connected"))
        if not online:
            return "UNAVAILABLE", {"https_ok": False}, "DNS/HTTPS test nedoložil dostupný internet."
        from public_search import search
        hits = search("Python documentation")
        count = len(hits.get("results", []))
        return ("VERIFIED" if count else "LIMITED",
                {"https_ok": True, "public_search_results": count},
                "Použij živé vyhledávání; výsledky a články stále ověřuj podle zdrojů.")
    if key == "browser":
        from browser_commands import intent, DESTINATIONS, execute
        target = intent("Otevři prohlížeč")
        correct = target == "prohlizec" and str(DESTINATIONS.get(target, "")).startswith("https://")
        if correct:
            dry = execute(target, opener=lambda *args, **kwargs: True)
            correct = dry.get("status") == "REQUESTED"
        return ("READY" if correct else "FAILED",
                {"safe_route_parser_passed": correct, "real_browser_opened": False},
                "Ověřen pouze rozbor příkazu a simulace otevření; skutečné GUI nebylo testováno.")
    if key == "code":
        from project_tools import status, search_lua
        before = status()
        found = search_lua("FR_NowNavRepeatsTitle")
        after = status()
        unchanged = all(before.get(k) == after.get(k) for k in ("branch", "commit", "changed_count", "changed_files"))
        matched = bool(found.get("matches") or found.get("results") or found.get("matched"))
        # A read-only lookup may legitimately find no matches in a different repo version.
        return ("VERIFIED" if unchanged else "FAILED",
                {"repo_read": bool(before.get("commit")), "lua_lookup_completed": True,
                 "lua_symbol_found": matched, "repo_state_unchanged": unchanged},
                "Umím jen číst stav Gitu a hledat Lua symboly. Neumím z toho automaticky upravit repozitář.")
    if key == "memory":
        from knowledge_store import NoteStore
        with tempfile.TemporaryDirectory(prefix="jarvis_skill_", dir=str(BASE)) as folder:
            notes = NoteStore(Path(folder) / "fixture.sqlite")
            saved = notes.remember("Tréninkový test paměti JARVIS 2026.")
            found = notes.search("Tréninkový test paměti JARVIS")
            duplicate = notes.remember("Tréninkový test paměti JARVIS 2026.")
            valid = (bool(found) and found[0]["id"] == saved["id"] and duplicate["duplicate"])
        return ("VERIFIED" if valid else "FAILED",
                {"write_read_duplicate_fixture_passed": valid, "real_user_notes_modified": False},
                "Paměť se testuje jen v dočasné izolované databázi, bez zásahu do tvých poznámek.")
    if key == "files":
        from project_tools import REPO
        candidate = next((REPO / x for x in ("README.md", "ForeverRoute.toc") if (REPO / x).is_file()), None)
        if candidate is None:
            return "UNAVAILABLE", {"approved_project_file_found": False}, "Projektový soubor nenalezen."
        with candidate.open("rb") as f:
            probe = f.read(1024)
        good = bool(probe) and candidate.stat().st_size >= len(probe)
        return ("VERIFIED" if good else "FAILED",
                {"approved_project_file_read": good, "sample_bytes": len(probe), "write_attempted": False},
                "Přečetl jsem pouze existující schválený soubor; nemám tím právo libovolně zapisovat.")
    if key == "models":
        from local_chat import MODEL
        data = _safe_loopback_json("http://127.0.0.1:11434/api/tags", timeout=3)
        models = data.get("models", [])
        installed = isinstance(models, list) and any(
            isinstance(x, dict) and x.get("name") == MODEL for x in models)
        return ("READY" if installed else "UNAVAILABLE",
                {"configured_model_installed": bool(installed), "inference_performed": False},
                "Ověřil jsem seznam lokálních modelů. Schopnost odpovídat vyžaduje samostatný test.")
    if key == "media":
        from in_app_media import image_query
        parsed = image_query("Najdi obrázky koček")
        return ("READY" if parsed is not None else "LIMITED",
                {"image_search_intent_ready": parsed is not None,
                 "generated_image": False, "generated_video": False},
                "Ověřené rozpoznání obrazového hledání; ne generování obrázků ani videa.")
    if key == "agents":
        from inspect_agent import extract_goal, plan
        goal = "Prověř chyby ForeverRoute v Lua funkci FR_NowNavRepeatsTitle"
        valid = bool(extract_goal(goal))
        steps = plan({"goal": goal}) if valid else {}
        safe = steps.get("intent") == "review_only" and "git_status" in steps.get("steps", [])
        return ("READY" if safe else "FAILED",
                {"safe_planner_ready": safe, "agent_executed": False, "writes_enabled": False},
                "Ověřen pouze omezený plánovač; sám neprogramuje ani nepublikuje.")
    if key == "knowledge":
        import knowledge
        stats = knowledge.status()
        docs = knowledge.search("ForeverRoute", limit=2)
        valid = isinstance(stats, dict) and isinstance(docs, list) and len(docs) > 0
        return ("VERIFIED" if valid else "LIMITED",
                {"knowledge_status_read": isinstance(stats, dict), "source_results": len(docs)},
                "Citované místní úryvky jsou podklady, ne automaticky potvrzená fakta.")
    if key == "system":
        import platform
        import psutil
        info = psutil.virtual_memory()
        valid = info.total > 0 and bool(platform.system())
        return ("VERIFIED" if valid else "FAILED",
                {"system_metrics_read": valid}, "Bezpečná diagnostika bez změny systému.")
    if key == "external_ai":
        return ("NEEDS_APPROVAL", {"external_request_sent": False},
                "Externí model nebyl automaticky volán; náklady a soukromí vyžadují výslovný pokyn.")
    raise ValueError("unknown_tool_no_execution")


@contextmanager
def _connect(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(db_path), timeout=8)
    db.execute("PRAGMA busy_timeout=8000")
    db.execute("""CREATE TABLE IF NOT EXISTS runs(
        id TEXT PRIMARY KEY, started REAL NOT NULL, finished REAL,
        status TEXT NOT NULL, discovered INTEGER NOT NULL,
        checked INTEGER NOT NULL DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS skills(
        id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL,
        example TEXT NOT NULL, lesson TEXT NOT NULL, evidence TEXT NOT NULL,
        source_hash TEXT NOT NULL, updated REAL NOT NULL, run_id TEXT NOT NULL)""")
    db.commit()
    try:
        yield db
        db.commit()
    finally:
        db.close()


def train_all(advertised_tools=(), db_path=None, report: Callable[[dict], None] | None = None,
              probe_overrides=None, cancel_event=None):
    """Triggered ONLY by explicit user intent. Never execute arbitrary tool names."""
    dest = Path(db_path) if db_path is not None else DEFAULT_DB
    if not _LOCK.acquire(blocking=False):
        return {"status": "BUSY", "reason": "training_already_running"}
    lock_path = dest.with_suffix(".running.lock")
    lock_created = False
    try:
        if lock_path.exists():
            import psutil
            old=lock_path.read_text(encoding='ascii')
            try:
                meta=json.loads(old) if old.lstrip().startswith('{') else {'pid':int(old)}
                process=psutil.Process(int(meta['pid']))
                alive=process.is_running() and ('created' not in meta or abs(process.create_time()-meta['created'])<.01)
            except psutil.NoSuchProcess:alive=False
            except (ValueError,KeyError,TypeError):alive=bool(old.strip()) or time.time()-lock_path.stat().st_mtime<30
            except psutil.AccessDenied:alive=True
            if not alive and lock_path.exists() and lock_path.read_text(encoding='ascii')==old:
                lock_path.unlink()
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="ascii") as f:
                import psutil
                f.write(json.dumps({'pid':os.getpid(),'created':psutil.Process().create_time()}))
            lock_created = True
        except FileExistsError:
            return {"status": "BUSY", "reason": "other_process_training_or_orphaned_lock"}
        items = discover(advertised_tools)
        run_id = str(uuid.uuid4())
        with _connect(dest) as db:
            db.execute("INSERT INTO runs(id,started,status,discovered) VALUES (?,?,?,?)",
                       (run_id, time.time(), "RUNNING", len(items)))
            db.commit()
            results = []
            for index, item in enumerate(items, 1):
                if cancel_event is not None and cancel_event.is_set():
                    db.execute("UPDATE runs SET finished=?,status=? WHERE id=?",
                               (time.time(), "INTERRUPTED", run_id))
                    db.commit()
                    return {"status": "INTERRUPTED", "checked": len(results), "discovered": len(items)}
                key = item["id"]
                if report:
                    try:
                        report({"index": index, "total": len(items), "name": item["name"], "phase": "testing"})
                    except Exception:
                        pass
                if not item["installed"]:
                    status, proof, lesson = "UNAVAILABLE", {"source_missing": True}, "Modul není nainstalovaný."
                elif key.startswith("advertised:"):
                    status, proof, lesson = (
                        "UNTESTED", {"registered_in_api_tools": True},
                        "Nástroj byl nalezen v živém seznamu; vyžaduje samostatnou schválenou zkoušku.")
                else:
                    try:
                        fn = (probe_overrides or {}).get(key, None)
                        status, proof, lesson = fn() if fn is not None else _probe_skill(key)
                        if status not in STATUSES or not isinstance(proof, dict):
                            raise ValueError("invalid_probe_outcome")
                    except Exception as exc:
                        status, proof, lesson = (
                            "FAILED", {"error_type": type(exc).__name__},
                            "Bezpečný test selhal; schopnost nelze prohlásit za funkční.")
                # Evidence values are fixed, explicitly generated by safe functions; no secrets, paths, prompts or URLs.
                encoded = json.dumps(proof, ensure_ascii=False, sort_keys=True)[:900]
                db.execute("""INSERT INTO skills(id,name,status,example,lesson,evidence,source_hash,updated,run_id)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET name=excluded.name,status=excluded.status,
                    example=excluded.example,lesson=excluded.lesson,evidence=excluded.evidence,
                    source_hash=excluded.source_hash,updated=excluded.updated,run_id=excluded.run_id""",
                    (key, item["name"], status, item["example"], lesson, encoded,
                     item["source_hash"], time.time(), run_id))
                db.execute("UPDATE runs SET checked=? WHERE id=?", (index, run_id))
                db.commit()
                results.append({"id": key, "status": status, "name": item["name"]})
            db.execute("UPDATE runs SET finished=?,status=? WHERE id=?",
                       (time.time(), "COMPLETED", run_id))
            db.commit()
        return {"status": "COMPLETED", "run_id": run_id, "checked": len(results),
                "counts": {s: sum(r["status"] == s for r in results) for s in STATUSES},
                "results": results}
    finally:
        if lock_created:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
        _LOCK.release()


def current(db_path=None):
    dest = Path(db_path) if db_path is not None else DEFAULT_DB
    if not dest.is_file():
        return {"status": "NEVER_RUN", "skills": [], "message": "Žádný trénink nástrojů ještě neproběhl."}
    with _connect(dest) as db:
        run = db.execute("SELECT id,started,finished,status,discovered,checked FROM runs ORDER BY started DESC LIMIT 1").fetchone()
        skills = db.execute("SELECT id,name,status,example,lesson,evidence,source_hash,updated FROM skills ORDER BY id").fetchall()
    outputs = []
    for k, name, status, example, lesson, evidence, source_hash, updated in skills:
        stale = k in MODULES and source_hash != _source_digest(k)
        outputs.append({"id": k, "name": name,
                        "status": "STALE" if stale else status,
                        "last_test_result": status, "source_changed_since_test": bool(stale),
                        "example": example, "lesson": lesson,
                        "evidence": json.loads(evidence), "tested_at": updated})
    return {"status": run[3] if run else "NEVER_RUN",
            "last_run_id": run[0] if run else None,
            "discovered": run[4] if run else 0,
            "checked": run[5] if run else 0,
            "skills": outputs}


def format_report(result):
    if result.get("status") == "BUSY":
        return "Výuka nástrojů už běží nebo zůstal zámek po přerušení. Nezačínám druhý běh; zkontroluj stav."
    if result.get("status") != "COMPLETED":
        return "Výuka nebyla dokončena ani nezávisle ověřena."
    counts = result["counts"]
    lines = ["Prošel jsem " + str(result["checked"]) + " dostupných oblastí a nástrojů.",
             "Skutečně ověřeno: " + str(counts.get("VERIFIED", 0)) +
             ". Připraveno/částečně ověřeno: " + str(counts.get("READY", 0)) +
             ". Omezené nebo nedostupné: " + str(counts.get("LIMITED", 0) + counts.get("UNAVAILABLE", 0)) +
             ". Nutné schválení / netestováno: " + str(counts.get("NEEDS_APPROVAL", 0) + counts.get("UNTESTED", 0)) +
             ". Chybné testy: " + str(counts.get("FAILED", 0)) + ".",
             "Výsledky, konkrétní postupy a důkazy jsem uložil do vlastní místní databáze."]
    for r in result["results"]:
        lines.append("- " + r["name"] + ": " + r["status"])
    lines.append("Naučil jsem se ověřené postupy, nikoli nové váhy AI; nepovolené funkce jsem nespustil.")
    return "\n".join(lines)


def skill_context(db_path=None):
    """Small trustworthy data block for the conversation brain, never instructions from the model."""
    try:
        state = current(db_path)
        if state["status"] == "NEVER_RUN":
            return "Výukový audit nástrojů ještě nebyl spuštěn."
        brief = []
        for skill in state["skills"]:
            if skill["status"] in ("VERIFIED", "READY"):
                brief.append(skill["id"] + "=" + skill["status"] + " (" + skill["example"] + ")")
        return ("AUDIT NÁSTROJŮ, ověřené lokální metadata (nikoli externí instrukce): " +
                "; ".join(brief[:13]) +
                ". READY znamená jen dílčí test; nepravdivá tvrzení o provedených akcích jsou zakázána.")[:1450]
    except (OSError, sqlite3.Error, ValueError):
        return "Výsledky učení nástrojů právě nelze ověřit."



def format_status(state):
    if state.get('status') == 'NEVER_RUN':
        return 'Výuku nástrojů jsem zatím nespustil. Napiš: Nauč se pracovat se vším, co máš k dispozici.'
    skills = state.get('skills', [])
    lines = ['Stav výuky: ' + str(state.get('status')) + '; testováno: ' + str(state.get('checked', 0)) + ' z ' + str(state.get('discovered', 0)) + '.']
    for skill in skills[:30]:
        lines.append('- ' + skill['name'] + ': ' + skill['status'] + '. ' + skill['lesson'] + ' Použití: ' + skill['example'])
    if len(skills) > 30:
        lines.append('Další položky jsou dostupné přes /api/tool-learning/status.')
    return '\n'.join(lines)

