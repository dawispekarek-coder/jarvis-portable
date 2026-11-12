from pathlib import Path
p=Path(r'H:\RealJarvis\V2Autonomy_20261027\BrainCore\companion_agent.py')
s=p.read_text(encoding='utf8')
if "if 'lali_pooli_autonomous_director' in used" not in s:
 marker="   self.store.finish(self.task['id'],status,answer,token=self.token)"
 assert s.count(marker)==1
 s=s.replace(marker,"   if 'lali_pooli_autonomous_director' in used and not result.get('last_result',{}).get('value',{}).get('quality_approved',False):status='PARTIAL'\n"+marker,1)
 p.write_text(s,encoding='utf8')
 print('PARTIAL_STATUS_GUARD_INSTALLED')
