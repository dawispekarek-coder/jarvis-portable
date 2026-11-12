"""All companion state belongs to this checkout; production project stays read-only."""
import os,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'BrainCore'
STATE=BASE/'companion.sqlite'
ARTIFACTS=ROOT/'CompanionArtifacts'
REPO=Path(r'H:\RealJarvis\AgentTeam\ForeverRouteDev')
MODEL='qwen3.5:4b-q4_K_M'
# Local Ollama listens on 11435 on this machine (11434 is dead). Env
# override keeps this configurable without code edits.
OLLAMA=os.environ.get('COMPANION_OLLAMA','http://127.0.0.1:11435/api/chat')
# Devin primary brain for plain conversation (local ACP agent, swe-2-high).
# Set COMPANION_DEVIN_PRIMARY=0 to fall back to Ollama-only answers.
DEVIN_PRIMARY=os.environ.get('COMPANION_DEVIN_PRIMARY','1')=='1'
PORT=7430
VERSION='2.1-autonomy-20261027'
def build_id():
 h=hashlib.sha256()
 for p in sorted(BASE.glob('companion_*.py')):
  if p.name=='companion_live_verify.py':continue
  h.update(p.name.encode());h.update(p.read_bytes())
 for p in sorted(BASE.glob('companion_*.js')):h.update(p.read_bytes())
 return VERSION+'-'+h.hexdigest()[:12]
