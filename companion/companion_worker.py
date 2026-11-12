"""One independent worker daemon. Browser/UI disconnects do not cancel accepted work."""
from __future__ import annotations
import os,sys,time,uuid,subprocess,json
from pathlib import Path
from companion_store import Store,TERMINAL

class Worker:
 def __init__(self,store,command=None,root=None,max_seconds=300):
  self.store=store;self.owner=str(uuid.uuid4());self.root=Path(root or __file__).resolve()
  if self.root.is_file():self.root=self.root.parent
  self.command=command or (lambda task:[sys.executable,str(Path(__file__).with_name('companion_job.py')),task['id'],'--db',str(store.path)])
  self.max_seconds=max_seconds;self.process=None;self.active=None;self.started=0;self.log=None
 def acquire(self):return self.store.service_lease('worker',self.owner,15)
 def stop_owned(self):
  if self.process and self.process.poll() is None:
   try:
    import psutil
    parent=psutil.Process(self.process.pid)
    for child in reversed(parent.children(recursive=True)):
     try:child.kill()
     except psutil.Error:pass
   except (ImportError,Exception):pass
   self.process.kill()
   try:self.process.wait(timeout=4)
   except subprocess.TimeoutExpired:pass
 def close(self):
  self.stop_owned()
  if self.log:self.log.close();self.log=None
  if self.active:self.store.heartbeat(self.active['id'],self.active['owner'],-1)
  with self.store.db() as cx:cx.execute('UPDATE service_leases SET expires=0 WHERE name=? AND owner=?',('worker',self.owner))
 def step(self):
  if not self.acquire():return False
  if self.process:
   task=self.store.get(self.active['id'])
   if task['status']=='CANCELLED':self.stop_owned()
   elif task['status']=='WAITING_APPROVAL':self.started=time.time()
   elif task['status']=='QUEUED' and task.get('pending'):
    self.store.activate_approved(task['id'],self.active['owner']);self.started=time.time()
   elif time.time()-self.started>self.max_seconds:
    self.stop_owned();self.store.heartbeat(task['id'],self.active['owner'],-1);self.store.recover()
   else:self.store.heartbeat(task['id'],self.active['owner'],30)
   if self.process.poll() is None:return True
   if self.store.get(task['id'])['status']=='RUNNING':self.store.heartbeat(task['id'],self.active['owner'],-1)
   if self.log:self.log.close();self.log=None
   self.process=None;self.active=None
  self.store.recover();self.store.tick()
  task=self.store.claim(self.owner,30)
  if not task:return True
  self.active=task;self.started=time.time()
  folder=self.root/'job_logs';folder.mkdir(parents=True,exist_ok=True)
  self.log=(folder/(task['id']+'.log')).open('ab')
  env={**os.environ,'PYTHONUTF8':'1','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2'}
  flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
  try:
   self.process=subprocess.Popen(self.command(task),cwd=self.root,env=env,stdin=subprocess.DEVNULL,stdout=self.log,stderr=subprocess.STDOUT,creationflags=flags)
   try:
    import psutil
    psutil.Process(self.process.pid).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name=='nt' else 10)
   except Exception:pass
  except OSError as exc:
   self.store.finish(task['id'],'FAILED','Pracovní proces se nepodařilo spustit: '+type(exc).__name__,token=task['owner'])
   self.active=None;self.log.close();self.log=None
  return True

def ensure_worker(settings):
 store=Store(settings.STATE)
 if store.service_status('worker')['alive']:return False
 flags=(subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0
 subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--serve'],cwd=Path(__file__).parent,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags,start_new_session=os.name!='nt')
 return True

def main():
 import companion_settings as settings
 worker=Worker(Store(settings.STATE),root=settings.BASE)
 build=settings.build_id();worker.owner=build+'|'+worker.owner;checked=time.time()
 try:
  while worker.step():
   if time.time()-checked>5:
    checked=time.time()
    if worker.process is None and settings.build_id()!=build:break
   time.sleep(.35)
 finally:worker.close()

if __name__=='__main__':main()
