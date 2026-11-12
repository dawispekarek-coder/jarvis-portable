"""Real source-driven code backlog; never create speculative tasks."""
import json, tempfile, unittest
from pathlib import Path
from DevinBridge.route_metric_issues import discover_route_metrics

REAL = Path(r'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge\autonomy_scope\workspaces\foreverroute-route-audit\tools\route_recalc_results_20261111.json')

class RouteMetricIssuesTests(unittest.TestCase):
 def test_actual_728_routes_give_three_code_not_docs_tasks(self):
  issues=discover_route_metrics(REAL)
  self.assertEqual(len(issues),3)
  self.assertEqual({i['detail_rows'] for i in issues},{18,41,26190})
  for issue in issues:
   self.assertEqual(issue['kind'],'test-add')
   self.assertTrue(any(a['type']=='test' for a in issue['acceptance']))
   self.assertTrue(any(a['type']=='file_exists' and a['path'].startswith('tools/') for a in issue['acceptance']))
   self.assertFalse(any(x.startswith('DB/') for x in issue['allowed_paths']))
 def test_zero_metrics_produce_zero_new_tasks(self):
  data=json.loads(REAL.read_text())
  data['totals']['gateInversions']=0
  data['gateInversionDetail']=[]
  data['totals']['authoredViolations']['final']=data['totals']['authoredViolations']['authored']
  data['totals']['ungroundedRows']=0
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'snapshot.json';p.write_text(json.dumps(data))
   self.assertEqual(discover_route_metrics(p),[])
 def test_invalid_report_is_not_trusted(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'snapshot.json';p.write_text('{"tool":"wrong","schemaVersion":1,"sections":728,"totals":{"gateInversions":18}}')
   self.assertEqual(discover_route_metrics(p),[])