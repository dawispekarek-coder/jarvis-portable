# DevinBridge — Scoped-Autonomy Readiness (2026-11-10)

Status: **implemented but NOT activated**. Bridge mode: `safe`.
`AUTONOMOUS_ENABLED.flag` absent. No production dispatch has been or
will be performed without explicit human action.

## What was built this round

| Layer | Delivered |
|---|---|
| P0 chat security | Exact-shape terminal allowlist (`python -m DevinBridge.jarvis_tools run <tool> [--json obj]`), fixed `sys.executable` + `MODULE_ROOT` cwd, `relative_to` path ancestry (junction/symlink-proof), caller `cwd/env/args` ignored, denial diagnostics, 23 negative/positive tests |
| P1 production queue | `scope` (production/test, auto-classified; legacy T9xx synthetic tasks migrate to `test` and are never auto-eligible), provenance fields (`owner`, `reason`, `generated_by`, `evidence_refs`, `deadline_epoch`, `max_attempts`, `declared_followups`), `protected_worktrees` config hold (GUI dev repo `ForeverRoute-Devin-1to60-20261110` + legacy `-db70338`), `planner.py` evidence-only proposer → `proposals.json` → human `promote` (approved=False always) |
| P2 verification | `github_issue` / `github_pr` / `github_checks` acceptance types via `GithubProbe` (fail-closed when probe unavailable), worktree-containment for file checks, `command` checks gated behind `shell_checks_approved` + metachar/dangerous-verb sanitiser, preferred `test` runner type (argv-only, allowlisted runners), per-task `max_attempts` |
| P3 mobile actions | ntfy `Click:` + `Actions: view, Open approval` on approval messages — GET-only dashboard open; the decision still requires authenticated CSRF POST; no `http` ntfy actions ever |
| P4 proof | `tests/test_sandbox_chain.py` — 2-task dependent chain (P-A→P-B), planner proposal+promote, crash-recovery no-redispatch, negative PERM→NEEDS_APPROVAL→reject→BLOCKED, protected-worktree refusal, T81 global hold, test-scope exclusion |
| P5 activation gate | `scripts/Start-DevinBridgeDaemon.ps1` (mutex single-instance, daily log rotation, `daemon_health.json`), this checklist |
| Robustness | `read_json` retries through the `os.replace` window (Windows sharing-violation race that silently returned `{}`) |

## Readiness checklist (human must check ALL before autonomy)

- [ ] Bridge daemon runs at login (`schtasks` command in the script header)
- [ ] `cli status` shows `mode: safe`, holds listed, test tasks excluded
- [ ] One production objective defined: write it as a PENDING task with
      `declared_followups` + acceptance checks (see "First real task")
- [ ] Phone notifications confirmed (done 2026-11-10, TEST dedup key)
- [ ] Tailscale dashboard reachable from phone (`DEVIN_APPROVAL_BIND`)
- [ ] Human reviewed `proposals.json` semantics: promote ≠ approve
- [ ] Create `AUTONOMOUS_ENABLED.flag` AND `cli mode autonomous`
- [ ] Verify one tick dispatches exactly one task, waits, verifies,
      proposes next — then pause and review before continued autonomy

## T148 reconciliation decision needed (blocking legacy queue)

`queue_state.pendingDispatch = T148_P0_RELEASE_QUALITY_GATE`
(`promptSent: false`, `lastResult: HOLD_UNCONFIRMED_DISPATCH`).

Evidence shows the dispatch **never reached Devin** — no session, no
receipt in `dispatch_receipts.log`, `promptSent` false. Options:

1. **Void it** — mark pendingDispatch void with evidence note (recommended;
   the gate can be re-scoped as a new bridge task against current HEAD).
2. **Keep the hold** — leave as-is; bridge `worktree_holds` already
   refuses dispatch to the legacy repo while it stands.

Either way the decision and its audit note are the user's.

## First proposed real task (draft — not queued)

```
id:    FR-001
title: Route data completeness audit (1-60)
prompt: Read tools/player_eyes/* and the route data files in this
        worktree. Produce a written audit: which level ranges are
        covered by route data, which are stub/missing, and the exact
        file paths each missing range would occupy. Write the audit to
        docs/route_coverage_audit.md. Do NOT edit route files.
worktree: <new isolated branch worktree of the addon repo>
acceptance: [{type: file_exists, path: docs/route_coverage_audit.md},
             {type: file_contains, path: docs/route_coverage_audit.md,
              pattern: "level range|coverage"}]
scope: production | approved: false | session_mode: smart
```

## Outstanding risks

- `terminal/*` for **task** sessions is still refused wholesale (chat
  allows whitelisted `jarvis_tools` only). Commands the agent needs must
  go through acceptance `test` checks or be added to `jarvis_tools`.
- Approval dashboard is plain HTTP — only ever bound to
  localhost/Tailscale; never port-forward.
- WoW-client QA cannot be verified by bridge checks — `human_gate`
  tasks remain for anything needing an in-game pass.
- ACP `swe-2-max` unavailable; `swe-2-high` is the ceiling.
