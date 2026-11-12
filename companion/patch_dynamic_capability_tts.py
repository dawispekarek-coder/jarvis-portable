from pathlib import Path
import shutil
p=Path("H:/RealJarvis/V2Sandbox/BrainCore/capability_inventory.py")
s=p.read_text(encoding="utf-8-sig")
old=s
s=s.replace('V2 má vlastní hlasové rozhraní nezapojené. Starší JARVIS má samostatnou hlasovou službu.','V2 má TTS API, jeho aktuální propojení ověřuji podle dostupnosti backendu.')
s=s.replace('def inventory(probe=True):\n return',"""def tts_bridge_wired():
 try:
  src=(BASE/"ui_compat.py").read_text(encoding="utf-8-sig")
  return "@app.post('/api/tts')" in src and "_voice_backend" in src
 except OSError:return False
def inventory(probe=True):
 speech=voice_backend() if probe else {"reachable":None,"ready":None}
 return""")
s=s.replace('  "tts_connected_to_v2":False,\n  "tts_external_service":voice_backend() if probe else {"reachable":None,"ready":None},','  "tts_connected_to_v2":bool(tts_bridge_wired() and speech.get("ready")),\n  "tts_api_configured":tts_bridge_wired(),\n  "tts_external_service":speech,')
s=s.replace(' if which=="all":\n  return',""" if which=="all":
  if state["tts_connected_to_v2"]:
   state["features"]["tts"]["detail"]="TTS API je propojené s dostupným hlasovým backendem. Přehrávání zpráv závisí na nastavení UI."
  return""")
s=s.replace('  return addon+"V JARVIS 2.0 ale TTS zatím NENÍ propojeno do konverzace. Nemohu tvrdit, že tato odpověď zazní nahlas."','  if state["tts_connected_to_v2"]:\n   return addon+"TTS API v JARVIS 2.0 je propojené. Samotné hlasité přehrání zprávy závisí na nastavení rozhraní."\n  return addon+"Funkční propojení TTS do V2 rozhraní nyní není ověřené."')
s=s.replace(' TTS V2 není připojeno. Nikdy si nevymýšlej dostupnost zařízení nebo provedené akce.',' TTS API může být propojené, jeho dostupnost vždy ověř z aktuálního stavu. Nepředstírej automatické přehrávání. Nikdy si nevymýšlej dostupnost zařízení nebo provedené akce.')
if s==old:raise SystemExit("unchanged")
compile(s,str(p),"exec")
backup=p.with_name("capability_inventory.py.before_live_tts_20261027.bak")
if backup.exists():raise SystemExit("backup exists")
shutil.copy2(p,backup)
p.write_text(s,encoding="utf-8")
print("CAPABILITY_LIVE_TTS_PATCHED")
