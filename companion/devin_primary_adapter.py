"""Devin primary-brain adapter for JARVIS 2.1 Companion.

Routes PLAIN conversational goals to the local Devin ACP agent
(swe-2-high) via the existing DevinBridge package. Tool/action goals
stay on the Ollama tool loop untouched.

Honesty contract: reply() returns text ONLY for a genuine Devin answer
(envelope brain=='devin'); any failure returns None and the caller falls
back to Ollama — the state records which brain answered.
"""
from __future__ import annotations

import sys

BRIDGE_PACKAGE_PARENT = r"C:\Users\Dawis\ForeverRouteJarvis"
_brain = None


def _get(persona: str, model: str = "swe-2-high"):
    global _brain
    if _brain is None:
        if BRIDGE_PACKAGE_PARENT not in sys.path:
            sys.path.insert(0, BRIDGE_PACKAGE_PARENT)
        from DevinBridge.chat import DevinBrain
        from DevinBridge.daemon import load_config, make_coordinator
        _brain = DevinBrain(make_coordinator(load_config()),
                            persona=persona, model=model)
    elif persona:
        _brain.persona = persona
    return _brain


def reply(user_text: str, persona: str, model: str = "swe-2-high",
          timeout_s: float = 240.0) -> str | None:
    """Return Devin's reply text or None when Devin could not answer."""
    if not user_text or not user_text.strip():
        return None
    try:
        env = _get(persona, model).respond(user_text, timeout=timeout_s)
    except Exception:
        return None
    if not isinstance(env, dict) or env.get("brain") != "devin":
        return None
    text = (env.get("text") or "").strip()
    if not text or len(text) > 6000:
        return None
    # Tool-call/protocol artifacts must never be shown as chat text.
    lt = text.lstrip()
    if lt.startswith(('{"tool"', '<tool_call', '<' + '|')):
        return None
    return text
