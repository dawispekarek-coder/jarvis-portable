"""Fake ``devin acp`` server for hermetic tests.

Speaks the same JSON-RPC-over-stdio surface the real server does:
initialize / authenticate / session/new / session/prompt / session/list /
session/load / session/set_config_option / session/close / session/cancel.

Simulated execution channel: if a prompt contains
``CREATE_FILE:<name>:<content>`` the file is written inside the session's
cwd — producing real filesystem evidence a verifier can check, without a
live agent.
"""
import json
import os
import re
import sys
import time

_SESSIONS_FILE = os.environ.get("FAKE_ACP_SESSIONS")
SESSIONS = {}
COUNT = [0]


def _persist():
    """Share sessions across fake processes (mirrors the real server's
    sessions.db — a second acp process can load another's session)."""
    if not _SESSIONS_FILE:
        return
    try:
        with open(_SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({"sessions": SESSIONS, "count": COUNT[0]}, f)
    except OSError:
        pass


def _restore():
    global SESSIONS
    if not _SESSIONS_FILE or not os.path.exists(_SESSIONS_FILE):
        return
    try:
        d = json.load(open(_SESSIONS_FILE, encoding="utf-8"))
        SESSIONS = d.get("sessions", {})
        COUNT[0] = int(d.get("count", 0))
    except Exception:
        pass


_restore()


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def handle(m):
    method = m.get("method")
    p = m.get("params") or {}
    mid = m.get("id")
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": 1,
            "agentCapabilities": {"loadSession": True,
                                  "promptCapabilities": {"image": True}},
            "authMethods": [{"id": "devin-browser"}],
            "agentInfo": {"name": "fake-devin", "version": "test"}}})
    elif method == "authenticate":
        if not (p.get("_meta") or {}).get("api_key"):
            send({"jsonrpc": "2.0", "id": mid, "error": {
                "code": -32000, "message": "api_key required"}})
        else:
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
    elif method == "session/new":
        COUNT[0] += 1
        sid = f"fake-session-{COUNT[0]}"
        SESSIONS[sid] = {"cwd": p.get("cwd", ""), "messages": 0,
                         "model": p.get("model") or "swe-2-high"}
        _persist()
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "sessionId": sid,
            "modes": {"currentModeId": "accept-edits",
                      "availableModes": [{"id": "accept-edits"}]},
            "configOptions": [
                {"id": "model", "type": "select",
                 "currentValue": SESSIONS[sid]["model"],
                 "options": [{"value": "swe-2-high"}]}]}})
    elif method == "session/load":
        sid = p.get("sessionId")
        _restore()
        if sid in SESSIONS:
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "modes": {"currentModeId": "accept-edits"},
                "configOptions": []}})
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {
                "code": -32000, "message": "session not found"}})
    elif method == "session/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"sessions": [
            {"sessionId": s, "cwd": v["cwd"], "title": "fake",
             "updatedAt": "2026-01-01T00:00:00Z"}
            for s, v in SESSIONS.items()]}})
    elif method == "session/set_config_option":
        sid = p.get("sessionId")
        if sid in SESSIONS and p.get("configId") == "model":
            if p.get("value") == "swe-2-max":
                send({"jsonrpc": "2.0", "id": mid, "error": {
                    "code": -32602, "message": "Invalid params",
                    "data": "Invalid value 'swe-2-max'"}})
                return
            SESSIONS[sid]["model"] = p.get("value")
        send({"jsonrpc": "2.0", "id": mid, "result": {"configOptions": [
            {"id": "model", "currentValue": SESSIONS.get(
                sid, {}).get("model", "")}]}})
    elif method == "session/prompt":
        sid = p.get("sessionId")
        _restore()
        text = "".join(c.get("text", "") for c in p.get("prompt", [])
                       if c.get("type") == "text")
        sess = SESSIONS.get(sid)
        reply = "MOCK_OK"
        # PERM:<kind>:<title> — ask the host for permission, wait for its
        # answer, continue only if an allow option was selected.
        pm = re.search(r"PERM:([a-z_]+):([^\n]+)", text)
        if sess and pm:
            req_id = 9000 + COUNT[0]
            send({"jsonrpc": "2.0", "id": req_id,
                  "method": "session/request_permission",
                  "params": {"sessionId": sid, "toolCall": {
                      "kind": pm.group(1), "title": pm.group(2).strip(),
                      "rawInput": {"command": pm.group(2).strip()},
                      "locations": []},
                      "options": [
                          {"optionId": "o-allow-once", "name": "Allow",
                           "kind": "allow_once"},
                          {"optionId": "o-reject", "name": "Reject",
                           "kind": "reject_once"}]}})
            for line in sys.stdin:  # wait for the host's response
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("id") == req_id:
                    outcome = ((r.get("result") or {})
                               .get("outcome") or {})
                    if outcome.get("outcome") == "selected" and \
                            "allow" in str(outcome.get("optionId", "")):
                        reply = "permission granted, action done"
                        sess["perm_granted"] = True
                    else:
                        reply = "permission denied; did not proceed"
                        sess["perm_granted"] = False
                    break
        denied = sess and sess.get("perm_granted") is False
        mm = re.search(r"CREATE_FILE:([^\s:]+):(.+)", text, re.S)
        if sess and mm and not denied:
            import pathlib
            fp = pathlib.Path(sess["cwd"]) / mm.group(1)
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(mm.group(2).strip(), encoding="utf-8")
            reply = f"created {mm.group(1)}"
        if "FAIL_ME" in text:
            reply = "simulated failure"
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": sid,
            "update": {"sessionUpdate": "agent_message_chunk",
                       "content": {"type": "text", "text": reply}}}})
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": sid,
            "update": {"sessionUpdate": "usage_update",
                       "used": 100, "size": 262000}}})
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "stopReason": "end_turn",
            "usage": {"totalTokens": 100, "inputTokens": 90,
                      "outputTokens": 10}}})
    elif method == "session/cancel":
        pass  # notification — no response per ACP
    elif method == "session/close":
        send({"jsonrpc": "2.0", "id": mid, "result": {}})
    elif mid is not None:
        send({"jsonrpc": "2.0", "id": mid, "error": {
            "code": -32601, "message": f"method not found: {method}"}})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except Exception as e:
            sys.stderr.write(f"fake_acp error: {e}\n")


if __name__ == "__main__":
    main()
