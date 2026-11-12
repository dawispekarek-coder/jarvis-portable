from pathlib import Path
p=Path(r'H:\RealJarvis\V2Sandbox\BrainCore\goal_workflow.stage_20261027.py')
s=p.read_text(encoding='utf-8-sig')
assert s.count("tested=0; failed=[]; cases=[]")==1
s=s.replace("tested=0; failed=[]; cases=[]","tested=0; failed=[]; fail_count=0")
s=s.replace("nonlocal tested\n        tested+=1\n        if not passed and len(failed)<28:failed.append({'kind':kind,'utterance':utterance})",
"""nonlocal tested,fail_count
        tested+=1
        if not passed:
            fail_count+=1
            if len(failed)<28:failed.append({'kind':kind,'utterance':utterance})""")
s=s.replace("'passed':tested-(len(failed) if len(failed)<28 else 28),",
            "'passed':tested-fail_count,")
s=s.replace("'failure_examples_capped':len(failed)>=28,",
            "'failure_count':fail_count,'failure_examples_capped':fail_count>28,")
s=s.replace("if not _ACTION.match(n):\n        return None",
"""if not _ACTION.match(n) and not (n.startswith('zjisti ') and
            any(x in n for x in (' a nauc se',' a oprav',' a pouzij',' a zrealizuj'))):
        return None""")
p.write_text(s,encoding='utf-8')
print('STAGE_PATCHED')
