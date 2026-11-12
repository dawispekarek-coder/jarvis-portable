import unittest
from unittest.mock import patch
import internet_access as i

class ConnectivityTests(unittest.TestCase):
 def test_real_phrases(self):
  for prompt in ('napoj se na internet','Připoj se k internetu','Jarvisi, zapni internet','zprovozni internet','Prosím připoj se na internet'):
   self.assertEqual(i.intent(prompt),'connect',prompt)
  for prompt in ('máš internet?','zkontroluj internet','otestuj internet'):
   self.assertEqual(i.intent(prompt),'check',prompt)
  for prompt in ('Ahoj','Najdi na internetu Lua','otevři prohlížeč'):
   self.assertIsNone(i.intent(prompt),prompt)
 def test_online_never_changes_network(self):
  probe=lambda:{'connected':True,'dns_ok':True,'https_ok':True,'reason':'ok'}
  def no_reconnect():raise AssertionError('unnecessary network change')
  x=i.check_or_connect('connect',probe,no_reconnect,lambda:True)
  self.assertTrue(x['connected'])
  self.assertTrue(x['web_search_ready'])
  self.assertFalse(x['reconnect_attempted'])
  self.assertIn('ověřený',i.format_result(x))
 def test_offline_one_reconnect_followed_by_verification(self):
  results=iter([{'connected':False,'reason':'dns_unavailable'},
                {'connected':True,'reason':'ok','https_ok':True}])
  x=i.check_or_connect('connect',lambda:next(results),lambda:'requested',lambda:True)
  self.assertTrue(x['connected'])
  self.assertTrue(x['reconnect_attempted'])
  self.assertEqual(x['reconnect_result'],'requested')
 def test_offline_check_only_does_not_reconnect(self):
  x=i.check_or_connect('check',lambda:{'connected':False,'reason':'dns_unavailable'},
                       lambda:1/0,lambda:True)
  self.assertFalse(x['reconnect_attempted'])
  self.assertFalse(x['connected'])
 def test_cannot_choose_between_multiple_wifi_profiles(self):
  with patch('internet_access.wifi_saved_profiles',return_value=['HomeA','HomeB']):
   with patch('internet_access.subprocess.run') as runner:
    self.assertEqual(i.reconnect_saved_wifi(),'no_unique_saved_wifi')
    runner.assert_not_called()
 def test_reconnect_only_uses_stored_profile_no_shell(self):
  from types import SimpleNamespace
  with patch('internet_access.wifi_saved_profiles',return_value=['SavedWiFi']):
   with patch('internet_access.subprocess.run',return_value=SimpleNamespace(returncode=0)) as run:
    self.assertEqual(i.reconnect_saved_wifi(),'requested')
    args=run.call_args.args[0]
    self.assertEqual(args,['netsh','wlan','connect','name=SavedWiFi'])
    self.assertFalse(run.call_args.kwargs.get('shell',False))
if __name__=='__main__':unittest.main()