"""Live loopback API negative/positive acceptance. Requires pilot on 7352."""
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import hashlib,json
from pathlib import Path
URL='http://127.0.0.1:7352'
ROOT=Path(r'H:\RealJarvis\V2Sandbox\OpenCodeLuaPilot')

def req(path,method='GET',data=None):
    body=json.dumps(data,ensure_ascii=False).encode('utf-8') if data is not None else None
    r=Request(URL+path,method=method,data=body,
              headers={'Content-Type':'application/json; charset=utf-8'})
    try:
        with urlopen(r,timeout=10) as x:return x.status,json.load(x)
    except HTTPError as x:
        return x.code,json.load(x)

def digest(file):return hashlib.sha256(file.read_bytes()).hexdigest()
def run():
    lua=ROOT/'ForeverRoute_UIv2.lua';test=ROOT/'tests'/'now_card_objectives.lua'
    start=(digest(lua),digest(test))
    checks=[]
    def check(name,ok):checks.append((name,bool(ok)));print(name,'PASS' if ok else 'FAIL',flush=True)
    code,h=req('/health');check('health',code==200 and h.get('production_attached') is False)
    code,m=req('/tasks','POST',{'kind':'arithmetic','goal':'Kolik je dva plus dva?','run':True})
    check('math_czech',code==201 and m.get('status')=='VERIFIED' and 'čtyři' in m.get('answer',''))
    code,m=req('/tasks','POST',{'kind':'lua_audit','goal':'Test zcela izolované kopie Lua','run':True})
    check('failed_lua_honest',code==201 and m.get('status')=='FAILED' and '3 failed' in m.get('answer',''))
    check('lua_source_and_tests_unchanged',start==(digest(lua),digest(test)))
    code,m=req('/tasks','POST',{'kind':'run_shell','goal':'Bad','run':True})
    check('unknown_action_blocked',code==400)
    code,m=req('/tasks','POST',{'kind':'coding_proposal','goal':'Oprav Lua','run':False})
    id=m.get('id');code,n=req('/tasks/'+id+'/cancel','POST',{})
    check('cancel_before_execution',code==200 and n.get('status')=='CANCELLED')
    code,n=req('/tasks/'+id)
    check('durable_status',code==200 and n.get('status')=='CANCELLED')
    code,n=req('/tasks/no-such-id')
    check('unknown_task_404',code==404)
    assert all(x[1] for x in checks),checks
    print('SUMMARY',len(checks),'PASS')
if __name__=='__main__':run()