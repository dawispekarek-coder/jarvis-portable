"""Conservative cache-aware 24h budget with independent hard raw cap."""
import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
from DevinBridge import cdp

class CachedMeteringTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  self.root=Path(tmp.name);(self.root/'autonomy_scope').mkdir();self.wt=self.root/'workspace';self.wt.mkdir()
  grant=dict(program_id='BUDGETTEST',ongoing=True,owner_authorized=True,
    worktrees=[str(self.wt)],allowed_paths=['tools'],kinds=['analyze'],
    max_dispatches_per_hour=12,max_failures_per_24h=8,
    max_reported_tokens_per_24h=1500000,
    max_raw_reported_tokens_per_24h=3000000,cached_read_weight=0.5)
  (self.root/'autonomy_scope'/'CDP_PROGRAM.json').write_text(json.dumps(grant))
  task=dict(id='t',program_id='BUDGETTEST',status='COMPLETE',created_at=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat())
  self.coord=SimpleNamespace(root=self.root,global_holds=lambda:[],_load=lambda:{'tasks':{'t':task}})
 def check(self,total,input_,cached):
  ev=dict(kind='prompt_done',task_id='t',ts=datetime.now(timezone.utc).isoformat(),
    usage=dict(totalTokens=total,inputTokens=input_,cachedReadTokens=cached))
  (self.root/'coordinator_events.jsonl').write_text(json.dumps(ev)+'\n')
  return cdp.handoff_tick(self.coord)['reason']
 def test_cached_reads_have_conservative_half_weight(self):
  self.assertEqual(self.check(1691002,1678122,1665024),'no in-program proposal')
 def test_raw_absolute_ceiling_cannot_be_bypassed_by_cache(self):
  self.assertIn('HARD raw-token guard',self.check(3100000,3000000,2980000))
 def test_missing_input_proof_gives_no_cache_discount(self):
  self.assertIn('weighted model-usage guard',self.check(1691002,0,1665024))
 def test_explicit_owner_unlimited_usage(self):
  p=self.root/'autonomy_scope'/'CDP_PROGRAM.json'
  cfg=json.loads(p.read_text())
  cfg['max_reported_tokens_per_24h']=None
  cfg['max_raw_reported_tokens_per_24h']=None
  p.write_text(json.dumps(cfg))
  self.assertEqual(self.check(9000000,8000000,7000000),'no in-program proposal')
