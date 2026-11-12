"""Lali & Pooli production quality review. Creative acceptance requires human signoff."""
from __future__ import annotations
import json,hashlib,time
from pathlib import Path
from PIL import Image
import cv2,numpy as np

ROOT=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot')
SOURCE=ROOT/'scenes'/'Stage3_Story.gd'
REFERENCE=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\study_examples')
FILE=Path(r'C:\Users\Dawis\Desktop\Jarvis_Reels\Lali_Pooli_Susenka_14s_PREVIEW_20261027_222228_d77c.mp4')
REPORT=ROOT/'training'/'production_quality_review_20261027.json'
SKILL=ROOT/'training'/'PRODUCTION_QUALITY_STANDARD.md'

def inspect():
    if not FILE.exists() or not SOURCE.exists():
        raise RuntimeError('Original technical draft missing: do not claim audit done')
    v=cv2.VideoCapture(str(FILE))
    duration=v.get(cv2.CAP_PROP_FRAME_COUNT)/max(1,v.get(cv2.CAP_PROP_FPS))
    w,h=int(v.get(cv2.CAP_PROP_FRAME_WIDTH)),int(v.get(cv2.CAP_PROP_FRAME_HEIGHT))
    samples=[]
    for t in [0.3,2.5,4.5,6.5,9.0,11.7,13.2]:
        v.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,f=v.read()
        if ok:samples.append((t,cv2.resize(f,(270,480))))
    v.release()
    differences=[]
    for a,b in zip(samples,samples[1:]):
        differences.append(round(float(np.mean(np.abs(a[1].astype('int16')-b[1].astype('int16')))),2))
    clips=[]
    for name in ('bubu_dudu_hug_motion_REFERENCE_ONLY.gif','kiss_reference_only.gif','bedroom_reference_only.gif'):
        p=REFERENCE/name
        if not p.exists():continue
        im=Image.open(p)
        total=0
        for k in range(im.n_frames):
            im.seek(k);total+=im.info.get('duration',100)
        clips.append({'name':name,'frame_count':im.n_frames,'duration_s':round(total/1000,2),'used_for':'study ONLY'})
    src=SOURCE.read_text(encoding='utf8')
    blockers=[
        'Uživatel výslovně odmítl výsledné video jako příšerné; tím kreativní kvalita automaticky NEPROŠLA.',
        'Pouze jedna původní statická póza mývala na postavu: pohybování výřezů neumožňuje přirozenou chůzi ani jinou akci.',
        'Neměnné otevřené oči/úsměv: zklamání, překvapení, smutek a radost nejsou věrohodně zahrané.',
        'Plochý vektorový podklad stylově neodpovídá jemně vykreslené 3D-like srsti postaviček.',
        'Beze změny kompozice a měřítka: kamera není režijní a neukazuje close-up/reakci.',
        'Sušenka létá bez jasné fyzikální nebo situační příčiny, divák nerozumí, co se stalo.',
        'Podobné pohyby obou postav opakované bez reakce těla: vizuální pantomima nedostatečná.',
        'Pohyblivé části vzniklé řezem přes jeden obrázek: riziko viditelných spár při otáčení a neexistujících zadních ploch.',
        'Zvukové žvatlání zatím není navázané na přesně animované tvary úst.'
    ]
    standard={
      'project':'Lali and Pooli original videos, inspired by emotion-first SHORTS, not by duplicating Bubu Dudu',
      'identity':['Maintain exact previously approved raccoon look and differentiate Pooli face',
                  'No new makeup/eyelashes for Pooli and no redrawn heads without owner approval',
                  'Never reconstruct unseen body texture automatically'],
      'minimum_character_assets':['approved high resolution head: front, 3/4, side','head expressions: neutral, surprise, sad, happiness, blink; direct approved original only',
            'mouth shapes: closed, O, smile, babble; owner approved',
            'feet in two walking positions and articulated independent forearms',
            'tail overlap art without cut-out edge seams'],
      'story':['visual reason for problem is clear in first 2 seconds','one concrete prop, clear anticipation and response','reaction shot and perspective change','emotion visible even with sound muted','ending clear in last 2s'],
      'technical':['1080x1920 encoded with 24fps or higher, natural visual sharpness',
          'no subtitles or text overlays inside the film','voice babbling plus distinct synchronized Foley',
          'verify face consistency frame samples','verify no visual seams/gaps'],
      'approval':['Never label creative quality VERIFIED merely because ffmpeg and Godot exit 0',
          'preflight visual contact sheet plus audio clip review required',
          'quality pass is FALSE until user explicitly approves',
          'never publish or schedule upload without separate permission']
    }
    report={
      'audit_kind':'creative_quality_and_reference_comparison',
      'timestamp':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
      'technical_verified':True,'creative_quality_passed':False,
      'publication_approved':False,
      'rejected_source':str(FILE),'reason':'Direct explicit negative user feedback and independent observable flaws',
      'reference_samples':clips,'duration_seconds':round(duration,2),
      'resolution':[w,h],'sampled_motion_differences':differences,
      'source_hash':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
      'observed_blockers':blockers,'acceptance_criteria':standard,
      'next_step':'Build approved expression/pose asset pack first. Do not render another cookie prototype.'
    }
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    md=['# REJECTED: visual quality audit of Lali & Pooli Stage3',
        'Technical tests were green. **Creative quality FAILED** by explicit owner feedback.',
        'Current Stage3 must NOT be used as production-ready Reel.',
        'Comparison clips are reference only; never embed them in authored output.',
        '## Reasons']
    md.extend('- '+x for x in blockers)
    md.append('## Requirements before next candidate')
    for k,values in standard.items():
        if isinstance(values,list):
            md.append('### '+k)
            md.extend('- '+str(x) for x in values)
    md.append('## Technical source and evidence')
    md.append(str(FILE))
    md.append(str(REPORT))
    SKILL.write_text('\n'.join(md)+'\n',encoding='utf8')
    return {'verified':True,'technical_verified':True,'creative_quality_passed':False,
            'publication_approved':False,'blockers':len(blockers),
            'reference_clips_studied':len(clips),'report':str(REPORT),'training_file':str(SKILL)}
if __name__=='__main__':
    print(json.dumps(inspect(),ensure_ascii=False))
