"""Trusted local test evidence for ongoing ForeverRoute CDP planning."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BRIDGE=Path(r'C:\Users\Dawis\ForeverRouteJarvis\DevinBridge')
ROOT=BRIDGE/'autonomy_scope'/'workspaces'/'foreverroute-route-audit'
TEST='test_route_nav_evidence_audit.py'
OUTPUT=ROOT/'tools'/'nav_regression_results.json'
assert (ROOT/'.git').exists() and (ROOT/'tests'/TEST).is_file()
command=[sys.executable,'-B','-m','unittest','discover','-s','tests','-p',TEST]
try:
 result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=90)
 passed=result.returncode==0
 detail=(result.stdout+'\n'+result.stderr)[-2000:]
except subprocess.TimeoutExpired:
 passed=False
 detail='NAV_EVIDENCE_TEST_TIMEOUT: unittest exceeded 90 seconds'
report={'generated_at':datetime.now(timezone.utc).isoformat(),
        'source':'trusted local static-test runner',
        'tests':[{'name':'route_nav_evidence_suite','ok':passed,
                  'error':detail if not passed else '',
                  'path':'tools',
                  'rerun':'python -m unittest discover -s tests -p '+TEST}]}
temp=OUTPUT.with_suffix('.json.tmp')
temp.write_text(json.dumps(report,indent=2),encoding='utf-8')
os.replace(temp,OUTPUT)
print('NAV_TEST_PROOF', 'PASS' if passed else 'FAIL',len(detail))
