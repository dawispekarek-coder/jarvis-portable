"""Mobile-friendly approval dashboard — stdlib only.

Binds 127.0.0.1:8765 by default (set DEVIN_APPROVAL_BIND/HOST/PORT; for
remote phone access point DEVIN_APPROVAL_BIND at the machine's Tailscale
IP — WireGuard-encrypted, never plain internet exposure).

Security model:
- Every page requires a session cookie. Sessions come ONLY from a
  single-use link token minted per request (inside the ntfy URL) or the
  local admin token file ``dashboard_admin.token`` (localhost use).
- Decisions need the per-session CSRF token.
- Decisions are single-use + staleness-checked by ApprovalManager;
  already-resolved/expired/mismatched → 409.
- Every hit to /decide is audit-logged (ip, ua, outcome) — a notification
  is never an approval; only an explicit in-dashboard POST is.

    python -m DevinBridge.approval_server
"""
from __future__ import annotations

import html
import json
import os
import secrets
import time
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import mobile_status
from .approvals import ApprovalManager
from .bridge_store import (append_jsonl, atomic_write_json, file_lock,
                           read_json, utcnow)

ROOT = Path(__file__).resolve().parent
SESSION_TTL_S = 12 * 3600
BIND = os.environ.get("DEVIN_APPROVAL_BIND", "127.0.0.1")
PORT = int(os.environ.get("DEVIN_APPROVAL_PORT", "8765"))
ADMIN_TOKEN_FILE = ROOT / "dashboard_admin.token"


def _admin_token() -> str:
    if not ADMIN_TOKEN_FILE.exists():
        ADMIN_TOKEN_FILE.write_text(secrets.token_urlsafe(24))
        try:
            os.chmod(ADMIN_TOKEN_FILE, 0o600)
        except OSError:
            pass
    return ADMIN_TOKEN_FILE.read_text().strip()


def _sessions_path() -> Path:
    return ROOT / "dashboard_sessions.json"


def _new_session(mgr: ApprovalManager) -> tuple[str, str]:
    sid, csrf = secrets.token_urlsafe(24), secrets.token_urlsafe(16)
    p = _sessions_path()
    with file_lock(ROOT / ".sess.lock"):
        d = read_json(p, {})
        cutoff = time.time() - SESSION_TTL_S
        d = {k: v for k, v in d.items() if v["exp"] > cutoff}
        d[sid] = {"csrf": csrf, "exp": time.time() + SESSION_TTL_S}
        atomic_write_json(p, d)
    return sid, csrf


def _get_session(sid: str) -> dict | None:
    d = read_json(_sessions_path(), {})
    s = d.get(sid)
    if s and s["exp"] > time.time():
        return s
    return None


PAGE = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>Jarvis Approvals</title><style>
body{font-family:system-ui;background:#101418;color:#e8eef4;margin:0;padding:14px}
h1{font-size:1.15rem}.card{background:#1a2129;border:1px solid #2c3947;
border-radius:10px;padding:14px;margin:12px 0}.risk-HIGH{color:#ff7070}
.risk-MEDIUM{color:#ffc466}.meta{color:#93a4b5;font-size:.8rem;word-break:break-all}
button{border:0;border-radius:8px;padding:12px 18px;font-size:1rem;margin-right:8px}
.approve{background:#2e7d4f;color:#fff}.reject{background:#8a3030;color:#fff}
.done{background:#22303d}.code{font-family:consolas,monospace;font-size:.75rem;
white-space:pre-wrap;background:#0c1014;border-radius:6px;padding:8px;max-height:180px;
overflow:auto}</style>
<h1>RealJarvis — Devin approvals</h1>
{%BODY%}
"""


def _render(mgr: ApprovalManager, csrf: str, flash: str = "") -> str:
    pend = mgr.pending()
    rows = ""
    for r in pend:
        tc = json.dumps(r.get("tool_call") or {}, indent=1)[:1200]
        left = max(int(r["expires_at_epoch"] - time.time()), 0)
        rows += f"""<div class=card>
<div><b>{html.escape(r['summary'])}</b>
<span class="risk-{r['risk']}"> [{r['risk']}]</span></div>
<div class=meta>task {r['task_id']} · session {r['session_id'][:24]} ·
req {r['request_id']} · {r['reason']} · expires in {left//60}m</div>
<div class=code>{html.escape(tc)}</div>
<form method=post action=/decide>
<input type=hidden name=csrf value="{csrf}">
<input type=hidden name=request_id value="{r['request_id']}">
<button class=approve name=decision value=approve>Approve</button>
<button class=reject name=decision value=reject>Reject</button></form></div>"""
    if not pend:
        rows = "<div class='card done'>Nothing pending.</div>"
    if flash:
        rows = f"<div class=card>{html.escape(flash)}</div>" + rows
    body = rows + ("<div class=meta>history: "
                   + f"{len(mgr._load()['requests'])} requests total</div>")
    return PAGE.replace("{%BODY%}", body)


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------- util
    def _send(self, code: int, body: str, ctype="text/html; charset=utf-8",
              headers: dict | None = None):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        # Mobile browsers over unstable Tailscale/4G should not accumulate
        # persistent idle HTTP/1.1 sockets, which can stall navigation.
        self.send_header("Connection", "close")
        self.close_connection = True
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _cookie_session(self) -> dict | None:
        raw = self.headers.get("Cookie") or ""
        c = cookies.SimpleCookie()
        try:
            c.load(raw)
        except cookies.CookieError:
            return None
        morsel = c.get("jr_session")
        return _get_session(morsel.value) if morsel else None

    def _audit(self, action: str, **kw):
        append_jsonl(ROOT / "dashboard_audit.jsonl", {
            "ts": utcnow(), "action": action,
            "ip": self.client_address[0],
            "ua": (self.headers.get("User-Agent") or "")[:120], **kw})

    def log_message(self, *a):  # quiet
        pass

    # ------------------------------------------------------------- GET
    def do_GET(self):
        mgr = ApprovalManager(ROOT)
        q = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(q.query)
        if q.path == '/mobile.webmanifest':
            self._send(200, mobile_status.MANIFEST,
                       ctype='application/manifest+json; charset=utf-8')
            return
        if q.path == '/status':
            if params.get('view'):
                sid = mobile_status.redeem_invite(params['view'][0])
                if not sid:
                    self._send(403, 'Neplatny nebo pouzity odkaz. Pozadej o novy.')
                    return
                self._audit('mobile_view_paired')
                self._send(302, '', headers={
                    'Location': '/status',
                    'Set-Cookie': f'jr_viewer={sid}; HttpOnly; SameSite=Lax; '
                                  f'Max-Age={mobile_status.VIEW_TTL}; Path=/status'})
                return
            if mobile_status.valid_view_cookie(self.headers.get('Cookie')) or self._cookie_session():
                self._send(200, mobile_status.render_status())
                return
            self._send(403, 'Pristup zamitnut. Otevri parovaci odkaz z ntfy.')
            return

        if params.get("admin"):  # local admin token → session
            if params["admin"][0] != _admin_token():
                self._audit("bad_admin_token")
                self._send(403, "bad token")
                return
            sid, _csrf = _new_session(mgr)
            self._audit("session_issued", request_id="admin")
            self._send(302, "", headers={
                "Location": "/", "Set-Cookie":
                f"jr_session={sid}; HttpOnly; SameSite=Lax; "
                f"Max-Age={SESSION_TTL_S}; Path=/"})
            return

        if params.get("t"):  # single-use link token → session
            rid = mgr.redeem_link_token(params["t"][0])
            if not rid:
                self._audit("bad_link_token")
                self._send(403, "<h3>Link expired or already used.</h3>")
                return
            sid, _csrf = _new_session(mgr)
            self._audit("session_issued", request_id=rid)
            self._send(302, "", headers={
                "Location": "/", "Set-Cookie":
                f"jr_session={sid}; HttpOnly; SameSite=Lax; "
                f"Max-Age={SESSION_TTL_S}; Path=/"})
            return

        sess = self._cookie_session()
        if not sess:
            self._send(403, "<h3>Not authorized. Use a fresh approval "
                            "link from your phone notification, or the "
                            "local admin token (?admin=...).</h3>")
            return
        if q.path == "/api/pending":
            self._send(200, json.dumps({"pending": mgr.pending()}),
                       ctype="application/json")
            return
        flash = ("Approved." if params.get("ok") else
                 "Rejected." if params.get("no") else
                 "That request is no longer pending." if params.get("stale")
                 else "")
        self._send(200, _render(mgr, sess["csrf"], flash))

    # ------------------------------------------------------------ POST
    def do_POST(self):
        mgr = ApprovalManager(ROOT)
        if self.path != "/decide":
            self._send(404, "")
            return
        sess = self._cookie_session()
        if not sess:
            self._audit("unauth_decide")
            self._send(403, "Not authorized")
            return
        n = int(self.headers.get("Content-Length") or 0)
        if n > 8192:
            self._send(413, "")
            return
        form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8"))
        if form.get("csrf", [""])[0] != sess["csrf"]:
            self._audit("csrf_fail")
            self._send(403, "CSRF check failed")
            return
        rid = form.get("request_id", [""])[0]
        decision = form.get("decision", [""])[0]
        if decision not in ("approve", "reject") or not rid:
            self._send(400, "bad request")
            return
        res = mgr.decide(rid, approved=(decision == "approve"),
                         decided_by=f"dashboard:{self.client_address[0]}")
        self._audit("decision", request_id=rid, decision=decision,
                    ok=res.get("ok"), error=res.get("error", ""))
        if res.get("ok"):
            q = "ok=1" if decision == "approve" else "no=1"
        else:
            q = "stale=1"
        self._send(302, "", headers={"Location": f"/?{q}"})


def serve(bind: str = BIND, port: int = PORT):
    ADMIN_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _admin_token()  # ensure exists
    httpd = ThreadingHTTPServer((bind, port), H)
    print(f"approval dashboard on http://{bind}:{port} "
          f"(admin token in {ADMIN_TOKEN_FILE})")
    httpd.serve_forever()


if __name__ == "__main__":
    import sys
    b = sys.argv[1] if len(sys.argv) > 1 else BIND
    p = int(sys.argv[2]) if len(sys.argv) > 2 else PORT
    serve(b, p)
