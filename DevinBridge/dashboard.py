"""Self-contained HTML dashboard — reads dashboard_state.json content
inlined at render time; file:// friendly, no server required.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def render_dashboard(st: dict[str, Any], out_path: Path) -> None:
    rows = []
    for t in st.get("tasks", []):
        cls = {"COMPLETE": "ok", "RUNNING": "run", "VERIFYING": "run",
               "FAILED": "bad", "BLOCKED": "warn",
               "NEEDS_REVIEW": "warn", "PAUSED": "warn"}.get(
                   t.get("status", ""), "")
        rows.append(
            f"<tr class='{cls}'><td>{html.escape(t.get('id',''))}</td>"
            f"<td>{html.escape(t.get('status',''))}</td>"
            f"<td>{html.escape((t.get('title') or '')[:60])}</td>"
            f"<td>{html.escape(t.get('session_id',''))}</td>"
            f"<td>{t.get('attempts',0)}</td>"
            f"<td>{'Y' if t.get('approved') else '—'}</td>"
            f"<td>{html.escape((t.get('last_error') or '')[:80])}</td></tr>")
    sess = "".join(
        f"<tr><td>{html.escape(s.get('id',''))}</td>"
        f"<td>{html.escape((s.get('model') or ''))}</td>"
        f"<td>{html.escape((s.get('title') or '')[:60])}</td></tr>"
        for s in st.get("sessions_recent", []))
    holds = "".join(f"<li>{html.escape(h)}</li>"
                    for h in st.get("global_holds", [])) or "<li>none</li>"
    counts = st.get("counts", {})
    mode = st.get("mode", "safe").upper()
    mode_cls = "bad" if mode == "AUTONOMOUS" else "ok"
    body = f"""<!doctype html><html><head><meta charset=utf-8>
<meta http-equiv=refresh content=30>
<title>RealJarvis Devin Bridge</title><style>
body{{font-family:Consolas,monospace;background:#101418;color:#d7e0ea;margin:24px}}
h1{{font-size:20px}} .card{{background:#161c24;border:1px solid #2a3442;border-radius:8px;padding:14px;margin:10px 0}}
table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{border-bottom:1px solid #232c38;padding:4px 8px;text-align:left}}
.ok{{color:#7ee787}} .run{{color:#79c0ff}} .warn{{color:#e3b341}} .bad{{color:#ff7b72}}
.kv b{{display:inline-block;min-width:210px;color:#8b98a8;font-weight:normal}}
</style></head><body>
<h1>RealJarvis — Devin Bridge</h1>
<div class=card>
<div class=kv><b>mode</b> <span class={mode_cls}>{mode}</span>
 (autonomous flag: {'SET' if st.get('autonomous_flag') else 'absent'}, paused: {'YES' if st.get('paused') else 'no'})</div>
<div class=kv><b>model</b> {html.escape(st.get('model',''))}</div>
<div class=kv><b>counts</b> {html.escape(json.dumps(counts))}</div>
<div class=kv><b>next eligible</b> {html.escape(str(st.get('next_eligible')))} — {html.escape(str(st.get('next_eligible_reason','')))}</div>
<div class=kv><b>running</b> {html.escape(json.dumps(st.get('running',[])))}</div>
<div class=kv><b>stats</b> {html.escape(json.dumps(st.get('stats',{})))}</div>
<div class=kv><b>github</b> {html.escape(json.dumps(st.get('github',{})))}</div>
<div class=kv><b>generated</b> {html.escape(str(st.get('generated_at','')))}</div>
</div>
<div class=card><b>Holds</b><ul>{holds}</ul></div>
<div class=card><b>Tasks</b><table>
<tr><th>id</th><th>status</th><th>title</th><th>session</th><th>attempts</th><th>approved</th><th>last error</th></tr>
{''.join(rows) or '<tr><td colspan=7>no tasks</td></tr>'}</table></div>
<div class=card><b>Recent Devin sessions (local)</b><table>
<tr><th>id</th><th>model</th><th>title</th></tr>{sess}</table></div>
</body></html>"""
    out_path.write_text(body, encoding="utf-8")
