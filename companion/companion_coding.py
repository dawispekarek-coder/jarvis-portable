"""Model-authored Lua proposals in a private workspace. Never applies production patches."""
from pathlib import Path
import difflib,hashlib,subprocess,json
from companion_tools import confined,read_project
from companion_registry import ToolError

def create_proposal(repo,out,path,old,new,lua=None):
 if Path(path).suffix.lower()!='.lua':raise ToolError('lua_only')
 source=confined(repo,path)
 if not isinstance(old,str) or not old or not isinstance(new,str) or len(new)>30000:raise ToolError('invalid_replacement')
 raw=source.read_bytes();before=raw.decode('utf-8-sig').replace('\r\n','\n')
 if len(raw)>450000 or before.count(old)!=1 or old==new:raise ToolError('replacement_must_match_once_and_change_source')
 candidate_text=before.replace(old,new,1);out=Path(out);target=confined(out/'candidate',path);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(candidate_text.encode('utf-8'))
 patch=out/'proposal.patch';patch.write_text(''.join(difflib.unified_diff(before.splitlines(True),candidate_text.splitlines(True),fromfile='a/'+path,tofile='b/'+path)),encoding='utf-8')
 syntax=False
 if lua and Path(lua).is_file():
  run=subprocess.run([str(lua),'-e','assert(loadfile([['+str(target)+']]))'],capture_output=True,timeout=15)
  syntax=run.returncode==0
 unchanged=source.read_bytes()==raw
 if not unchanged:raise ToolError('source_changed_during_proposal')
 return {'candidate':str(target),'patch':str(patch),'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'production_modified':False,'syntax_verified':syntax,'behavior_verified':False,'verified':target.read_text(encoding='utf-8')==candidate_text and bool(patch.stat().st_size),'scope':'Private proposal only. A behavioral regression test and review are still required.'}
