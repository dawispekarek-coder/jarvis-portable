"""Observed Windows UIA controls with single-use, state-bound write references.

No application launch, shell, keyboard injection, coordinate clicks, or app closing.
Windows and pywinauto imports stay lazy so the companion can run elsewhere.
"""
from __future__ import annotations

from collections import deque
import hashlib
import importlib.util
import json
import ntpath
import os
from pathlib import Path
import re
import uuid

from companion_registry import ToolError


MAX_CONTROLS = 80
MAX_DEPTH = 4
MAX_TEXT = 4000
_SENSITIVE = re.compile(
    r'password|passcode|passwd|credential|secret|api[ _-]*key|token|'
    r'\bpin\b|\botp\b|one.time.code|verification.code|credit.card|card.number|'
    r'\bcvv\b|\bcvc\b|social.security|\bssn\b|heslo|soubor|'
    r'file[ _-]*(name|path|upload)|upload|browse', re.IGNORECASE)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def _content_digest(state):
    # Focus changes while the user reviews approval. Keep the original approval
    # token bound to exact target contents; validate foreground independently.
    return _digest({key: value for key, value in state.items() if key != 'foreground_handle'})


def _foreground_handle():
    import ctypes
    from ctypes import wintypes
    get_foreground = ctypes.windll.user32.GetForegroundWindow
    get_foreground.restype = wintypes.HWND
    return int(get_foreground() or 0)


def _window_process_cmdline(handle):
    """Read the owning process, never infer ownership from a window title."""
    import ctypes
    from ctypes import wintypes
    import psutil
    get_process = ctypes.windll.user32.GetWindowThreadProcessId
    get_process.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    get_process.restype = wintypes.DWORD
    pid = wintypes.DWORD()
    if not get_process(wintypes.HWND(handle), ctypes.byref(pid)) or not pid.value:
        return []
    return psutil.Process(pid.value).cmdline()


class DesktopAdapter:
    def __init__(self, out):
        self.out = Path(out)
        self.available = os.name == 'nt' and importlib.util.find_spec('pywinauto') is not None
        self._window = None
        self._window_identity = None
        self._approved = None
        self.refs = {}
        self.document_id = ''
        self.state_hash = ''

    def _require_available(self):
        if not self.available:
            raise ToolError('desktop_unavailable_windows_uia_required')

    def _discard_approval(self):
        self.refs = {}
        self.document_id = ''
        self.state_hash = ''
        self._approved = None

    def _is_companion_foreground(self, handle):
        try:
            command = _window_process_cmdline(handle)
            if not command or ntpath.basename(command[0]).casefold() != 'msedge.exe':
                return False
            apps = [arg for arg in command if arg.startswith('--app=')]
            profiles = [arg for arg in command if arg.startswith('--user-data-dir=')]
            if apps != ['--app=http://127.0.0.1:7430/'] or len(profiles) != 1:
                return False
            profile = profiles[0].split('=', 1)[1].strip('"')
            if not os.path.isabs(profile):
                return False
            expected = self.out.parent.parent / 'BrowserProfile'
            return os.path.normcase(os.path.realpath(profile)) == os.path.normcase(os.path.realpath(expected))
        except Exception:
            return False

    @staticmethod
    def _entry(control, inherited_sensitive=False, file_dialog=False):
        info = control.element_info
        # UIA wrappers may enable property caches while locating a window.
        # Approval checks must query the provider again, including the root.
        info.set_cache_strategy(False)
        role = str(info.control_type or '')
        name = str(info.name or '')
        auto_id = str(info.automation_id or '')
        password = bool(info.element.CurrentIsPassword)
        sensitive = bool(inherited_sensitive or password or
                         _SENSITIVE.search(name + ' ' + auto_id) or
                         (file_dialog and role in ('Edit', 'ComboBox')))
        runtime_id = list(info.runtime_id or [])
        identity = {'process_id': int(info.process_id), 'runtime_id': runtime_id,
                    'automation_id': auto_id, 'role': role,
                    'name': '[protected]' if sensitive else name}
        value = ''
        if role == 'Edit' and not sensitive:
            value = str(control.get_value())
        return {**identity, 'name': identity['name'][:240],
                'automation_id': auto_id[:240], 'value': value[:MAX_TEXT],
                'identity_hash': _digest(identity), 'value_hash': _digest(value),
                'visible': bool(control.is_visible()),
                'enabled': bool(control.is_enabled()), 'sensitive': sensitive}

    def _capture(self):
        """Capture only the observed session; never search/reconnect during a write."""
        if self._window is None:
            raise ToolError('desktop_session_lost_observe_again')
        try:
            foreground = _foreground_handle()
            root = self._window
            root_entry = self._entry(root)
            handle = int(root.element_info.handle or 0)
            window = {'handle': handle, 'process_id': root_entry['process_id'],
                      'runtime_id': root_entry['runtime_id']}
            if not root_entry['visible'] or window != self._window_identity:
                raise ToolError('desktop_session_lost_observe_again')
            file_dialog = (str(root.element_info.class_name) == '#32770' and
                           str(root.element_info.name).casefold() in
                           ('open', 'save', 'save as', 'otevřít', 'uložit jako'))
            rows, wrappers = [], []
            queue = deque([(root, 0, False)])
            truncated = False
            while queue and len(rows) < MAX_CONTROLS:
                control, depth, inherited = queue.popleft()
                entry = self._entry(control, inherited, file_dialog)
                entry['depth'] = depth
                rows.append(entry)
                wrappers.append(control)
                remaining = MAX_CONTROLS - len(rows) - len(queue)
                if depth >= MAX_DEPTH or remaining <= 0:
                    # Coverage past either boundary is deliberately unknown.
                    truncated = True
                    continue
                children = control.children()
                if len(children) > remaining:
                    truncated = True
                queue.extend((child, depth + 1, entry['sensitive'])
                             for child in children[:remaining])
            if _foreground_handle() != foreground:
                raise ToolError('desktop_foreground_changed_observe_again')
            state = {'title': root_entry['name'], 'window': window,
                     'foreground_handle': foreground, 'elements': rows,
                     'truncated': truncated}
            return state, wrappers
        except ToolError:
            raise
        except Exception as exc:
            self._discard_approval()
            self._window = None
            raise ToolError('desktop_session_lost_observe_again') from exc

    def observe(self, title=''):
        self._require_available()
        self._discard_approval()
        self._window = None
        try:
            from pywinauto import Desktop
            backend = Desktop(backend='uia')
            if title:
                matches = [w for w in backend.windows()
                           if str(w.element_info.name) == title]
                if len(matches) != 1:
                    raise ToolError('desktop_title_ambiguous' if matches else 'desktop_window_not_found')
                window = matches[0]
            else:
                handle = _foreground_handle()
                if not handle:
                    raise ToolError('desktop_foreground_unavailable')
                window = backend.window(handle=handle).wrapper_object()
            self._window = window
            info = window.element_info
            self._window_identity = {'handle': int(info.handle or 0),
                                     'process_id': int(info.process_id),
                                     'runtime_id': list(info.runtime_id or [])}
            return self._snapshot()
        except ToolError:
            raise
        except Exception as exc:
            self._window = None
            raise ToolError('desktop_observation_unavailable') from exc

    def _snapshot(self):
        state, _ = self._capture()
        self.document_id = uuid.uuid4().hex
        self.state_hash = _content_digest(state)
        self._approved = state
        self.refs = {}
        for index, entry in enumerate(state['elements']):
            ref = 'd' + _digest([self.document_id, index, entry])[:18]
            self.refs[ref] = (index, entry)
        result = {**state, 'document_id': self.document_id,
                  'state_hash': self.state_hash,
                  'elements': [{'ref': ref, **entry} for ref, (_, entry) in self.refs.items()],
                  'verified': True}
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / 'desktop_snapshot.json').write_text(
            json.dumps(result, ensure_ascii=False), encoding='utf-8')
        return result

    def _locate(self, ref, document_id, state_hash, *, allow_companion_ui=False):
        self._require_available()
        if self._window is None or self._approved is None:
            raise ToolError('desktop_session_lost_observe_again')
        if document_id != self.document_id or state_hash != self.state_hash:
            raise ToolError('approved_document_or_action_changed')
        if ref not in self.refs:
            raise ToolError('unknown_or_stale_reference')
        state, controls = self._capture()
        foreground = state['foreground_handle']
        if foreground != state['window']['handle']:
            if not allow_companion_ui or not self._is_companion_foreground(foreground):
                raise ToolError('desktop_foreground_changed_observe_again')
        if _content_digest(state) != state_hash:
            raise ToolError('approved_document_or_action_changed')
        index, expected = self.refs[ref]
        current = state['elements'][index]
        if current != expected:
            raise ToolError('desktop_element_changed_observe_again')
        if current['sensitive']:
            raise ToolError('sensitive_input_not_supported')
        if not current['visible'] or not current['enabled']:
            raise ToolError('desktop_control_not_actionable')
        if not current['runtime_id'] or current['process_id'] <= 0:
            raise ToolError('desktop_control_identity_unavailable')
        return controls[index], current

    def prepare_approved_action(self, args):
        """Call only after Store.approved has matched the exact action arguments.

        Only our authenticated approval UI may yield focus to the exact stored
        target. The original document/reference/content tokens remain unchanged.
        click/fill still perform their normal strict foreground and state checks.
        """
        ref, document_id, state_hash = args['ref'], args.get('document_id'), args.get('state_hash')
        self._locate(ref, document_id, state_hash, allow_companion_ui=True)
        target = self._window_identity['handle']
        foreground = _foreground_handle()
        if foreground != target:
            if not self._is_companion_foreground(foreground):
                raise ToolError('desktop_foreground_changed_observe_again')
            # Recheck the complete target immediately before the one focus attempt.
            self._locate(ref, document_id, state_hash, allow_companion_ui=True)
            if _foreground_handle() != foreground:
                raise ToolError('desktop_foreground_changed_observe_again')
            try:
                self._window.set_focus()
            except Exception as exc:
                raise ToolError('desktop_foreground_restore_failed') from exc
            if _foreground_handle() != target:
                raise ToolError('desktop_foreground_restore_not_verified')
        self._locate(ref, document_id, state_hash)
        return {'verified': True, 'foreground_prepared': True,
                'document_id': document_id, 'state_hash': state_hash}

    def action_context(self, name, args):
        _, entry = self._locate(args['ref'], args.get('document_id'), args.get('state_hash'),
                                allow_companion_ui=True)
        if name not in ('desktop_fill', 'desktop_click'):
            raise ToolError('unsupported_desktop_action')
        action = 'Vyplnit pole' if name == 'desktop_fill' else 'Aktivovat prvek'
        if _foreground_handle() != self._window_identity['handle']:
            action = 'Přepnout do aplikace a ' + action.lower()
        return {'title': self._approved['title'], 'label': entry['name'] or entry['automation_id'] or entry['role'],
                'action': action,
                'value': args.get('text', ''), 'document_id': self.document_id,
                'state_hash': self.state_hash}

    def click(self, ref, document_id=None, state_hash=None):
        control, _ = self._locate(ref, document_id, state_hash)
        invoke = getattr(control, 'invoke', None)
        if not callable(invoke):
            raise ToolError('desktop_invoke_not_supported')
        self._discard_approval()
        try:
            invoke()
        except Exception as exc:
            raise ToolError('desktop_invoke_failed_or_unsupported_observe_again') from exc
        result = self._snapshot()
        result['invoke_dispatched'] = True
        result['effect_observed'] = result['state_hash'] != state_hash
        result['verified'] = result['effect_observed']
        return result

    def fill(self, ref, text, document_id=None, state_hash=None):
        if not isinstance(text, str) or len(text) > MAX_TEXT:
            raise ToolError('desktop_text_invalid_or_too_long')
        control, entry = self._locate(ref, document_id, state_hash)
        if entry['role'] != 'Edit':
            raise ToolError('desktop_edit_control_required')
        self._discard_approval()
        try:
            control.set_edit_text(text)
            if str(control.get_value()) != text:
                raise ToolError('desktop_field_value_not_verified')
            # Re-read the tree independently, binding readback to the same element.
            result = self._snapshot()
            matches = [e for e in result['elements'] if e['identity_hash'] == entry['identity_hash']]
            if len(matches) != 1 or matches[0]['value'] != text:
                self._discard_approval()
                raise ToolError('desktop_field_value_not_verified')
            return {**result, 'field_value_verified': True}
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError('desktop_field_value_not_verified_observe_again') from exc
