"""Actual existing WanGP video production state; no claims of finished reels."""
from pathlib import Path
import json
ROOT=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\studio_library')
PROJECT=ROOT/'production_pipeline'
PILOT=PROJECT/'pilot_pooli_20261029'
MISSION=ROOT.parent/'training'/'JARVIS_ANIMATOR_MISSION.md'
RESEARCH=PROJECT/'AUTONOMNI_REELS_RESEARCH_20261029.md'

def status():
 from companion_character_database import status as dbstatus, plan
 v=dbstatus();p=plan('pooli','wave')
 videos=sorted(PILOT.glob('*.mp4'),key=lambda a:a.stat().st_mtime,reverse=True)
 qa=sorted(PILOT.glob('*.qa.json'),key=lambda a:a.stat().st_mtime,reverse=True)
 review=json.loads(qa[0].read_text(encoding='utf-8')) if qa else None
 first=json.loads((PILOT/'pilot_manifest.json').read_text(encoding='utf-8')) if (PILOT/'pilot_manifest.json').is_file() else {}
 diagnostic=json.loads((PILOT/'anchor_S_diagnostic_manifest.json').read_text(encoding='utf-8')) if (PILOT/'anchor_S_diagnostic_manifest.json').is_file() else {}
 refinement=json.loads((PILOT/'screenright_refinement_manifest.json').read_text(encoding='utf-8')) if (PILOT/'screenright_refinement_manifest.json').is_file() else {}
 return {'verified':bool(v.get('verified')),'character_database_assets':v.get('assets'),
 'approved_pooli_refs':[r['id'] for r in p.get('references',[])],
 'production_mission':str(MISSION),'research':str(RESEARCH),
 'production_method':'whole-frame WanGP Fun InP 1.3B / VACE 1.3B, no Godot or cutout puppet',
 'pilot_directory':str(PILOT),'pilot_video':str(videos[0]) if videos else None,
 'pilot_status':first.get('status','NOT_PREPARED'),'pilot_quality_rejected':str(first.get('status','')).startswith('REJECTED'),
 'diagnostic_status':diagnostic.get('status','NOT_STARTED'),'diagnostic_job_id':diagnostic.get('job_id'),
 'refinement_status':refinement.get('status','NOT_STARTED'),'next_animation_step':'Use VACE with properly verified image-relative right-paw motion guide. Old doorway-scene mask must not be reused.',
 'technical_review':review,'first_pilot_qa_findings':first.get('qa_findings',[]),'published':False,'quality_approved':False,
 'next_step':'Inspect actual generated video at multiple timestamps, check full-body acting and identity before proceeding to a second linked shot.'}