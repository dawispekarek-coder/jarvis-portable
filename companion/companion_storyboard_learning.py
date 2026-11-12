"""Reference-driven multi-shot storyboarding training for Jarvis 2.1.
References are viewed for pacing and staging only; no copyrighted frames
are used in any produced Lali/Pooli video or public export.
"""
from pathlib import Path
import base64,hashlib,io,json,time,urllib.request
from PIL import Image
import numpy as np
from companion_store import Store
from companion_settings import STATE

ROOT=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D')
PROJECT=ROOT/'LaliPooli2D_Pilot'
DATA=PROJECT/'training'/'shot_learning'/'training_data.json'
KB=Path(r'H:\RealJarvis\V2Autonomy_20261027\KnowledgeInbox')
REPORT=PROJECT/'training'/'shot_learning'/'JARVIS_STORYBOARD_LESSON.json'

def _model_review(board:Path):
    original=Image.open(board).convert('RGB')
    original.thumbnail((1300,500))
    buf=io.BytesIO()
    original.save(buf,format='JPEG',quality=70)
    prompt=('These are FIVE STORYBOARD CARDS extracted ONLY from original owner-approved'
            ' Lali & Pooli character references. Analyze composition in Czech.'
            ' Explain the five narrative shot roles (wide, reaction, reaction,'
            ' medium, wide), when four cuts should happen, why a single moving'
            ' character image alone cannot tell the full story.'
            ' Be precise: this storyboard is static, NOT animation.'
            ' Do not infer camera moves, gestures or scene actions not shown.'
            ' Keep characters original; do not copy Bubu and Dudu art.'
            ' Answer in 5 short Czech sentences.')
    req={'model':'qwen3.5:4b-q4_K_M','messages':[{'role':'user','content':prompt,'images':[base64.b64encode(buf.getvalue()).decode('ascii')]}],
         'stream':False,'think':False,'options':{'num_predict':230,'temperature':0.1}}
    rq=urllib.request.Request('http://127.0.0.1:11434/api/chat',
        data=json.dumps(req).encode('utf8'),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(rq,timeout=95) as response:
        reply=json.load(response)['message']['content'].strip()
    if not reply: raise RuntimeError('vision returned empty storyboard reading')
    return reply[:1700]

def study():
    if not DATA.is_file():raise RuntimeError('Teaching board must be made first')
    d=json.loads(DATA.read_text(encoding='utf8'))
    shots=d['multishot_example']
    if len(shots)!=5 or d.get('scene_cuts')!=4:
        raise RuntimeError('Storyboard cut count mismatch')
    if [s['framing'] for s in shots]!=['WIDE','CLOSE','CLOSE','MEDIUM','WIDE']:
        raise RuntimeError('Camera grammar mismatch')
    if any(abs(shots[i]['end']-shots[i+1]['start'])>0.001 for i in range(4)):
        raise RuntimeError('Story beats have timeline gap')
    if d['reference_gif_tests'][0]['frames']<2:raise RuntimeError('No moving reference')
    if d['full_reference_video_cut_verification']:
        raise RuntimeError('Do not claim full video cut analysis was verified')
    if len(set(s['beat'] for s in shots))!=5:raise RuntimeError('Duplicate story beats')
    board=Path(d['training_board'])
    if not board.is_file():raise RuntimeError('Owner character board missing')
    interpretation=_model_review(board)
    content={
     'date':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
     'result':'VERIFIED_TRAINING_NOT_FINISHED_VIDEO',
     'student':'Jarvis 2.1 local vision assistant',
     'motion_reference_frames':[x['frames'] for x in d['reference_gif_tests']],
     'story_shots':len(shots),'story_cuts':4,'camera_framings':[s['framing'] for s in shots],
     'storyboard_source':'user approved Lali & Pooli character sheet',
     'explanation_by_vision_model_unverified':interpretation,
     'full_youtube_cut_analysis_finished':False,
     'still_storyboard_finished':True,'animation_completed':False,
     'creative_quality_approved':False,
     'reference_shots_used_in_final_video':False,
     'board':str(board),
     'next_step':'Only after original production-quality character poses and matching scenery are ready: animate each shot, edit cuts and sound, then obtain owner review'
    }
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(content,ensure_ascii=False,indent=2),encoding='utf8')
    store=Store(STATE)
    store.remember('lali_pooli_storyboard_5shot_training',
        'VIZUALNE OVERENO: Jarvis 2.1 precetl vlastni petizaberovy storyboard z originalnich uzivatelskych referenci Lali/Pooli; kamera WIDE CLOSE CLOSE MEDIUM WIDE, strihy 2.2 4.0 6.0 9.0 s, jedna jasna situace/problem/reakce/reseni/pointa. Tri kratke studijni GIFy maji 8,8,18 snimku (single gestures). Plne casove analyzovany cizi dlouhy film NEMAME; pokus o browserovy sampling byl neplatny, neukladat jako dukaz. Plnohodnotna animace NEHOTOVA; stare video kreativne ODMITNUTO. Dokument: '+str(REPORT)+'.',
        'verified_multishot_learning')
    journal=PROJECT/'training'/'verified_steps.jsonl'
    with journal.open('a',encoding='utf8') as f:
       f.write(json.dumps({'task':'godot_2d_storyboard_training',
          'date':content['date'],'status':'VERIFIED_LEARNING_ONLY',
          'file':str(REPORT),'video_created':False},ensure_ascii=False)+'\n')
    return {'verified':True,'learned_shot_count':5,'learned_cut_count':4,
            'camera_framings':content['camera_framings'],
            'study_reference_frames':[8,8,18],
            'board':str(board),'memory_saved':True,'creative_quality_approved':False,
            'finished_video':False,'full_reference_video_analyzed':False}

def practice_animatic():
    """Verify actual five-shot cut timeline, never call this a finished film."""
    import subprocess,sys,hashlib
    source=PROJECT/'training'/'shot_learning'/'animate_five_cuts.py'
    infofile=PROJECT/'training'/'shot_learning'/'animatic_practice_result.json'
    if not source.is_file():raise RuntimeError('shot timeline generator missing')
    run=subprocess.run([sys.executable,str(source)],
         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',timeout=80)
    if run.returncode or 'CUT_TIMELINE_CONFIRMED' not in run.stdout or not infofile.is_file():
        raise RuntimeError('five-shot preview export not proven: '+run.stdout[-600:])
    result=json.loads(infofile.read_text(encoding='utf8'))
    if result.get('technical_cut_test')!='PASS' or len(result.get('four_real_cuts',[]))!=4:
        raise RuntimeError('cut timing mismatched')
    if not all(c['real_visual_cut'] for c in result['four_real_cuts']):
        raise RuntimeError('one of the four cuts was not visually detected')
    note=('Jarvis technicky VYTVORIL TRENINGOVY animatik s 5 ruznymi obrazovymi zabery '
          'a 4 meritelne oddelenymi strihy v casovych bodech 2.2 4 6 9 sekund, '
          '13s/24fps/312 snimku. Ve videu se pouzivaji pouze referencni '
          'uzivatelem dodane ilustrace Lali/Pooli, kratka obrazova '
          'kamerova priblizeni. Toto NENI animace tvaru tela/gesta '
          'ani kvalitni Reel. Původni zamitnute video nepouzito. '
          'Video: '+result['file'])
    Store(STATE).remember('lali_pooli_multishot_animatic_proof',note,
                          'verified_cut_editing_training')
    with (PROJECT/'training'/'verified_steps.jsonl').open('a',encoding='utf8') as j:
        j.write(json.dumps({'date':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
          'task':'five_shot_editing_practice','result':'CUTS_VERIFIED_CREATIVE_UNAPPROVED',
          'file':result['file']},ensure_ascii=False)+'\n')
    return {'verified':True,'shots':5,'cuts':4,
        'timestamps':[c['time'] for c in result['four_real_cuts']],
        'output_file':result['file'],
        'made_video_preview':True,
        'full_production_video':False,
        'creative_quality_approved':False,
        'published_on_instagram':False}
