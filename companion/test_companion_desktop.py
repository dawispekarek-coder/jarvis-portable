"""Desktop contracts tested without a Windows desktop or injected action bypasses."""
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import companion_desktop as desktop
except ImportError:
    desktop = None
from companion_registry import ToolError


class Control:
    """Small UIA provider fixture; reads and mutations share actual state."""
    def __init__(self, name, role='Button', rid=1, children=(), value='',
                 password=False, automation_id='', handle=0):
        self.element_info = types.SimpleNamespace(
            name=name, control_type=role, runtime_id=[42, rid], process_id=700,
            automation_id=automation_id, handle=handle, class_name='Fixture',
            element=types.SimpleNamespace(CurrentIsPassword=password),
            set_cache_strategy=lambda cached: None)
        self.nodes = list(children)
        self.value = value
        self.alive = True
        self.enabled = True
        self.visible = True
        self.accept_text = True
        self.children_reads = 0
        self.invocations = 0
        self.on_invoke = lambda: None
        self.on_focus = lambda: None
        self.focuses = 0

    def children(self):
        self.children_reads += 1
        return list(self.nodes)

    def descendants(self):
        raise AssertionError('Unbounded tree traversal is forbidden')

    def is_visible(self):
        if not self.alive:
            raise RuntimeError('UIA element no longer exists')
        return self.visible

    def is_enabled(self):
        return self.enabled

    def get_value(self):
        if self.element_info.element.CurrentIsPassword:
            raise AssertionError('Password values must never be read')
        return self.value

    def set_edit_text(self, text):
        if self.accept_text:
            self.value = text

    def invoke(self):
        self.invocations += 1
        self.on_invoke()

    def set_focus(self):
        self.focuses += 1
        self.on_focus()


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(desktop, 'Windows desktop adapter is missing')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.edit = Control('Message', 'Edit', 2, value='draft', automation_id='message')
        self.status = Control('Ready', 'Text', 3)
        self.button = Control('Apply', rid=4)
        self.root = Control('Notes', 'Window', 100,
                            [self.edit, self.status, self.button], handle=900)
        self.windows = [self.root]
        self.foreground = 900
        self.commands = {}
        self.root.on_focus = lambda: setattr(self, 'foreground', 900)
        owner = self

        class Backend:
            def __init__(self, backend):
                if backend != 'uia':
                    raise AssertionError('UIA is required')

            def windows(self):
                return list(owner.windows)

            def window(self, handle):
                matches = [w for w in owner.windows if w.element_info.handle == handle]
                if len(matches) != 1:
                    raise RuntimeError('Window disappeared')
                return types.SimpleNamespace(wrapper_object=lambda: matches[0])

        self.adapter = desktop.DesktopAdapter(Path(self.tmp.name))
        self.adapter.available = True
        self.addCleanup(patch.stopall)
        patch.dict('sys.modules', {'pywinauto': types.SimpleNamespace(Desktop=Backend)}).start()
        patch.object(desktop, '_foreground_handle', side_effect=lambda: self.foreground).start()
        patch.object(desktop, '_window_process_cmdline',
                     side_effect=lambda handle: self.commands.get(handle, []), create=True).start()

    def observe(self):
        return self.adapter.observe()

    @staticmethod
    def ref(snapshot, name):
        return next(e['ref'] for e in snapshot['elements'] if e['name'] == name)

    def args(self, snapshot, name):
        return {'ref': self.ref(snapshot, name), 'document_id': snapshot['document_id'],
                'state_hash': snapshot['state_hash']}

    def companion_foreground(self):
        self.foreground = 905
        self.commands[905] = [r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                              '--app=http://127.0.0.1:7430/',
                              '--user-data-dir=' + str((self.adapter.out.parent.parent / 'BrowserProfile').resolve())]

    def prepare(self, args):
        self.assertTrue(callable(getattr(self.adapter, 'prepare_approved_action', None)),
                        'Approved focus restoration is missing')
        return self.adapter.prepare_approved_action(args)

    def test_unavailable_adapter_fails_before_any_desktop_access(self):
        self.adapter.available = False
        with self.assertRaisesRegex(ToolError, 'unavailable'):
            self.observe()

    def test_snapshot_has_real_labels_values_and_stable_fingerprint(self):
        first = self.observe()
        self.assertTrue(first['verified'])
        self.assertEqual(first['title'], 'Notes')
        self.assertEqual(next(e['value'] for e in first['elements'] if e['name'] == 'Message'), 'draft')
        self.assertEqual(len(first['state_hash']), 64)
        again = self.observe()
        self.assertEqual(again['state_hash'], first['state_hash'])
        self.edit.value = 'new draft'
        self.assertNotEqual(self.observe()['state_hash'], first['state_hash'])

    def test_snapshot_redacts_password_and_file_content_without_reading_it(self):
        self.root.nodes.extend([
            Control('hunter2', 'Edit', 5, value='hunter2', password=True),
            Control('File name:', 'Edit', 6, value='C:/private/secret.txt')])
        data = self.observe()
        serialized = json.dumps(data)
        self.assertNotIn('hunter2', serialized)
        self.assertNotIn('private/secret', serialized)
        persisted = (Path(self.tmp.name) / 'desktop_snapshot.json').read_text()
        self.assertNotIn('hunter2', persisted)

    def test_wrong_document_and_changed_state_never_write(self):
        snap = self.observe()
        args = self.args(snap, 'Message')
        with self.assertRaises(ToolError):
            self.adapter.fill(text='bad', **{**args, 'document_id': 'unapproved'})
        self.status.element_info.name = 'New dialog'
        with self.assertRaises(ToolError):
            self.adapter.fill(text='bad', **args)
        self.assertEqual(self.edit.value, 'draft')

    def test_replaced_control_with_same_label_is_rejected(self):
        snap = self.observe()
        replacement = Control('Message', 'Edit', 999, value='draft', automation_id='message')
        self.root.nodes[0] = replacement
        with self.assertRaises(ToolError):
            self.adapter.fill(text='bad', **self.args(snap, 'Message'))
        self.assertEqual(replacement.value, 'draft')

    def test_foreground_change_requires_new_observation(self):
        snap = self.observe()
        self.foreground = 901
        with self.assertRaisesRegex(ToolError, 'foreground'):
            self.adapter.click(**self.args(snap, 'Apply'))
        self.assertEqual(self.button.invocations, 0)

    def test_cached_window_properties_cannot_hide_a_changed_title(self):
        class CachedInfo(types.SimpleNamespace):
            cached = True

            def __getattribute__(self, name):
                if name == 'name' and self.cached:
                    return 'Notes'
                return super().__getattribute__(name)

            def set_cache_strategy(self, cached):
                self.cached = cached

        values = dict(vars(self.root.element_info))
        del values['set_cache_strategy']
        self.root.element_info = CachedInfo(**values)
        snap = self.observe()
        self.root.element_info.name = 'Unexpected new document'
        with self.assertRaises(ToolError):
            self.adapter.click(**self.args(snap, 'Apply'))
        self.assertEqual(self.button.invocations, 0)

    def test_approved_companion_transition_restores_target_before_write(self):
        snap = self.observe()
        args = {**self.args(snap, 'Message'), 'text': 'approved from companion'}
        self.companion_foreground()
        error = None
        try:
            context = self.adapter.action_context('desktop_fill', args)
        except ToolError as exc:
            error = exc
        self.assertIsNone(error, 'Our authenticated approval UI must allow a read-only context')
        self.assertEqual(context['label'], 'Message')
        self.assertEqual(self.foreground, 905)
        with self.assertRaises(ToolError):
            self.adapter.fill(**args)
        prepared = self.prepare(args)
        self.assertTrue(prepared['verified'])
        self.assertEqual(self.foreground, 900)
        result = self.adapter.fill(**args)
        self.assertEqual(self.edit.value, 'approved from companion')
        self.assertTrue(result['field_value_verified'])

    def test_explicit_title_background_observation_keeps_original_approval_tokens(self):
        self.companion_foreground()
        snap = self.adapter.observe('Notes')
        args = self.args(snap, 'Message')
        self.prepare(args)
        self.assertEqual(self.adapter.document_id, args['document_id'])
        self.assertEqual(self.adapter.state_hash, args['state_hash'])
        self.assertEqual(self.foreground, 900)
        self.assertTrue(self.adapter.fill(text='background target', **args)['field_value_verified'])

    def test_lookalike_apps_or_wrong_profiles_never_receive_focus_restoration(self):
        snap = self.observe()
        args = self.args(snap, 'Message')
        self.companion_foreground()
        valid = list(self.commands[905])
        variants = [valid[:1],
                    [valid[0], '--app=http://127.0.0.1:7430/other', valid[2]],
                    [valid[0], valid[1], valid[2] + '-different'],
                    [r'C:\Tools\unrelated.exe', *valid[1:]],
                    [*valid, r'--user-data-dir=C:\OtherProfile']]
        for command in variants:
            with self.subTest(command=command):
                self.commands[905] = command
                with self.assertRaisesRegex(ToolError, 'foreground|companion'):
                    self.prepare(args)
                self.assertEqual(self.foreground, 905)
                self.assertEqual(self.root.focuses, 0)
                self.assertEqual(self.edit.value, 'draft')

    def test_changed_target_is_refused_before_restoring_from_approval_ui(self):
        snap = self.observe()
        self.companion_foreground()
        self.status.element_info.name = 'Unexpected document change'
        with self.assertRaisesRegex(ToolError, 'changed'):
            self.prepare(self.args(snap, 'Message'))
        self.assertEqual(self.foreground, 905)
        self.assertEqual(self.root.focuses, 0)

    def test_failed_focus_restoration_cannot_enable_a_write(self):
        snap = self.observe()
        self.companion_foreground()
        self.root.on_focus = lambda: None
        with self.assertRaisesRegex(ToolError, 'foreground'):
            self.prepare(self.args(snap, 'Message'))
        with self.assertRaises(ToolError):
            self.adapter.fill(text='bad', **self.args(snap, 'Message'))
        self.assertEqual(self.edit.value, 'draft')

    def test_lost_session_is_not_recreated(self):
        snap = self.observe()
        self.root.alive = False
        self.windows = [Control('Notes', 'Window', 101, handle=900)]
        with self.assertRaisesRegex(ToolError, 'session_lost'):
            self.adapter.fill(text='bad', **self.args(snap, 'Message'))
        self.assertEqual(self.edit.value, 'draft')

    def test_fill_requires_session_and_independently_verifies_actual_value(self):
        with self.assertRaisesRegex(ToolError, 'session_lost'):
            self.adapter.fill('invented', 'bad', 'document', 'hash')
        snap = self.observe()
        result = self.adapter.fill(text='approved text', **self.args(snap, 'Message'))
        self.assertEqual(self.edit.value, 'approved text')
        self.assertTrue(result['field_value_verified'])
        self.assertTrue(result['verified'])
        self.assertNotEqual(result['document_id'], snap['document_id'])
        self.edit.accept_text = False
        with self.assertRaisesRegex(ToolError, 'not_verified'):
            self.adapter.fill(text='ignored', **self.args(result, 'Message'))

    def test_click_uses_invoke_and_observes_its_effect(self):
        self.button.on_invoke = lambda: setattr(self.status.element_info, 'name', 'Applied')
        snap = self.observe()
        result = self.adapter.click(**self.args(snap, 'Apply'))
        self.assertEqual(self.button.invocations, 1)
        self.assertIn('Applied', [e['name'] for e in result['elements']])
        self.assertTrue(result['verified'])

    def test_unsupported_click_never_uses_coordinate_fallback(self):
        self.button.invoke = None
        snap = self.observe()
        with self.assertRaisesRegex(ToolError, 'invoke'):
            self.adapter.click(**self.args(snap, 'Apply'))
        self.assertEqual(self.button.invocations, 0)

    def test_sensitive_and_file_edits_are_not_actionable(self):
        self.root.nodes.extend([
            Control('Password', 'Edit', 5, password=True),
            Control('File name:', 'Edit', 6),
            Control('API token', 'Edit', 7)])
        snap = self.observe()
        for item in [e for e in snap['elements'] if e.get('sensitive')]:
            with self.subTest(item=item['ref']):
                with self.assertRaisesRegex(ToolError, 'sensitive'):
                    self.adapter.fill(item['ref'], 'bad', snap['document_id'], snap['state_hash'])
        self.assertEqual(sum(e.get('sensitive', False) for e in snap['elements']), 3)

    def test_snapshot_bounds_tree_by_count_and_depth(self):
        leaf = Control('Too deep', 'Text', 899)
        for i in range(8):
            leaf = Control('Level ' + str(i), 'Pane', 800 + i, [leaf])
        self.root.nodes = [leaf]
        deep = self.observe()
        self.assertNotIn('Too deep', [e['name'] for e in deep['elements']])
        self.assertTrue(deep['truncated'])
        self.root.nodes = [Control('Button ' + str(i), rid=i + 1000) for i in range(150)]
        wide = self.observe()
        self.assertLessEqual(len(wide['elements']), 80)
        self.assertTrue(wide['truncated'])
        self.assertLessEqual(sum(c.children_reads for c in self.root.nodes), 79)

    def test_title_selection_is_exact_and_ambiguous_titles_are_refused(self):
        self.windows.append(Control('Notes extra', 'Window', 101, handle=901))
        self.assertEqual(self.adapter.observe('Notes')['title'], 'Notes')
        self.windows.append(Control('Notes', 'Window', 102, handle=902))
        with self.assertRaisesRegex(ToolError, 'ambiguous'):
            self.adapter.observe('Notes')
        with self.assertRaises(ToolError):
            self.adapter.observe('Note')

    def test_approval_context_contains_application_control_action_and_value(self):
        snap = self.observe()
        args = {**self.args(snap, 'Message'), 'text': 'review this value'}
        context = self.adapter.action_context('desktop_fill', args)
        self.assertEqual(context['title'], 'Notes')
        self.assertEqual(context['label'], 'Message')
        self.assertEqual(context['value'], 'review this value')
        self.assertTrue(context['action'])


if __name__ == '__main__':
    unittest.main()
