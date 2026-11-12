import tempfile, unittest
from pathlib import Path
from companion_agent import known_call, goal_contract
try:
    from companion_krita import KritaAdapter, validate_svg, safe_name
except ImportError:
    KritaAdapter = None

class DrawingTests(unittest.TestCase):
    def test_new_drawing_tools_exist(self):
        self.assertIsNotNone(KritaAdapter, 'Real Krita drawing adapter is missing')

    def test_draw_request_is_not_old_video_audit(self):
        goal = 'Nakresli Lali a Pooli podle predlohy kvalitne, zadne orezy, potom animace'
        result = known_call(goal, {'krita_drawing_brief', 'godot_2d_production_quality_audit'})
        self.assertEqual(result['name'] if result else None, 'krita_drawing_brief')
        self.assertIn('krita_drawing_brief', goal_contract(goal)['required'])

    def test_svg_and_path_boundaries(self):
        self.assertIsNotNone(KritaAdapter, 'Real Krita drawing adapter is missing')
        validate_svg('<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 1 L9 9"/></svg>')
        for svg in ('<svg><image href="ref.png"/></svg>', '<svg><script/></svg>',
                    '<!DOCTYPE svg><svg/>', '<svg><use href="https://x"/></svg>'):
            with self.assertRaises(ValueError): validate_svg(svg)
        for name in ('../old', 'a/b', 'C:\\x', '', 'x.png'):
            with self.assertRaises(ValueError): safe_name(name)

    def test_export_only_confined_new_drawings(self):
        self.assertIsNotNone(KritaAdapter, 'Real Krita drawing adapter is missing')
        with tempfile.TemporaryDirectory() as tmp:
            a = KritaAdapter(Path(tmp))
            with self.assertRaises(ValueError): a.open_drawing('../reference')
            with self.assertRaises(ValueError): a.import_godot('../reference')
            with self.assertRaises(ValueError): a.paint_svg('<svg><image href="old.png"/></svg>', 'old')

    def test_disconnected_krita_does_not_report_success(self):
        self.assertIsNotNone(KritaAdapter, 'Real Krita drawing adapter is missing')
        with tempfile.TemporaryDirectory() as tmp:
            a=KritaAdapter(Path(tmp), url='http://127.0.0.1:1')
            self.assertFalse(a.status()['verified'])

if __name__=='__main__': unittest.main()
