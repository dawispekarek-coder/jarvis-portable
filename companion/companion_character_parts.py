"""Local Florence-2 + SAM body-part recognition for original raccoon characters.
This only recognizes visible parts. Missing limbs and final animation require a separate model and QA.
"""
from __future__ import annotations
from pathlib import Path
import json,subprocess,time
DIR=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\studio_library\character_understanding')
CMD=DIR/'run_auto_recognition.cmd'
FLORENCE=Path(r'H:\RealJarvis\OptionalPlugins\ComfyUI\models\florence2\Florence-2-base-ft\model.safetensors')
SAM=Path(r'H:\RealJarvis\OptionalPlugins\ComfyUI\models\sams\sam_vit_b_01ec64.pth')

def status():
    ready=FLORENCE.is_file() and FLORENCE.stat().st_size>460_000_000 and SAM.is_file() and SAM.stat().st_size>370_000_000
    result={'verified':True,'recognition_models_ready':ready,'detects_visible_paw_and_tail':True if ready else False,'can_reconstruct_missing_limbs':False,'can_generate_professional_animation':False,'samples':{}}
    for name in ('pooli','lali'):
        p=DIR/(name+'_SEMANTIC_PARTS.json')
        if not p.is_file():continue
        try:
            data=json.loads(p.read_text(encoding='utf-8'))
            result['samples'][name]={'mask_result':str(p),'overlay':data['review_overlay'],'parts':{k:v['bbox'] for k,v in data['parts'].items()},'visual_approval_required':True}
        except (ValueError,KeyError,OSError):result['samples'][name]={'error':'invalid_result'}
    return result

def analyze():
    if not CMD.is_file() or not status()['recognition_models_ready']:
        return {'verified':False,'status':'unavailable','reason':'Missing runner or downloaded models'}
    log=DIR/'jarvis_recognition_run.log'
    with log.open('wb') as fp:
        process=subprocess.Popen(['cmd.exe','/c',str(CMD)],cwd=str(DIR),stdout=fp,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    (DIR/'jarvis_recognition_job.json').write_text(json.dumps({'pid':process.pid,'started_at':time.time(),'status':'started','log':str(log)}),encoding='utf-8')
    return {'verified':True,'status':'started_not_finished','pid':process.pid,'log':str(log),'check_with':'character_parts_status','note':'Rechecks visible paws and tails for BOTH characters; do not claim rendering or approval'}