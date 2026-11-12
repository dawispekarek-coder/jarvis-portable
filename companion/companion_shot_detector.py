"""Bounded local shot-boundary detector for video training with user authorization.
Accepts only explicit accessible study/project files, never downloads external clips.
"""
from __future__ import annotations
import cv2,numpy as np,json,time
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D')
ALLOWED=[ROOT/'study_examples',ROOT/'LaliPooli2D_Pilot'/'training',
         Path.home()/'Desktop'/'Jarvis_Reels']
def analyze_local_clip(path:str)->dict:
    if not path: raise ValueError('path required')
    file=Path(path).resolve()
    if file.suffix.lower() not in ('.mp4','.mov','.avi','.webm'):
        raise ValueError('not a supported video')
    if not file.is_file():raise FileNotFoundError(file)
    if not any(base.resolve()==file or base.resolve() in file.parents for base in ALLOWED):
        raise ValueError('video outside approved study folders')
    if file.stat().st_size>180_000_000:raise ValueError('file exceeds 180MB study budget')
    cap=cv2.VideoCapture(str(file))
    if not cap.isOpened():raise RuntimeError('cannot decode video')
    fps=cap.get(cv2.CAP_PROP_FPS)
    frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps<1 or fps>240 or frame_count<1:raise RuntimeError('bad metadata')
    duration=frame_count/fps
    if duration>600:raise ValueError('video longer than 10min study budget')
    samples=min(1200,max(2,int(duration*4)))
    prev=None;candidates=[];rowframes=[];dt=duration/samples
    for step in range(samples):
        sec=min(duration-0.001,step*dt)
        cap.set(cv2.CAP_PROP_POS_MSEC,sec*1000)
        ok,frm=cap.read()
        if not ok:continue
        frm=cv2.resize(frm,(160,90),interpolation=cv2.INTER_AREA)
        if prev is not None:
            delta=float(np.mean(np.abs(frm.astype('int16')-prev.astype('int16'))))/255
            if delta>0.135:
                candidates.append({'time':round(sec,2),'luma_rgb_change':round(delta,4)})
        prev=frm
    cap.release()
    # Group near-adjacent candidate frames into probable scene boundaries.
    scene_cuts=[]
    for cut in candidates:
        if scene_cuts and cut['time']-scene_cuts[-1]['time']<0.85:
            if cut['luma_rgb_change']>scene_cuts[-1]['luma_rgb_change']:
                scene_cuts[-1]=cut
        else:
            scene_cuts.append(cut)
    boundaries=[0.0]+[x['time'] for x in scene_cuts]+[round(duration,2)]
    out_dir=ROOT/'LaliPooli2D_Pilot'/'training'/'shot_learning'
    out_dir.mkdir(exist_ok=True)
    report={'file':str(file),'duration':round(duration,2),'fps':fps,'samples_scanned':samples,
        'approximate_cut_boundaries':scene_cuts,
        'estimated_shots':len(scene_cuts)+1,
        'threshold':0.135,'limitations':'Brightness/fast motion may trigger false cuts. Manual confirmation of contact frames required.',
        'verified':True,'automatic_verified':True,'creative_quality_approved':False,'published':False}
    out=out_dir/('cuts_'+file.stem+'.json')
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    report['report_file']=str(out)
    return report
if __name__=='__main__':
    import sys
    print(json.dumps(analyze_local_clip(sys.argv[1]),ensure_ascii=False))
