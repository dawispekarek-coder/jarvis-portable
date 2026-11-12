"""Owner-approved ordering: complete verified Hyjal + source waypoint overlay before final 56x13 recalculation."""
from DevinBridge.daemon import make_coordinator, load_config
from DevinBridge.coordinator import utcnow
c=make_coordinator(load_config())
target="FR-LIVE-20261111-04"
deps=["FR-HYJAL-20261111-02","FR-LIVE-20261111-03"]
for dep in deps:
    t=c.get_task(dep)
    assert t and t.get('scope')=='production', ('missing prerequisite',dep)
before=c.get_task(target)
assert before.get('status') in ('PENDING','READY'), ('recalc active: cannot safely change deps',before.get('status'))
def update(t):
    if t['status'] not in ('PENDING','READY'): raise RuntimeError('recalc no longer idle')
    t['depends_on']=deps[:]
    t['priority']=20
    if t['status']=='READY':
        t.setdefault('history',[]).append(dict(ts=utcnow(), **{'from':'READY','to':'PENDING'},reason='Owner: complete verified Hyjal and waypoint integration before route recalculation'))
        t['status']='PENDING'
r=c._mutate(target,update)
assert r['ok'], r
c._event('owner_priority_gate',task_id=target,depends_on=deps,reason='Hyjal + waypoints before full route recalc')
print('UPDATED',target,'STATUS',r['task']['status'],'DEPENDS',','.join(r['task']['depends_on']))
for task_id in ['FR-HYJAL-20261111-01','FR-HYJAL-20261111-02','FR-LIVE-20261111-03',target]:
    t=c.get_task(task_id);print(task_id,t['status'],'deps=',t.get('depends_on'))

