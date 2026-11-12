"""Godot 2D: visual observation and bounded verified learning for Lali/Pooli."""
from __future__ import annotations
from pathlib import Path
import ctypes, io, base64, json, subprocess, urllib.request, time
from PIL import Image, ImageGrab
from companion_store import Store
from companion_settings import STATE

EXE = Path(r"H:\RealJarvis\OptionalPlugins\Godot4.7.2\Godot_v4.7.2-stable_win64.exe")
PROJECT = Path(r"H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot")
REF = PROJECT / "assets" / "official_character_sheet.png"
POOLI = Path(r"H:\RealJarvis\OptionalPlugins\JarvisBlender3D\References\05_Pooli_otocka.jpg")
OBS = PROJECT.parent / "observations"

def status():
    import psutil
    tasks = [p for p in psutil.process_iter(['pid','name']) if 'godot' in (p.info.get('name') or '').lower()]
    files = [PROJECT/'project.godot', PROJECT/'scenes'/'Main.tscn', REF, POOLI]
    return {'verified':all(p.is_file() for p in files) and EXE.is_file(),
            'ready':EXE.is_file(),'project_exists':(PROJECT/'project.godot').is_file(),
            'processes':[p.pid for p in tasks],
            'reference_paths':[str(REF),str(POOLI)],
            'project':str(PROJECT),
            'real_character_rig_completed':False,'creative_quality_approved':False,'stage3_rejected_by_user':True,'official_expression_references':12,
            'independent_scene_exists':(PROJECT/'scenes'/'Stage2_Independent.tscn').is_file(),
            'scope':'Two independent full-body sprites + AnimationPlayer; no articulated limbs, no finished Reel'}

def _foreground_godot():
    import psutil
    user32=ctypes.windll.user32
    hwnd=user32.GetForegroundWindow()
    pid=ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    proc=psutil.Process(pid.value)
    if 'godot' not in proc.name().lower():
        raise RuntimeError('Godot is not foreground window: activate its preview/editor first')
    return proc.pid

def observe():
    pid=_foreground_godot()
    if not REF.is_file() or not POOLI.is_file():
        raise RuntimeError('approved user image references missing')
    OBS.mkdir(exist_ok=True,parents=True)
    snap=ImageGrab.grab(bbox=(0,0,1920,1080),all_screens=True).convert('RGB')
    stamp=str(int(time.time()))
    out=OBS/('godot_window_'+stamp+'.jpg')
    snap.save(out,quality=80)
    snap.thumbnail((1200,750))
    def b64(img):
        fp=io.BytesIO();img.save(fp,format='JPEG',quality=70)
        return base64.b64encode(fp.getvalue()).decode('ascii')
    with Image.open(POOLI) as im:
        refer=b64(im.convert('RGB'))
    prompt=('First image is a REAL CURRENT WINDOWS GODOT 2D SCREEN with the app open, '
            'second is the APPROVED LOOK of Pooli raccoon boy. '
            'Report in Czech what is visibly present. Is this the Godot editor, a playing scene, '
            'or an error? Is it one static image or a layered rig? '
            'Do NOT claim full character animation. State one safe next training task. '
            'Pooli must retain his original face and no makeup; do not invent unseen features. '
            'Max 90 Czech words.')
    payload={'model':'qwen3.5:4b-q4_K_M','messages':[{'role':'user','content':prompt,
        'images':[b64(snap),refer]}], 'stream':False,'think':False,
        'options':{'num_predict':175,'temperature':0.1,'num_ctx':4096}}
    req=urllib.request.Request('http://127.0.0.1:11434/api/chat',
       data=json.dumps(payload).encode('utf-8'),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=110) as f:
        reply=json.load(f).get('message',{}).get('content','')
    if not reply.strip(): raise RuntimeError('empty_response_from_vision_model')
    return {'verified':True,'screen_observed':True,'reference_used':True,
            'pid':pid,'screenshot':str(out),'observation':reply[:1600],
            'scope':'real Godot screenshot interpreted with local image model'}

def verify_stage2():
    """Independent objective checks: two distinct sprites and four live key tracks."""
    import hashlib
    scene=PROJECT/'scenes'/'Stage2_Independent.tscn'
    verifier=PROJECT/'training'/'verify_stage2.gd'
    if not scene.is_file() or not verifier.is_file():
        raise RuntimeError('Stage2 scene or verifier not present')
    proc=subprocess.run([str(EXE),'--headless','--verbose','--path',str(PROJECT),
                         '--script','res://training/verify_stage2.gd'],
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        text=True,timeout=35,errors='replace')
    token='STAGE2_VERIFIED independent_sprites=true independent_animation=true articulated_rig=false'
    if proc.returncode!=0 or token not in proc.stdout:
        raise RuntimeError('Stage2 did not independently verify: '+proc.stdout[-1100:])
    proof={'verified':True,'scene_path':str(scene),'animation_tracks':4,
           'independent_sprites':True,'separate_character_motion':True,
           'articulated_rig_completed':False,
           'scene_sha256':hashlib.sha256(scene.read_bytes()).hexdigest(),
           'lali_png_sha256':hashlib.sha256((PROJECT/'assets'/'sprites'/'lali_official_fullpose_cutout.png').read_bytes()).hexdigest(),
           'pooli_png_sha256':hashlib.sha256((PROJECT/'assets'/'sprites'/'pooli_official_fullpose_cutout.png').read_bytes()).hexdigest(),
           'proof_log':proc.stdout[-1500:]}
    return proof

def learn_one_step():
    if not status()['verified']:
        raise RuntimeError('Godot binary or official reference missing')
    visual=observe()
    independently_verified=verify_stage2()
    note=('OVĚŘENO: Godot 4.7.2 — dva samostatné, z oficiálního charakterového listu '
          'vyříznuté 2D sprite objekty Lali a Pooli. '
          'Čtyři animační stopy AnimationPlayer: samostatná poloha a náklon '
          'Lali i Pooli, každá mění polohu v průběhu 8sekundového cyklu. '
          'Skutečný screenshot okna pořízen, lokální obrazový model '
          'jej pouze popsal. Komentář obrazového modelu NEPOTVRZUJE identitu; '
          'rozhodující jsou uživatelem schválené obrázky. '
          'ZATÍM CHYBÍ samostatná animace hlavy, rukou a nohou (rig), '
          'video MP4 i schválený Reel. '
          'Projekt: '+str(PROJECT))
    store=Store(STATE)
    store.remember('godot_2d_visual_training',note,'verified_local_training')
    store.remember('godot_2d_independent_characters',
        'Godot Stage2: dvě samostatné Sprite2D postavy + 4 správně ověřené animační '
        'stopy: Characters/Lali:position, Characters/Pooli:position, '
        'Characters/Lali:rotation, Characters/Pooli:rotation. '
        'Sprity získány z originálního character sheetu (žádná AI překresba). '
        'Skript verify_stage2.gd, 8s perioda. '
        'Další krok: rozdělení na pohyblivé části se zachováním předlohy, '
        'vytvoření ručně ověřené kostry.','verified_local_training')
    journal=PROJECT/'training'/'verified_steps.jsonl'
    journal.parent.mkdir(parents=True,exist_ok=True)
    record={'timestamp':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'result':'VERIFIED',
       'test':'two independently animated official 2D character sprites',
       'screenshot':visual['screenshot'],'model_comment_unverified':visual['observation'],
       'stage2_verifier':independently_verified,'not_finished_reel':True}
    with journal.open('a',encoding='utf-8') as f:
        f.write(json.dumps(record,ensure_ascii=False)+'\n')
    return {'verified':True,
            'training_step':'Stage2 visible 2D editor and independent characters validated',
            'screenshot':visual['screenshot'],
            'independent_sprites':True,'animation_tracks':4,'limb_rig_completed':False,
            'recorded_in_longterm_memory':True, 'journal_path':str(journal)}

def render_demo():
    """Export a self-contained, visibly moving technical MP4; never publish."""
    import cv2, numpy as np, hashlib, uuid
    proof=verify_stage2()
    ffmpeg=Path(r"H:\RealJarvis\OptionalPlugins\JarvisVideo\.venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe")
    if not ffmpeg.is_file():
        raise RuntimeError('local ffmpeg binary not found')
    outdir=Path.home()/'Desktop'/'Jarvis_Reels'
    outdir.mkdir(parents=True,exist_ok=True)
    tag=time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4]
    avi=PROJECT/'training'/('godot2d_'+tag+'.avi')
    output=outdir/('Lali_Pooli_Godot2D_8s_demo_'+tag+'.mp4')
    cmd=[str(EXE),'--path',str(PROJECT),'--write-movie',str(avi),
         '--fixed-fps','15','--quit-after','120',
         'res://scenes/Stage2_Independent.tscn']
    run=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
         text=True,errors='replace',timeout=75)
    if run.returncode or 'Done recording movie at path:' not in run.stdout:
        raise RuntimeError('Godot movie export failed: '+run.stdout[-1000:])
    cmd=[str(ffmpeg),'-hide_banner','-loglevel','error','-y','-i',str(avi),
         '-an','-vf','scale=1080:1920:flags=lanczos,fps=15,format=yuv420p',
         '-c:v','libx264','-preset','veryfast','-crf','24',
         '-movflags','+faststart',str(output)]
    trans=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                         text=True,errors='replace',timeout=90)
    if trans.returncode or not output.is_file() or output.stat().st_size<30000:
        raise RuntimeError('ffmpeg MP4 encoding failed: '+trans.stdout[-1000:])
    video=cv2.VideoCapture(str(output))
    if not video.isOpened():raise RuntimeError('MP4 cannot be decoded')
    frames=int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    fps=video.get(cv2.CAP_PROP_FPS)
    w=int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    h=int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video.set(cv2.CAP_PROP_POS_FRAMES,5);okay1,first=video.read()
    video.set(cv2.CAP_PROP_POS_FRAMES,48);okay2,later=video.read()
    video.release()
    if not okay1 or not okay2:raise RuntimeError('Missing decoded video frames')
    delta=float(np.mean(np.abs(first.astype(np.int16)-later.astype(np.int16))))
    if not (w==1080 and h==1920 and 14.5<=fps<=15.5 and 115<=frames<=121 and delta>5):
        raise RuntimeError(f'Export failed check: size={w}x{h} fps={fps} frames={frames} delta={delta}')
    result={'verified':True,'mp4':str(output),'seconds':round(frames/fps,2),
      'frames':frames,'fps':fps,'width':w,'height':h,'movement_difference':round(delta,2),
      'source_render': '540x960 Godot movie upscaled with FFmpeg to 1080x1920',
      'source_scene_sha256':proof['scene_sha256'],
      'separate_character_motion':True,'articulated_rig_completed':False,
      'uploaded_to_instagram':False,
      'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
    Store(STATE).remember('godot_2d_render_proof',
          'Ověřen lokální 8s technický Godot 2D MP4 test: 2 samostatné postavy, '
          '4 tracky AnimationPlayer, '+str(frames)+' snímků při 15 FPS, '
          '1080x1920 po upscalingu z 540x960. Video: '+str(output)+'. '
          'Nejde o finální Reel. Chybí rig rukou, nohou a hlavy. Na Instagram NEPUBLIKOVÁNO.',
          'verified_local_training')
    journal=PROJECT/'training'/'verified_steps.jsonl'
    with journal.open('a',encoding='utf-8') as f:
        f.write(json.dumps({'timestamp':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
           'test':'godot_stage2_export','result':'VERIFIED','evidence':result},
           ensure_ascii=False)+'\n')
    return result

def render_cookie_story():
    """Run a bounded 14s independent Godot story, original audio, verify then persist."""
    import hashlib,uuid,cv2,numpy as np
    movie=PROJECT/'scenes'/'Stage3_Story.tscn'
    verifier=PROJECT/'training'/'verify_story3.gd'
    wav=PROJECT/'training'/'stage3_original_audio.wav'
    ffmpeg=Path(r"H:\RealJarvis\OptionalPlugins\JarvisVideo\.venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe")
    if not all(x.is_file() for x in (movie,verifier,wav,EXE,ffmpeg)):
        raise RuntimeError('Godot story resources or audio missing')
    chk=subprocess.run([str(EXE),'--headless','--path',str(PROJECT),
        '--script','res://training/verify_story3.gd'],
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',timeout=35)
    if chk.returncode or 'STORY3_VERIFIED' not in chk.stdout:
        raise RuntimeError('Independent story rig verification failed: '+chk.stdout[-900:])
    ident=time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4]
    avi=PROJECT/'training'/('stage3_'+ident+'.avi')
    target=Path.home()/'Desktop'/'Jarvis_Reels'/('Lali_Pooli_Susenka_14s_PREVIEW_'+ident+'.mp4')
    target.parent.mkdir(exist_ok=True,parents=True)
    render=subprocess.run([str(EXE),'--path',str(PROJECT),'--write-movie',str(avi),
        '--fixed-fps','24','--quit-after','336','res://scenes/Stage3_Story.tscn'],
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',timeout=110)
    if render.returncode or 'Done recording movie at path:' not in render.stdout:
        raise RuntimeError('Godot failed to render story: '+render.stdout[-1000:])
    ff=subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-y',
        '-i',str(avi),'-i',str(wav),'-map','0:v:0','-map','1:a:0',
        '-vf','scale=1080:1920:flags=lanczos,fps=24,format=yuv420p',
        '-c:v','libx264','-preset','veryfast','-crf','22',
        '-c:a','aac','-b:a','160k','-t','14','-movflags','+faststart',str(target)],
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',timeout=110)
    if ff.returncode or not target.is_file() or target.stat().st_size<200000:
        raise RuntimeError('MP4 encoding failed: '+ff.stdout[-900:])
    v=cv2.VideoCapture(str(target))
    width=int(v.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(v.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps=v.get(cv2.CAP_PROP_FPS);frames=int(v.get(cv2.CAP_PROP_FRAME_COUNT))
    v.set(cv2.CAP_PROP_POS_FRAMES,20);aok,a=v.read()
    v.set(cv2.CAP_PROP_POS_FRAMES,155);bok,b=v.read()
    v.release()
    if not (aok and bok):raise RuntimeError('MP4 cannot decode two sampled frames')
    moving=float(np.abs(a.astype(np.int16)-b.astype(np.int16)).mean())
    if not(width==1080 and height==1920 and 23.5<fps<24.5 and 331<=frames<=338 and moving>4):
        raise RuntimeError(f'Video metadata not verified: {width}x{height} fps={fps} frames={frames} motion={moving}')
    # Audio must decode as well, without relying just on extension.
    audio=subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-i',str(target),
        '-map','0:a:0','-f','null','-'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        text=True,errors='replace',timeout=35)
    if audio.returncode:raise RuntimeError('Audio track failed decoding: '+audio.stdout[-400:])
    result={'verified':True,'preview_file':str(target),'duration_seconds':round(frames/fps,2),
      'resolution':f'{width}x{height}','fps':fps,'frames':frames,
      'motion_difference':round(moving,2),'head_and_arm_pivots_per_character':2,
      'actual_independent_head_arm_movement':True,
      'audio':'original synthesized gibberish and effects','subtitles':False,
      'published':False,'real_bone_rig':False,
      'source_sha256':hashlib.sha256(movie.read_bytes()).hexdigest()}
    Store(STATE).remember('lali_pooli_stage3_story',
        'Ověřeno v Godot 4.7.2: 14s vlastní příběh Pooliho sušenky. '
        'Dvě oficiální postavy ze schválených pixelů mají každá samostatné body/head/arm '
        'části s rotací kolem pivotů, animovanou sušenku a srdíčka. '
        'Původní syntetické zvuky a nesrozumitelné žvatlání bez titulků. '
        'Výsledný soubor: '+str(target)+'. Zatím nejde o plnohodnotnou kostru ani hotový sériový workflow. '
        'Bez publikace na IG.','verified_local_training')
    journal=PROJECT/'training'/'verified_steps.jsonl'
    with journal.open('a',encoding='utf-8') as j:
        j.write(json.dumps({'timestamp':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
          'result':'VERIFIED','test':'stage3_original_cookie_story', 'details':result},
          ensure_ascii=False)+'\n')
    return result
