"""Notifications through the EXISTING channel.

The legacy watchdog/watcher already alert the user via ntfy.sh topic
``foreverroute01343423Deci`` (JarvisWatchdog.ps1, NtfyWatcher.pyw).
The bridge reuses the same topic — no new channel, no new credentials.

HONEST DELIVERY STATES — a 200 response proves the SERVER accepted the
message, not that the phone displayed it:

    CREATED                      — claimed a send slot
    PUBLISHED                    — HTTP accepted, message id recorded
    SERVER_CONFIRMED             — message retrievable via topic poll
    CLIENT_DELIVERY_UNVERIFIED   — phone receipt unknown (the ceiling
                                   of what we can prove remotely)
    USER_CONFIRMED               — user said they saw it (cli
                                   ntfy-confirm / dashboard button)
    FAILED                       — transport/server rejected after
                                   bounded retries

Dedup + rate limiting live in ``notifications_ledger.json``.
Failures are logged, never fatal. DEVIN_BRIDGE_DISABLE_NTFY=1 for tests;
DEVIN_BRIDGE_NTFY_BASE to point at a mock server.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

from .bridge_store import atomic_write_json, file_lock, read_json, utcnow

DEFAULT_TOPIC = "foreverroute01343423Deci"

DEDUP_TTL_S = 6 * 3600
MAX_PER_HOUR = 12
RETRY_DELAYS = (3.0, 10.0)          # bounded backoff on transient fails
CONFIRM_POLL_S = 2.0
CONFIRM_TIMEOUT_S = 15.0


def _base() -> str:
    return os.environ.get("DEVIN_BRIDGE_NTFY_BASE", "https://ntfy.sh")


class Notifier:
    def __init__(self, root: str | Path,
                 topic: str = DEFAULT_TOPIC):
        self.root = Path(root)
        self.topic = topic
        self.ledger = self.root / "notifications_ledger.json"
        self.lock = self.root / ".notify.lock"

    # ----------------------------------------------------- ledger/state
    def _set_state(self, dedup_key: str, state: str, **extra) -> None:
        with file_lock(self.lock):
            st = read_json(self.ledger, {})
            ent = st.setdefault("sent", {}).setdefault(
                dedup_key, {"at": time.time()})
            ent["state"] = state
            ent["state_ts"] = utcnow()
            ent.update(extra)
            atomic_write_json(self.ledger, st)

    def states(self) -> list[dict]:
        st = read_json(self.ledger, {})
        return [{"dedup_key": k, **v} for k, v in
                st.get("sent", {}).items()]

    def mark_user_confirmed(self, dedup_key: str) -> dict:
        ent = {e["dedup_key"]: e for e in self.states()}.get(dedup_key)
        if not ent:
            return {"ok": False, "error": "unknown dedup_key"}
        self._set_state(dedup_key, "USER_CONFIRMED")
        return {"ok": True, "dedup_key": dedup_key}

    # ---------------------------------------------------------- plumbing
    def _post(self, title: str, body: str, priority: str,
              tags: str, extra_headers: dict | None = None) -> dict:
        """One publish attempt. Returns {ok, msg_id, http, error}."""
        headers = {"Title": title.encode("ascii", "replace").decode(),
                   "Priority": priority, "Tags": tags}
        headers.update(extra_headers or {})
        try:
            req = urllib.request.Request(
                f"{_base()}/{self.topic}",
                data=body.encode("utf-8"),
                headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as r:
                data = {}
                try:
                    data = json.loads(r.read().decode("utf-8", "replace"))
                except (ValueError, UnicodeDecodeError):
                    pass
                return {"ok": 200 <= r.status < 300, "http": r.status,
                        "msg_id": data.get("id", ""),
                        "expires": data.get("expires")}
        except urllib.error.HTTPError as e:
            return {"ok": False, "http": e.code,
                    "error": f"http {e.code}: {e.reason}"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    def _publish_with_retry(self, title, body, priority, tags,
                            extra_headers) -> dict:
        last = {}
        for attempt in range(len(RETRY_DELAYS) + 1):
            last = self._post(title, body, priority, tags, extra_headers)
            if last.get("ok"):
                return last
            # 4xx (except 429) is not transient — don't retry
            http = last.get("http")
            if http and 400 <= http < 500 and http != 429:
                return last
            if attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
        return last

    def confirm_on_server(self, msg_id: str, since_epoch: float,
                          timeout: float = CONFIRM_TIMEOUT_S) -> bool:
        """Poll the topic's public message API until the message id is
        retrievable — proves server-side persistence (what the phone
        app would also fetch)."""
        deadline = time.time() + timeout
        since = int(since_epoch) - 30
        while time.time() < deadline:
            try:
                req = urllib.request.Request(
                    f"{_base()}/{self.topic}/json?poll=1&since={since}")
                with urllib.request.urlopen(req, timeout=8) as r:
                    for line in r.read().decode("utf-8", "replace"
                                                ).splitlines():
                        try:
                            m = json.loads(line)
                        except ValueError:
                            continue
                        if m.get("id") == msg_id:
                            return True
            except Exception:
                pass
            time.sleep(CONFIRM_POLL_S)
        return False

    # -------------------------------------------------------- send path
    def _claim(self, dedup_key: str, urgent: bool) -> str:
        now = time.time()
        with file_lock(self.lock):
            st = read_json(self.ledger, {})
            sent = st.setdefault("sent", {})
            sent = {k: v for k, v in sent.items()
                    if v.get("at", 0) > now - DEDUP_TTL_S * 4}
            st["sent"] = sent
            if dedup_key in sent and now - sent[dedup_key]["at"] < DEDUP_TTL_S:
                atomic_write_json(self.ledger, st)
                return "deduplicated"
            hour_ago = now - 3600
            recent = [v for v in sent.values() if v.get("at", 0) > hour_ago]
            if not urgent and len(recent) >= MAX_PER_HOUR:
                atomic_write_json(self.ledger, st)
                return "rate_limited"
            sent[dedup_key] = {"at": now, "state": "CREATED"}
            atomic_write_json(self.ledger, st)
        return "claimed"

    def send(self, dedup_key: str, title: str, body: str,
             priority: str = "default", tags: str = "jarvis",
             urgent: bool = False,
             extra_headers: dict | None = None) -> dict:
        """Publish once per dedup_key per TTL. The outcome string is an
        honest delivery state — 'sent' is never claimed."""
        claim = self._claim(dedup_key, urgent)
        if claim != "claimed":
            return {"sent": False, "outcome": claim}
        if os.environ.get("DEVIN_BRIDGE_DISABLE_NTFY") == "1":
            self._set_state(dedup_key, "FAILED", error="disabled by env")
            return {"sent": False, "outcome": "disabled",
                    "state": "FAILED"}
        t0 = time.time()
        pub = self._publish_with_retry(title, body, priority, tags,
                                       extra_headers)
        if not pub.get("ok"):
            err = pub.get("error") or f"http {pub.get('http')}"
            self._set_state(dedup_key, "FAILED", error=err)
            return {"sent": False, "outcome": "publish_failed",
                    "error": err, "state": "FAILED"}
        self._set_state(dedup_key, "PUBLISHED",
                        msg_id=pub.get("msg_id", ""), http=pub.get("http"))
        # Server-side persistence check — the same API the phone app polls
        if pub.get("msg_id") and self.confirm_on_server(
                pub["msg_id"], t0):
            self._set_state(dedup_key, "SERVER_CONFIRMED")
        self._set_state(dedup_key, "CLIENT_DELIVERY_UNVERIFIED")
        return {"sent": True, "outcome": "CLIENT_DELIVERY_UNVERIFIED",
                "msg_id": pub.get("msg_id", ""),
                "state": "CLIENT_DELIVERY_UNVERIFIED"}

    def _send_raw(self, title: str, body: str, priority: str,
                  tags: str, extra_headers: dict | None = None) -> bool:
        if os.environ.get("DEVIN_BRIDGE_DISABLE_NTFY") == "1":
            return False
        return bool(self._post(title, body, priority, tags,
                               extra_headers).get("ok"))

    # --------------------------------------------------------- the 4 types
    def approval_required(self, task_title: str, action: str, risk: str,
                          link: str, request_id: str) -> dict:
        # `view` action + Click both OPEN the dashboard URL (GET only —
        # the token redeems a login session; the decision itself still
        # requires an authenticated CSRF-protected POST). No `http`
        # actions are ever attached — a notification can never approve.
        return self.send(
            dedup_key=f"APPROVAL|{request_id}",
            title="RealJarvis: Devin needs your approval",
            body=(f"Task: {task_title}\nAction: {action}\n"
                  f"Risk: {risk}\nStatus: Waiting for approval\n{link}"),
            priority="5", tags="warning,bell", urgent=True,
            extra_headers={
                "Click": link,
                "Actions": f"view, Open approval, {link}"})

    def task_completed(self, task_title: str, verdict: str,
                       next_task: str = "") -> dict:
        tail = f"\nNext: {next_task}" if next_task else ""
        return self.send(
            dedup_key=f"DONE|{task_title}|{verdict}",
            title="RealJarvis: Devin task completed",
            body=f"Task: {task_title}\nVerification: {verdict}{tail}",
            priority="3", tags="white_check_mark,jarvis")

    def task_failed(self, task_title: str, summary: str,
                    needed: str) -> dict:
        return self.send(
            dedup_key=f"FAIL|{task_title}|{summary[:60]}",
            title="RealJarvis: Devin task failed/blocked",
            body=(f"Task: {task_title}\nWhy: {summary}\n"
                  f"Needs: {needed}"),
            priority="4", tags="x,jarvis")

    def daily_summary(self, lines: list[str]) -> dict:
        today = utcnow()[:10]
        return self.send(
            dedup_key=f"SUMMARY|{today}",
            title="RealJarvis: daily development summary",
            body="\n".join(lines) or "No bridge activity.",
            priority="2", tags="chart_with_upwards_trend,jarvis")


def send_ntfy(title: str, body: str, priority: str = "5",
              topic: str = DEFAULT_TOPIC, tags: str = "warning,bell",
              timeout: float = 10.0) -> bool:
    """Back-compat single-shot helper (urgent priority like watchdog)."""
    return Notifier(Path("."), topic)._send_raw(
        title, body, priority, tags)

