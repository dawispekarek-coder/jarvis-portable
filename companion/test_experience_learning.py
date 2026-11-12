import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import experience_learning as l
import adaptive_research as a
from page_reader import PageUnavailable

class ExperienceTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(prefix='learnv2_')
  self.p=patch.object(l,'DB',Path(self.t.name)/'experiences.sqlite');self.p.start()
 def tearDown(self):self.p.stop();self.t.cleanup()
 def test_unverified_outcome_does_not_train(self):
  self.assertFalse(l.observe_url('https://lua.org/manual','read_public_page',True,False))
  self.assertFalse(l.observe_url('http://localhost/private','read_public_page',True,True))
  self.assertEqual(l.summary()['verified_observations'],0)
 def test_verified_outcomes_change_strategy(self):
  fail='https://blocked.example/a';good='https://lua.org/manual'
  for _ in range(4):l.observe_url(fail,'read_public_page',False,True)
  for _ in range(4):l.observe_url(good,'read_public_page',True,True)
  items=[{'url':fail,'title':'bad'},{'url':good,'title':'good'},{'url':'https://novel.example/new','title':'new'}]
  ordered=l.order_sources(items)
  self.assertEqual(ordered[0]['url'],good)
  self.assertEqual(l.summary()['verified_observations'],8)
  self.assertEqual(l.summary()['observed_domains'],2)
 def test_learns_from_actual_reader_only(self):
  link={'url':'https://lua.org/manual/5.1/','title':'Lua official'}
  good={'url':link['url'],'title':'Lua official','excerpt':'Lua 5.1 manual discusses standard library and gsub. '*5}
  def finder(q):return {'provider':'test','results':[link]}
  observed=a.research('Lua 5.1',searcher=finder,reader=lambda x:good)
  self.assertEqual(observed['evidence_level'],2)
  self.assertEqual(l.summary()['successful_reads'],1)
  def error(x):raise PageUnavailable('offline')
  failed=a.research('Lua 5.1',searcher=finder,reader=error)
  self.assertEqual(failed['evidence_level'],1)
  self.assertEqual(l.summary()['failed_reads'],1)
if __name__=='__main__':unittest.main()