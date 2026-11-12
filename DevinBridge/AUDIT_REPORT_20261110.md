# Phase 1 Audit — ForeverRoute/Jarvis Automated Dispatch
**Date:** 2026-11-10 · **Auditor:** Devin (lydian-crepe) · **Scope:** why automated task dispatch stopped, exact holds, safe recovery. Read-only audit — nothing was changed, reset, deleted or re-sent.

## Executive summary

Automated dispatch stopped for **three stacked, independent reasons** — all still in effect:

1. **`T81_EXTERNAL_ACTIVE.flag`** (rewritten 2026-10-24 as a *user pause-for-restart* hold) makes `JarvisDaemon.poll_gate()` return `WAITING_EXTERNAL_T81` before every poll; `JarvisQueue.ps1` also exits early on the same flag. No queue poll → no dispatch.
2. **`pendingDispatch` for `T148_P0_RELEASE_QUALITY_GATE` with `promptSent=false`** latched `HOLD_UNCONFIRMED_DISPATCH` on 2026-10-24. The queue's own fail-closed rule ("never retransmit an uncertain draft") then forbade any further send.
3. **All Jarvis/ForeverRoute scheduled tasks are DISABLED** in Task Scheduler (10 of 12). Only `RealJarvis-Ollama-Vulkan` and `QueueReporting` remain Ready. The daemon's own bootstrap also disables the "ForeverRoute Jarvis" task on start.

Meanwhile **T148 actually ran to completion anyway**: the "unconfirmed" send did reach Devin. Git history shows 11 T148 commits after the hold, ending in the committed terminal marker `3b65d61 "T148 marker: BLOCKED HUMAN-ONLY at tested HEAD b547797"` (2026-10-25 02:42). The queue never consumed the marker — its last observed head is still `34db81a` — so `queue_state.json` incorrectly shows T148 as `PENDING` with a live `pendingDispatch` hold.

## Timeline reconstruction (independent evidence)

| When | Event | Evidence |
|---|---|---|
| 2026-10-24 02:56 | T144 marker `BLOCKED HUMAN-ONLY` held as *unsupported status* | `queue.log` WARN |
| 2026-10-24 08:32 | T144 marked BLOCKED manually; queue attempts T148 dispatch → send unconfirmed → first `HOLD_UNCONFIRMED_DISPATCH` | `queue.log` |
| 2026-10-24 10:58 | Devin's T148 session commits `34db81a` "release-readiness gate" | `git log` |
| 2026-10-24 11:00 | Queue discards stale pendingDispatch (head moved), re-sends T148 → **send again unconfirmed** → hold re-latches at head `34db81a` | `queue.log` ERROR at `JarvisQueue.ps1:751` |
| 2026-10-24 15:40→25 02:42 | **Devin's T148 session keeps working**: `d28e85a`, `fdc7c7e`, `1907ca3`, `e2cb07b`, `ee8af09`, `6272566`, `ac6195b`, `81d670e`, `8f5e6bc`, `b547797`, then marker `3b65d61` | `git log` |
| 2026-10-24 | User writes pause note into `T81_EXTERNAL_ACTIVE.flag`: *"USER PAUSE FOR RESTART … Resume only on explicit user request."* | flag file |
| 2026-10-25 12:57 | RealJarvis side dispatch of a Czech-language proposal to a **cloud** session `d54806ba…` while queue hold still active (recorded honestly with `queue_pendingDispatch: true`) | `DevinCoordinator/dispatches.jsonl` |
| 2026-11-10 15:30 | Daemon still alive, still writing `daemon_gate.json` = `WAITING_EXTERNAL_T81` | `daemon_gate.json` |

**Root-cause class:** the dispatch *verification* channel (UIAutomation "Task ID + Cancel" detection in `Send-QueuedPrompt`) is far less reliable than the dispatch channel itself (SendKeys/paste into the Devin Desktop window). Sends succeed while verification fails → `pendingDispatch.promptSent` stays `false` → permanent fail-closed hold. This same class of incident already hit T136 (2026-10-21) and T143 (2026-10-22), each resolved by manual reconciliation.

## Component status

| Component | State |
|---|---|
| `JarvisDaemon.pyw` | **Running** (mutex alive, writes `daemon_gate.json`), but every cycle short-circuits on the T81 flag |
| `JarvisQueue.ps1` | Idle; would exit early on T81 flag before touching the hold |
| `JarvisWatchdog.ps1` | Idle; only acts on an `ACTIVE` task — `activeTaskId` is empty |
| `watchdog_state.json` | Neutral/empty — no stale tracking |
| `queue_state.json` | 120 COMPLETE · 25 BLOCKED (23 `HUMAN-ONLY` real-client gates) · 5 PENDING (T19, T55, T147, T148, T149) · 1 SKIPPED · `lastResult=HOLD_UNCONFIRMED_DISPATCH` |
| `dispatch_receipts.log` | Last receipt T144 2026-10-23; no T148 receipt (correct — send was never confirmed) |
| Scheduled tasks | 10 Jarvis/ForeverRoute tasks Disabled; none will restart the loop |
| `DevinCoordinator/` (H:) | Proposal pipeline intact; 10 proposals + 1 cloud dispatch recorded |
| Repo `ForeverRoute-db70338` | HEAD `3b65d61`; clean worktree |

## Devin local agent (verified live)

- CLI binary: `…\windsurf\devin\bin\devin.exe` v3000.12.43 — **not on PATH** (must be invoked by full path or added).
- `devin auth status` → **Not logged in** (interactive `devin auth login` was never run). `devin models`/`doctor` confirm.
- `devin acp` (JSON-RPC over stdio) **works**: `initialize` advertises `session/new`, `session/load`, `session/list`, `session/close`, `session/set_config_option`, `authenticate`, MCP, mid-turn prompts.
- ACP auth path proven: `authenticate {methodId:"devin-browser", _meta:{api_key}}` with the account's stored `windsurf_api_key` → real session (`talented-temper`) → prompt → `BRIDGE_OK` + token usage accounting. Local sessions, **no cloud spend**.
- Model catalog via ACP offers `swe-2-high` (display name "SWE-2", **account default**), `swe-2-flash-medium`, `swe-1-7-medium`, `swe-1-6`, and fusion pairs. **`swe-2-max` is rejected** (`Invalid value` on `session/set_config_option`) — it is not selectable through ACP on this account even though past Desktop sessions used it. For ACP dispatch, `swe-2-high` is the correct top SWE-2 tier.
- `sessions.db` (173 sessions) + `summaries/` give durable read-side evidence: session titles, models, activity timestamps, per-message content.
- GitHub: no `gh` CLI; existing automation uses a DPAPI token (`github_token.dpapi`) against `api.github.com` for issue #16 PATCHes — reusable **read-only** for bridge evidence (issues/PRs/check-runs). `DEVIN_API_KEY`/`DEVIN_ORG_ID` exist in Dix01 `.env` (paid cloud path — kept as optional, off by default).

## What exactly blocks recovery

1. `T81_EXTERNAL_ACTIVE.flag` — user-created pause; **must not be removed without the user's word**.
2. `pendingDispatch{T148, 34db81a, promptSent=false}` — stale but fail-closed; next poll at a moved head would discard it and **re-dispatch T148** (dangerous: the result is already committed).
3. T148's terminal marker was never consumed — `queue_state.tasks.T148` must be reconciled to `BLOCKED` (its marker's verdict), not PENDING, or the queue will try to redo finished work.
4. 23 `HUMAN-ONLY` blockers — real WoW client acceptance cannot be automated; they are not dispatch candidates.
5. Dispatch verification channel (UIA) is unreliable — any recovery that keeps UIA-only confirmation will re-latch the same hold.

## Recommended safe recovery (proposed, NOT executed)

1. **Reconcile T148 first** (evidence-based, one-time, manual approval):
   - Record `tasks.T148.status = "BLOCKED"`, `blockedObservedHead = 3b65d61`, note = committed marker verdict.
   - Clear `pendingDispatch`; append a *reconcile* receipt line (task/head + `RECONCILED_NOT_DISPATCHED`) so history shows no resend.
   - Then the queue's next PENDING normal task becomes `T147_P1_REAL_TRAVEL_PATHS` — still gated by the T81 flag.
2. Keep `T81_EXTERNAL_ACTIVE.flag` until the user explicitly clears it (as the flag itself demands).
3. Introduce the ACP bridge (this module) for all **new** dispatch: real session IDs, `stopReason`, usage accounting — replaces SendKeys+UIA confirmation. Legacy UIA path stays untouched for history.
4. Leave all scheduled tasks Disabled; the bridge daemon (when approved) runs under its own lifecycle.

## Files of record (unchanged)

`queue_state.json` · `task_queue.json` · `JarvisQueue.ps1` · `JarvisDaemon.pyw` · `JarvisWatchdog.ps1` · `dispatch_receipts.log` · `watchdog_state.json` · `daemon_gate.json` · `T81_EXTERNAL_ACTIVE.flag` · `H:\RealJarvis\DevinCoordinator\*`
