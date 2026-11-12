import unittest
from unittest.mock import patch
import foreverroute_study as s
class RealSourceStudyTests(unittest.TestCase):
 def test_czech_study_command(self):
  self.assertTrue(s.intent('máš přístup k forever route, zkus to znova, nastuduj si to'))
  self.assertTrue(s.intent('Nastuduj si ForeverRoute'))
  self.assertTrue(s.intent('Co víš o ForeverRoute?'))
  self.assertFalse(s.intent('Ahoj'))
  self.assertFalse(s.intent('Oprav ForeverRoute'))
 def test_actual_repo_study(self):
  before=s.status()
  info=s.study('Nastuduj si ForeverRoute')
  self.assertTrue(info['verified'])
  self.assertTrue(info['read_only'])
  self.assertEqual(info['commit'],before['commit'])
  self.assertGreaterEqual(info['source_count'],10)
  self.assertTrue(any(x[0]=='ForeverRoute_PlannerV4.lua' and x[1]>1000 for x in info['modules']))
  report=s.format_study(info)
  self.assertIn('ForeverRoute.toc:',report)
  self.assertIn('README.md:',report)
  self.assertIn('ForeverRoute_QuestEngine.lua',report)
  after=s.status()
  self.assertEqual(before['commit'],after['commit'])
  self.assertEqual(before['changed_count'],after['changed_count'])
 def test_refuse_silent_repo_failure(self):
  with patch('foreverroute_study.status',side_effect=RuntimeError('repo_unavailable')):
   with self.assertRaises(RuntimeError):s.study()
