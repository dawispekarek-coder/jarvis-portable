# jarvis-portable

Portable autonomous Jarvis: DevinBridge autonomy engine + companion chat UI.
Clone this repo on a second PC, run `setup.ps1`, point it at any project —
Jarvis plans, dispatches to Devin (SWE-2 flash medium), verifies results,
recovers from failures and keeps working until the goal is proven.

## What's inside

| Path | What |
|---|---|
| `DevinBridge/` | Autonomy engine: coordinator, daemon, watchdog, AI planner, recovery pipeline, approvals, WoW QA tools, learner |
| `DevinBridge/autonomy_scope/examples/` | Reference program/authorization files from the ForeverRoute deployment |
| `companion/` | RealJarvis V2 companion (chat UI, memory, tools) — source only, venv is built by setup |
| `init_project.py` | Point Jarvis at a project → generates program scope + goal authorization + enables autonomy |
| `setup.ps1` | Bootstrap: config paths, venv, deps, autostart registration |

## Second PC quick start

Prereqs: Python 3.10+, the Devin app (CLI) installed, git.

```powershell
git clone https://github.com/dawispekarek-coder/jarvis-portable.git
cd jarvis-portable
powershell -ExecutionPolicy Bypass -File setup.ps1
devin login                                   # one-time Devin auth
python init_project.py --repo "C:\path\to\project" --goal "release-ready v1.0"
python -m DevinBridge.daemon                  # or just log off/on — autostart is registered
```

The daemon then runs: plan → propose → dispatch → verify → repair → repeat,
single-worker paced, inside the scope `init_project.py` granted. No pushes,
no publishes — code stays local on the project worktree.

## Model

`DevinBridge/bridge_config.json` → `"model": "swe-2-flash-medium"`.
Change it there any time; the daemon picks it up on restart.

## Safety defaults (unchanged)

- `allow_push` / `allow_publish` / `allow_install`: false
- 12 dispatches/hour, 6 failures/24h circuit breaker, 1 worker
- Approval delegation still requires the safety policy — unsafe actions are rejected, not approved
- WoW QA tooling ships disabled until a program grants it

## Notes

- Your learned-lessons state ships in `DevinBridge/learner_state.json` — Jarvis keeps improving across projects.
- Companion memory (`companion/companion.sqlite`) ships as-is; delete it if you want a fresh personality on the new machine.
- Ollama/local models are NOT included — companion falls back to Devin ACP until you install Ollama + pull models.
