"""Bounded local Blender task: fixed pre-reviewed scene, no arbitrary user code."""
from pathlib import Path
import subprocess
ROOT=Path(r'H:\RealJarvis\OptionalPlugins\JarvisBlender3D')
BLENDER=Path(r'H:\RealJarvis\OptionalPlugins\Blender4.5LTS\blender-4.5.15-windows-x64\blender.exe')
SCRIPT=ROOT/'pilot.py'
SCENE=ROOT/'Lali_Pooli_3D_Pilot.blend'
def status():
 return {'verified':True,'ready':BLENDER.is_file() and SCRIPT.is_file(),'blender':str(BLENDER),'scene_exists':SCENE.is_file(),'automation':'fixed Blender Python scene; no arbitrary scripts','published':False}
def create_scene():
 if not BLENDER.is_file() or not SCRIPT.is_file():raise RuntimeError('blender_or_fixed_scene_missing')
 proc=subprocess.run([str(BLENDER),'-b','--factory-startup','-t','2','--python-exit-code','27','--python',str(SCRIPT)],cwd=str(ROOT),capture_output=True,text=True,timeout=55,encoding='utf-8',errors='replace')
 if proc.returncode!=0 or not SCENE.is_file():raise RuntimeError('blender_scene_failed:'+proc.stderr[-400:])
 return {'verified':True,'scene_file':str(SCENE),'bytes':SCENE.stat().st_size,'character_names':['Lali','Pooli'],'real_3d_keyframes':True,'published':False,'scope':'simple 3D pilot, not final visual quality or production Reel'}

def render_preview():
 """Render fixed 30-frame Blender pilot; no arbitrary input or publishing."""
 script=ROOT/'render_preview.py'
 output=ROOT/'Lali_Pooli_3D_Pilot_2s.mp4'
 if not BLENDER.is_file() or not SCENE.is_file() or not script.is_file():raise RuntimeError('blender_scene_or_preview_missing')
 proc=subprocess.run([str(BLENDER),'-b',str(SCENE),'-t','2','--python-exit-code','25','--python',str(script)],cwd=str(ROOT),capture_output=True,text=True,timeout=90,encoding='utf-8',errors='replace')
 if proc.returncode or not output.is_file() or output.stat().st_size<10000:raise RuntimeError('blender_render_failed:'+proc.stderr[-300:])
 return {'verified':True,'preview_file':str(output),'bytes':output.stat().st_size,'duration_seconds':2,'fps':15,'published':False,'has_audio':False,'scope':'basic 3D technical preview, NOT finished reel'}

def import_references():
 """Controlled import of authenticated user-approved reference images from Downloads."""
 import importlib.util
 path=ROOT/'import_references.py'
 if not path.is_file():raise RuntimeError('reference_importer_missing')
 spec=importlib.util.spec_from_file_location('lali_pooli_reference_importer',str(path))
 module=importlib.util.module_from_spec(spec)
 spec.loader.exec_module(module)
 return module.import_reference_zip()

def reference_status():
 """Never substitute a technical scene for verified 3D character models."""
 source=ROOT/'References'
 full=[source/'01_Charakterovy_list_Lali_Pooli.png',source/'02_Mimika_a_pohyby_Lali_Pooli.png']
 present=all(p.is_file() for p in full)
 model=ROOT/'ApprovedModels'/'Lali_Pooli_Approved_Models.blend'
 return {'verified':True,'references_loaded':present,'character_models_approved':model.is_file(),'ready_for_final_reels':False,'reference_dir':str(source),'next_step':'Manually compare 3D models against canonical character reference images; no completed rig yet'}