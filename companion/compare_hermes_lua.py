"""Alternative already-installed local model comparison. No production writes."""
import json
from pathlib import Path
import lua_coding_lab as lab
import lua_refine_pilot as refine
lab.MODEL='hermes-qwen4b:latest'
refine.REPORT=lab.ROOT/'reports'/'coding_hermes_refinement.json'
print(json.dumps(refine.run(),ensure_ascii=True)[:2800],flush=True)