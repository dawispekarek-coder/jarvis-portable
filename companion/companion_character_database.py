"""Safe read-only Jarvis adapter over persistent Lali/Pooli SQLite asset catalog."""
from __future__ import annotations
from pathlib import Path
import importlib.util,sys,json
HERE=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\studio_library\character_database')

spec=importlib.util.spec_from_file_location('lali_pooli_catalog',HERE/'catalog.py')
if spec is None or spec.loader is None:raise RuntimeError('Character database not installed')
catalog=importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)

def status():
    data=catalog.verify()
    return {**data,'verified':data['verified'],'originals_immutable':True,'working_wave_reference':'pooli_wave_open_working_a','auto_publish':False,'roles':{'approved_master':'original source identity','approved_working':'reusable tested art','candidate':'requires review','rejected':'forbidden as reference'}}

def search(character='pooli',kind='all',status='approved',pose=''):
    allowed=('approved_master','approved_working') if status=='approved' else (status,)
    if status!='approved' and status not in ('candidate','rejected'):raise ValueError('unsupported status search')
    if character not in ('pooli','lali','shared'):raise ValueError('invalid character')
    if kind!='all' and kind not in catalog.KINDS:raise ValueError('invalid kind')
    images=catalog.list_assets(character=character,kind=None if kind=='all' else kind,statuses=allowed,pose=pose or None)
    return {'verified':True,'character':character,'status_filter':status,'items':[{'id':i['id'],'name':i['name'],'kind':i['kind'],'pose':i['pose'],'status':i['status'],'path':i['path'],'sha256':i['sha256'],'tags':i['tags'],'annotations':i['annotations'],'integrity_valid':i['integrity_valid']} for i in images],'count':len(images),'safe_for_new_generations':status=='approved'}

def plan(character='pooli',action='wave',expression=''):
    if character not in ('pooli','lali'):raise ValueError('invalid character')
    res=catalog.select(character,action=action,expression=expression or None)
    return {**res,'visual_qa_required':True,'may_recreate_missing_parts':False,'can_use_rejected':False,'verified':res['verified']}