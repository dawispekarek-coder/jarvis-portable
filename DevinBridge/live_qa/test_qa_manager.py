"""Hermetic QA swap/rollback regression: never touches actual WoW."""
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import qa_manager as q

class QADeployTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.addCleanup(self.tmp.cleanup)
  self.base=Path(self.tmp.name)
  self.wow=self.base/'WoW';self.addons=self.wow/'Interface'/'AddOns'
  self.addons.mkdir(parents=True)
  self.live=self.addons/'ForeverRoute'
  self.live.mkdir()
  (self.live/'ForeverRoute.toc').write_text('## Interface: 16001\nCore.lua\n')
  (self.live/'Core.lua').write_text('ORIGINAL')
  self.source=self.base/'repo';self.source.mkdir()
  (self.source/'.git').mkdir()
  (self.source/'ForeverRoute.toc').write_text('## Interface: 16001\nCore.lua\n')
  (self.source/'Core.lua').write_text('CANDIDATE')
  self.here=self.base/'qa';self.here.mkdir()
  patches=[patch.object(q,'WOW',self.wow),patch.object(q,'ADDONS',self.addons),
           patch.object(q,'LIVE',self.live),patch.object(q,'PROBE',self.addons/'ForeverRouteLiveQA'),
           patch.object(q,'SOURCE',self.source),patch.object(q,'HERE',self.here),
           patch.object(q,'STAGE',self.here/'staged'/'ForeverRoute'),
           patch.object(q,'MANIFEST',self.here/'deployment.json'),
           patch.object(q,'wow_running',lambda:False)]
  for x in patches:x.start();self.addCleanup(x.stop)
 def test_deploy_and_rollback_preserves_exact_original(self):
  orig=q.sha(self.live/'Core.lua')
  staged=q.stage_candidate()
  self.assertEqual(staged['files_in_toc'],1)
  with self.assertRaises(RuntimeError):q.deploy_candidate(False)
  activated=q.deploy_candidate(True)
  self.assertTrue(activated['active'])
  self.assertEqual((self.live/'Core.lua').read_text(),'CANDIDATE')
  restored=q.rollback()
  self.assertFalse(restored['active'])
  self.assertEqual(q.sha(self.live/'Core.lua'),orig)
  self.assertEqual(q.rollback()['state'],'ALREADY_RESTORED')
 def _clean_record(self):
  import time
  return {'state':'COMPLETE','started_at':time.time()-5,
   'protected_popup_seen':False,'qa':{
    'state':'LIVE_RESULT_RECORDED','result':'PASS','health':'OK',
    'phase':'PLAYER_LOGOUT','blocked_actions':0,'forbidden_actions':0,
    'modules_total':21,'degraded_modules':[],
    'file_mtime_epoch':time.time()}}
 def test_keep_clean_pass_preserves_backup(self):
  q.stage_candidate();m=q.deploy_candidate(True)
  done=q.keep_verified(self._clean_record())
  self.assertEqual(done['state'],'KEPT_VERIFIED')
  self.assertFalse(done['active'])
  self.assertEqual((self.live/'Core.lua').read_text(),'CANDIDATE')
  self.assertEqual((Path(done['backup'])/'Core.lua').read_text(),'ORIGINAL')
 def test_warn_or_protected_event_rolls_back_not_kept(self):
  q.stage_candidate();q.deploy_candidate(True)
  rec=self._clean_record();rec['qa']['result']='WARN'
  with self.assertRaises(RuntimeError):q.keep_verified(rec)
  rec=self._clean_record();rec['qa']['forbidden_actions']=1
  with self.assertRaises(RuntimeError):q.keep_verified(rec)
  rec=self._clean_record();rec['protected_popup_seen']=True
  with self.assertRaises(RuntimeError):q.keep_verified(rec)
  restored=q.rollback()
  self.assertEqual(restored['state'],'RESTORED')
  self.assertEqual((self.live/'Core.lua').read_text(),'ORIGINAL')
 def test_missing_toc_file_fails_closed(self):
  (self.source/'ForeverRoute.toc').write_text('Missing.lua\n')
  with self.assertRaises(RuntimeError):q.stage_candidate()
  self.assertEqual((self.live/'Core.lua').read_text(),'ORIGINAL')
 def test_refuses_swap_if_game_running(self):
  q.stage_candidate()
  with patch.object(q,'wow_running',lambda:True):
   with self.assertRaises(RuntimeError):q.deploy_candidate(True)
  self.assertEqual((self.live/'Core.lua').read_text(),'ORIGINAL')

if __name__=='__main__':unittest.main()
