# DevinBridge — Verification Report 2026-11-10

## Real end-to-end results (live `devin acp` server, swe-2-high)

| Scenario | Result |
|---|---|
| ACP auth via stored credential (`devin-browser` + `_meta.api_key`) | PASS |
| Session create / prompt / streamed updates / `session/list` / `session/load` | PASS |
| Detached prompt worker survives caller exit | PASS (worker pid recorded, reconcile on death) |
| Chat brain: "Ahoj" → real ACP session → Czech persona reply | PASS ("Dobrý den, pane. JARVIS hlásí připravenost…") |
| Out-of-workspace write attempt → NEEDS_APPROVAL + approval record + ONE ntfy | PASS (T903, request `4cae0edf4428`) |
| CLI approve → `resume_task` → same-session follow-up → agent retries → write succeeds | PASS (`outside_proof.txt` = `OUTSIDE_OK`) |
| Verify on real evidence → COMPLETE | PASS |
| Marked test ntfy to real channel | PASS (dedup key `TEST|bridge-verification-20261110`) |
| Dashboard: unauth→403, bad link→403, admin session→200, no-CSRF→403 | PASS |
| Unit suites | 25/25 PASS (15 bridge + 10 approvals) |

## Key REAL-SERVER findings (important, honest)

1. **Devin's `smart` mode grants scope INTERNALLY.** Its "permission
   request" for e.g. widening write scope is judged inside the agent
   runtime and does NOT reach the ACP host as
   `session/request_permission`. The supported host-side boundary is the
   **`fs/*` and `terminal/*` handler**: out-of-workspace writes and shell
   commands are refused there. The bridge therefore treats a denied
   out-of-scope `fs/write_text_file` as an approval request: record +
   NEEDS_APPROVAL + ntfy. On approval the exact reviewed path is added
   to `granted_paths` and the resumed agent's retry succeeds. Verified
   live (T903).
2. **`swe-2-max` is rejected by ACP** (`Invalid value`). The catalog
   offers `swe-2-high` (used everywhere), `swe-2-flash-medium`,
   `swe-1-7`, `swe-1-6` + fusion variants.
3. **`ask`/`plan` modes are read-only personas**, not
   ask-before-acting styles. `smart` is the unattended ceiling —
   `dangerous`/`bypass` are refused by `session_new`.
4. **Sessions are daemon-managed.** A session with no completed turn is
   not yet loadable from another process; the detached worker creates
   the session itself. `session_load` works for persisted (played-out)
   sessions — follow-up resumes verified live.
5. CLI `auth status` still says "Not logged in"; ACP authenticates via
   `authenticate` + stored `windsurf_api_key` regardless.

## Permission model — CLI/ACP sessions vs Devin Desktop

- **New ACP/CLI sessions**: mode is set per session via
  `session/set_config_option` (`smart` here; `accept-edits`, `plan`,
  `ask` also allowed; `bypass`/`dangerous` refused by the bridge).
  The host handler additionally gates `fs/*`, `terminal/*`, and
  `session/request_permission` through `policy.py` → ALLOW / DENY / ASK.
- **config.json `permissions.allow[]`** (AppData/Roaming/devin): global
  CLI allow list — applies to local agent sessions.
- **Devin Desktop UI** has its own permission prompts for its own
  sessions (the UI is the ACP host there) — bridge approvals never
  affect Desktop sessions.
- `--sandbox` is unsupported on this Windows build.

## Notification flow

ntfy topic `foreverroute01343423Deci` (existing watchdog channel —
reused, no new credentials). Dedup + rate-limit ledger:
`DevinBridge/notifications_ledger.json`. Event types:
approval-required / task-completed / task-failed / daily-summary.

## Approval dashboard

`python -m DevinBridge.approval_server [bind] [port]` — default
127.0.0.1:8765. Auth = single-use link token (`?t=…` minted into the
ntfy URL, 30 min TTL, one-shot) or `dashboard_admin.token` (local).
Sessions: HttpOnly cookie, 12 h, SameSite=Strict. Decisions require the
per-session CSRF token; stale/replayed/expired decisions → 409/403.
Remote phone access: bind the Tailscale IP
(`DEVIN_APPROVAL_BIND=100.x.y.z`) — WireGuard-encrypted, never plain
internet. Audit: `approval_audit.jsonl` + `dashboard_audit.jsonl`.

## Recovery

- Worker died mid-turn → tick marks NEEDS_REVIEW; `cli resume-task ID`
  loads the session and continues (no re-dispatch, no duplicated work).
- Approval expired → request goes EXPIRED (never auto-approved);
  re-attempt creates a fresh request.
- Restart: `coordinator_state.json`, `approval_requests.json`,
  `chat_session.json` all persist; nothing is re-sent on boot.

## ntfy delivery diagnosis (2026-11-10 evening)

- User reported ZERO phone notifications despite server 200s.
- Poll of the topic's message API proves all bridge messages ARE
  stored server-side and retrievable — publication works.
- Root cause is phone-side, not the pipeline: the legacy watcher's last
  real send was 2026-10-24 (~17 days before the report); the ntfy
  Android app was very likely killed by battery optimization or the
  subscription went inactive since.
- Aggravating factor: my earlier sends used Priority 2–4 while the
  legacy watchdog always uses **5** (urgent). Approval + test sends are
  now Priority 5.
- New honest delivery-state machine in `notify.py`:
  CREATED → PUBLISHED → SERVER_CONFIRMED → CLIENT_DELIVERY_UNVERIFIED →
  USER_CONFIRMED (or FAILED). "Delivered to phone" is never claimed
  remotely. `cli notify-status` / `cli ntfy-confirm <dedup_key>`.
- Marked test notification: msg id `IRE6P58A8pLE`, Priority 5, stored
  and retrievable on the topic — **awaiting user phone confirmation**.
- Phone-side checklist if nothing arrives: ntfy app subscribed to the
  topic (check topic list), app battery set to "unrestricted",
  notification permission granted, subscription priority ≥ 3, try
  "Instant delivery" toggle.

## JARVIS 2.1 Companion → Devin primary brain (same evening)

- Root cause of URLError on "Ahoj": `companion_settings.py` hardcoded
  Ollama `http://127.0.0.1:11434/api/chat`; Ollama actually listens on
  **11435**. Fixed via `COMPANION_OLLAMA` env with new default 11435 —
  no other files touched (several feature scripts still hardcode 11434
  but they are not in the chat path).
- New `BrainCore/devin_primary_adapter.py` + hook in
  `companion_agent.Agent.decide()`: when `goal_contract` reports no
  action and no tools are pending, the plain-conversation reply comes
  from the Devin ACP chat session (swe-2-high). `s['brain']` records
  `devin` vs `local-ollama` — a fallback is never disguised.
  `COMPANION_DEVIN_PRIMARY=0` disables.
- Verified live through the Companion's own code path:
  `reply('Ahoj', SYSTEM)` → real Czech persona answer, multi-turn
  memory intact (it remembered the earlier greeting).
- NOTE: the Companion must be **restarted** for the new code to load
  (`.pyw` process caches modules).

## Remaining blockers / honest gaps

- `T81_EXTERNAL_ACTIVE.flag` and the T148 `HOLD_UNCONFIRMED_DISPATCH`
  state are UNTOUCHED — legacy queue still paused; bridge is additive.
- terminal/* is refused for task sessions (read/write-only surface);
  chat sessions allow whitelisted `jarvis_tools` commands only.
- GitHub probe exists (`github_probe.py`) but issue/PR/CI cross-checking
  is not yet wired into verify().
- Dashboard binds HTTP locally; on Tailscale it inherits WireGuard
  encryption but is still cleartext HTTP to that interface — acceptable
  per "authenticated encrypted transport", but do NOT port-forward it.
- Chat approvals wait 120 s then cancel the live request (chat can't
  stall for hours); an approved fingerprint auto-passes on the next
  attempt, or the task flow handles it via NEEDS_APPROVAL.
- ACP client still logs ResourceWarnings for subprocess streams on
  teardown — cosmetic, cleanup TODO.
