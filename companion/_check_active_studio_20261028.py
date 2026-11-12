import sqlite3,companion_settings as s
cx=sqlite3.connect(str(s.STATE))
print("ALL",cx.execute("select status,count(*) from tasks group by status").fetchall())
print("ACTIVE",cx.execute("select id,status,substr(goal,1,90) from tasks where status in ('RUNNING','QUEUED','WAITING_APPROVAL') order by rowid desc limit 20").fetchall())
