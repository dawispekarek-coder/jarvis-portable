"""Lua probe simulation; NOT a substitute for actual WoW login."""
import unittest
from pathlib import Path
from lupa import LuaRuntime

SRC=(Path(__file__).parent/'ForeverRouteLiveQA'/'ForeverRouteLiveQA.lua').read_text(encoding='utf-8-sig')
BASE='''
mockFrame={}
function CreateFrame(kind)
 return {RegisterEvent=function(self,event) end,
         SetScript=function(self,key,fn) mockFrame.OnEvent=fn end}
end
function time() return 1773300000 end
C_AddOns={IsAddOnLoaded=function(name) return name=="ForeverRoute" end}
C_Timer={After=function(delay,fn) fn() end}
function GetBuildInfo() return "1.60.1","build","date",16001 end
ForeverRouteRouteService={}; ForeverRouteGuides={}; ForeverRouteStepEngine={}
'''

class ProbeLuaTests(unittest.TestCase):
 def simulate(self,diagnostic):
  lua=LuaRuntime(unpack_returned_tuples=True)
  lua.execute(BASE)
  if diagnostic:
   lua.execute(diagnostic)
  code=lua.eval('load')(SRC,'@ForeverRouteLiveQA.lua')
  if isinstance(code,tuple):raise AssertionError(str(code))
  code('ForeverRouteLiveQA')
  lua.execute('mockFrame.OnEvent(nil,"ADDON_LOADED","ForeverRouteLiveQA")')
  lua.execute('mockFrame.OnEvent(nil,"PLAYER_LOGIN")')
  lua.execute('mockFrame.OnEvent(nil,"PLAYER_ENTERING_WORLD")')
  lua.execute('mockFrame.OnEvent(nil,"PLAYER_LOGOUT")')
  return lua.globals().FRLiveQAResults['last']
 def test_no_gameplay_and_positive_probe(self):
  result=self.simulate('ForeverRouteDiagnostics={ModuleHealth=function() return {{name="Store",loaded=true,healthy=true}},0 end}')
  self.assertEqual(result['result'],'PASS')
  self.assertEqual(result['health'],'OK')
  self.assertEqual(result['phase'],'PLAYER_LOGOUT')
  self.assertTrue(result['login'] and result['world'])
 def test_forbidden_foreverroute_action_causes_fail(self):
  lua=LuaRuntime(unpack_returned_tuples=True)
  lua.execute(BASE)
  lua.execute('ForeverRouteDiagnostics={ModuleHealth=function() return {{name="Store",loaded=true,healthy=true}},0 end}')
  code=lua.eval('load')(SRC,'@ForeverRouteLiveQA.lua')
  if isinstance(code,tuple):raise AssertionError(str(code))
  code('ForeverRouteLiveQA')
  lua.execute('mockFrame.OnEvent(nil,"PLAYER_LOGIN")')
  lua.execute('mockFrame.OnEvent(nil,"PLAYER_ENTERING_WORLD")')
  lua.execute('mockFrame.OnEvent(nil,"ADDON_ACTION_FORBIDDEN","ForeverRoute","SecureFunction")')
  lua.execute('mockFrame.OnEvent(nil,"PLAYER_LOGOUT")')
  q=lua.globals().FRLiveQAResults['last']
  self.assertEqual(q['result'],'FAIL')
  self.assertEqual(q['forbiddenActions'],1)
 def test_other_addon_event_does_not_mark_foreverroute_failed(self):
  lua=LuaRuntime(unpack_returned_tuples=True)
  lua.execute(BASE)
  lua.execute('ForeverRouteDiagnostics={ModuleHealth=function() return {{name="Store",loaded=true,healthy=true}},0 end}')
  code=lua.eval('load')(SRC,'@ForeverRouteLiveQA.lua')
  if isinstance(code,tuple):raise AssertionError(str(code))
  code('ForeverRouteLiveQA')
  lua.execute('mockFrame.OnEvent(nil,"PLAYER_LOGIN")')
  lua.execute('mockFrame.OnEvent(nil,"PLAYER_ENTERING_WORLD")')
  lua.execute('mockFrame.OnEvent(nil,"ADDON_ACTION_BLOCKED","UnrelatedAddon","SecureFunction")')
  lua.execute('mockFrame.OnEvent(nil,"PLAYER_LOGOUT")')
  q=lua.globals().FRLiveQAResults['last']
  self.assertEqual(q['result'],'PASS')
  self.assertEqual(q['blockedActions'],0)
 def test_missing_diagnostics_not_a_false_pass(self):
  result=self.simulate('')
  self.assertEqual(result['result'],'FAIL')
  self.assertEqual(result['health'],'DIAGNOSTICS_MISSING')
 def test_degraded_probe_is_warning(self):
  result=self.simulate('ForeverRouteDiagnostics={ModuleHealth=function() return {{name="Navigation",loaded=false,healthy=false}},1 end}')
  self.assertEqual(result['result'],'WARN')
  self.assertEqual(result['health'],'DEGRADED')

if __name__=='__main__':unittest.main()
