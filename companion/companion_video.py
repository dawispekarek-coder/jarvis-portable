"""Fixed, local-only video render tool. Does not publish or download."""
import json,subprocess,uuid
from pathlib import Path

ROOT=Path(r'H:\RealJarvis\OptionalPlugins\JarvisVideo')
PY=ROOT/'.venv'/'Scripts'/'python.exe'
SCRIPT=ROOT/'render_pair.py'

def status():
    ready=PY.is_file() and SCRIPT.is_file()
    return {'verified':ready,'ready':ready,'workspace':str(ROOT),
        'duration_seconds':15,'resolution':[720,1280],
        'scope':'Original fixed 2D pilot only; never publishes to social networks'}

def render():
    if not status()['ready']:raise RuntimeError('reel_renderer_missing')
    target='reel_kapka_hvezdicka_'+uuid.uuid4().hex[:8]+'.mp4'
    result=subprocess.run([str(PY),str(SCRIPT),'--output',target],
        cwd=str(ROOT),capture_output=True,text=True,encoding='utf-8',
        timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('reel_render_failed: '+result.stderr[-700:])
    data=json.loads(result.stdout.strip().splitlines()[-1])
    p=ROOT/target
    if p.resolve()!=Path(data['path']).resolve() or not p.is_file():
        raise RuntimeError('unexpected_reel_output')
    return {'verified':True,'render':data,'preview_file':str(p),
        'published':False,'story':'A rainy day is brightened by a friend',
        'scope':'Local MP4 output only'}


def render_animals():
    """Create original wordless animal reel. Does not publish."""
    program=ROOT/'render_animals.py'
    if not (PY.is_file() and program.is_file()):
        raise RuntimeError('animal_renderer_missing')
    target='animal_story_'+uuid.uuid4().hex[:8]+'.mp4'
    run=subprocess.run([str(PY),str(program),'--output',target],
        cwd=str(ROOT),capture_output=True,text=True,encoding='utf-8',
        timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if run.returncode:
        raise RuntimeError('animal_render_failed: '+run.stderr[-800:])
    data=json.loads(run.stdout.strip().splitlines()[-1])
    p=(ROOT/target).resolve()
    if not p.is_file() or str(p)!=str(Path(data['file']).resolve()):
        raise RuntimeError('animal_video_missing')
    if p.stat().st_size<30000 or data['published'] or data['onscreen_text'] is not False:
        raise RuntimeError('animal_video_validation_failed')
    import shutil
    from datetime import datetime
    from companion_hashtags import suggest
    desk=Path.home()/'Desktop'/'Jarvis_Reels'
    desk.mkdir(parents=True,exist_ok=True)
    name='Jarvis_Zviratka_'+datetime.now().strftime('%Y%m%d')+'_'+uuid.uuid4().hex[:6]
    dest=desk/(name+'.mp4')
    if dest.exists():raise FileExistsError(dest)
    shutil.copy2(p,dest)
    if dest.stat().st_size!=p.stat().st_size:raise RuntimeError('desktop_copy_incomplete')
    meta=suggest(data['story'])
    caption='A tiny everyday misunderstanding turns into a moment of friendship. ????\n\n'+meta['caption_suffix']
    (desk/(name+'_instagram_caption.txt')).write_text(caption,encoding='utf-8')
    return {'verified':True,'preview_file':str(dest),'source_file':str(p),
      'render':data,'hashtags':meta['hashtags'],'caption_file':str(desk/(name+'_instagram_caption.txt')),
      'published':False,'scope':'Daily local draft only; publishing not connected'}
