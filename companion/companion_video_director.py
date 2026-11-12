"""Jarvis standalone Czech story director; planning is NOT production approval."""
import json,urllib.request,re,unicodedata,time,hashlib
from pathlib import Path
from companion_store import Store
from companion_settings import STATE
R=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot')
OUT=R/'training'/'autonomous';OUT.mkdir(parents=True,exist_ok=True)
BEATS=('setup','trigger','reaction','response','payoff')
FIELDS=('beat','camera','setting','action','lali_emotion','pooli_emotion','lali_pose','pooli_pose','prop','sound')
schema={'type':'object','properties':{'title':{'type':'string'},'premise':{'type':'string'},'location':{'type':'string'},'shots':{'type':'array','items':{'type':'object','properties':{k:{'type':'string'} for k in FIELDS},'required':list(FIELDS)}}},'required':['title','premise','location','shots']}
SYS=('Create an ORIGINAL 14-second wordless 2D animated raccoon mini-story from the exact Czech user request. '
'LALI is female with original pink bow; POOLI male in backward blue cap/hoodie with distinct original masculine face, no added makeup or eyelashes. '
'Return ONLY valid JSON: title, premise, location, shots (exactly 5 in order setup,trigger,reaction,response,payoff), '
'each shot has beat,camera [WIDE/MEDIUM/CLOSE],setting,action,lali_emotion,pooli_emotion,lali_pose,pooli_pose,prop,sound. '
'Use Czech for values. Show clearly WHY the situation happens, anticipation, changing emotions, realistic physical interaction and happy payoff. '
'If coming home from work show door, work bag and joyful welcome and hug. '
'Never substitute cookie/picnic for requested situation. Make story understandable without dialogue or subtitles, only original playful babbling and effects. '
'Camera and physical poses must change. No borrowed Bubu/Dudu characters, art or scenes. '
'Keep approved Lali and Pooli identities. User request: ')
def norm(s):
 return ''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if not unicodedata.combining(c))
CINEMA_BEATS=('setup','approach','entry','reaction','embrace','payoff')
CINEMA_SCRIPT=R/'training'/'director_curriculum'/'04_KINOVA_REZIE_ZAVRENE_DVERE_POOLI_VCHAZI.md'
GENERAL_TEMPLATE=R/'training'/'director_curriculum'/'02_REEL_PROMPT_TEMPLATE_CZ.md'

def is_homecoming(goal):
 n=norm(goal)
 return 'prace' in n and any(t in n for t in ('dom','vrat','prichaz','prijde','vchaz'))

def cinema_context(goal):
 if is_homecoming(goal):
  if not CINEMA_SCRIPT.is_file():raise RuntimeError('Cinematic continuity reference missing')
  script=CINEMA_SCRIPT.read_text(encoding='utf8')
  return ('\\nMANDATORY ORIGINAL CINEMATIC SCRIPT; follow six shots in order,'
          ' do not claim footage exists simply because planned.\\n'+script[:5500]+
          '\\nMANDATORY ENDING, CONTINUITY AND QA:\\n'+script[-1800:])
 if not GENERAL_TEMPLATE.is_file():raise RuntimeError('Generic per-Reel prompt template missing')
 script=GENERAL_TEMPLATE.read_text(encoding='utf8')
 return '\\nGENERAL CINEMATIC REQUIREMENTS FOR EACH REEL:\\n'+script[:2800]

def learned_techniques():
    ref=R/'training'/'learning20'/'lessons_for_director.txt'
    if not ref.is_file():return ''
    lines=ref.read_text(encoding='utf8').splitlines()
    if len(lines)<20:return ''
    return '\n'+'VERIFIED SAMPLED REFERENCE LESSONS (TECHNIQUES ONLY, NEVER COPY ART/SHOTS):\n'+ '\n'.join(x[:220] for x in lines[:20])+'\n'
def make_plan(goal):
 cinema=is_homecoming(goal)
 system=SYS
 if cinema:
  system=system.replace('14-second','18-second').replace(
   'exactly 5 in order setup,trigger,reaction,response,payoff',
   'exactly 6 in order setup,approach,entry,reaction,embrace,payoff')
 system += (' Every shot must state the physical action, visual expression, feet and ground contact '
            'if walking, necessary prop state, justified camera angle, and exact scene continuity. '
            'Closed doors must be visible BEFORE the act of opening, and actor must visibly cross threshold. ')
 payload={'model':'qwen3.5:4b-q4_K_M',
   'messages':[{'role':'user','content':system+goal+cinema_context(goal)+learned_techniques()[:1800]}],
   'stream':False,'format':'json','think':False,
   'options':{'temperature':0.15,'num_predict':2600,'num_ctx':8192}}
 req=urllib.request.Request('http://127.0.0.1:11434/api/chat',
   data=json.dumps(payload,ensure_ascii=False).encode('utf8'),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=115) as response:
  obj=json.load(response)
 return json.loads(obj['message']['content'])

def camera_class(value):
 n=norm(str(value))
 if 'close' in n or 'detail' in n:return 'CLOSE'
 if 'medium' in n or 'polocelk' in n:return 'MEDIUM'
 if 'wide' in n or 'celk' in n:return 'WIDE'
 return 'unknown'

def audit_plan(plan,goal):
 faults=[];shots=plan.get('shots',[])
 expected=CINEMA_BEATS if is_homecoming(goal) else BEATS
 if len(shots)!=len(expected):return ['Vyžadováno přesně '+str(len(expected))+' různých záběrů']
 for i,s in enumerate(shots):
  beat=norm(str(s.get('beat','')))
  if is_homecoming(goal):
   mt=re.match(r'^([0-9]+(?:[.,][0-9]+)?)\s*[–-]',str(s.get('beat','')))
   starts=(0.0,2.0,4.5,7.5,10.0,15.0)
   good_timing=mt is not None and abs(float(mt.group(1).replace(',','.'))-starts[i])<.31
   beat_ok=beat==expected[i] or good_timing
  else:
   beat_ok=beat==expected[i]
  if not beat_ok:faults.append('Neplatné pořadí děje v záběru '+str(i+1))
  if camera_class(s.get('camera',''))=='unknown':faults.append('Chybí kompozice v záběru '+str(i+1))
  for field in FIELDS:
   if len(str(s.get(field,'')))<2:faults.append('Záběr '+str(i+1)+' nemá '+field)
 if is_homecoming(goal):
  segments=[norm(s.get('action','')+' '+s.get('setting','')+' '+s.get('prop','')) for s in shots]
  must=[(0,('zavren','dver'),'Prvni zaber musi ukazat zavrene dvere'),
        (1,('pooli','klik'),'Pooli musi dojit k zavrenym dverim a uchopit kliku'),
        (2,('otevr','prah'),'Zaber 3 musi ukazat skutecne otevreni dveri a pruchod prahem'),
        (3,('lali',),'Zaber 4 musi ukazat Laliinu reakci'),
        (4,('objm',),'Zaber 5 musi ukazat skutecne objeti')]
  for i,tokens,msg in must:
   if i==4 and any(t in segments[i] for t in ('objm','objim','obejm','objeti','obeti')):continue
   if not all(t in segments[i] for t in tokens):faults.append(msg)
 if len({camera_class(s.get('camera','')) for s in shots})<2:faults.append('Chybí střídání velikostí záběrů')
 if len({s['lali_emotion'] for s in shots})<2:faults.append('Lali nereaguje emocionálně')
 if len({s['pooli_emotion'] for s in shots})<2:faults.append('Pooli nereaguje emocionálně')
 text=norm(' '.join([plan.get('premise',''),plan.get('location','')]+
  [s.get('action','')+' '+s.get('setting','') for s in shots]))
 prompt=norm(goal)
 if 'prace' in prompt and 'dom' in prompt:
  for key,ok in [('práce',any(w in text for w in ('prac','smen','zamestnan'))),
                 ('návrat domů',any(w in text for w in ('dom','dver','vchod','byt'))),
                 ('radostné přivítání',any(w in text for w in ('radost','vit','obejm','tesi','nadsen','stast','usme')))]:
   if not ok:faults.append('Příběh neobsahuje '+key)
 return faults
def quality_gate():
 p=R/'assets'/'approved_expression_library'/'atlas.json'
 n=len(json.loads(p.read_text(encoding='utf8')).get('expressions',[])) if p.is_file() else 0
 return {'reference_emotions':n,'production_assets_ready':False,'creatively_approved':False,
 'blockers':['Neexistují produkčně schválené víceúhlové HD podoby Lali/Pooli',
  'Chybí plnohodnotný rig chůze, přivítání a objetí',
  'Chybí sourodé HD prostředí pro konkrétní scénu',
  'Vizuální shoda Pooliho obličeje ve snímcích nebyla prokázána',
  'Předchozí výtvarně nevyhovující video bylo výslovně odmítnuto']}
def direct_story(goal):
 if not isinstance(goal,str) or not 8<=len(goal)<=1100:raise ValueError('Neplatná délka zadání')
 plan=make_plan(goal); faults=audit_plan(plan,goal);gate=quality_gate()
 draft=None
 if not faults and not is_homecoming(goal) and 'prace' in norm(goal) and 'dom' in norm(goal) and (R/'training'/'learning20'/'lessons_for_director.txt').is_file():
  from companion_homecoming_render import render_homecoming
  try:draft=render_homecoming()
  except Exception as exc:draft={'stage':'RENDER_FAILED','error':type(exc).__name__+': '+str(exc)[:240]}
 d=OUT/(time.strftime('%Y%m%d_%H%M%S')+'_'+hashlib.sha256(goal.encode()).hexdigest()[:8]);d.mkdir()
 manifest={'goal':goal,'storyboard':plan,'plan_faults':faults,'quality_gate':gate,
 'plan_valid':not faults,'cinematic_six_shots':is_homecoming(goal),'cinematic_reference':str(CINEMA_SCRIPT) if is_homecoming(goal) else str(GENERAL_TEMPLATE),'creative_quality_approved':False,'finished_video':False,
 'instagram_posted':False,'draft_render':draft,'stage':'PLAN_NEEDS_REVISION' if faults else 'DRAFT_NOT_APPROVED' if draft and draft.get('preview_file') else 'ASSETS_BLOCK_PRODUCTION'}
 report=d/'manifest.json';report.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
 lines=['# '+plan.get('title','Lali a Pooli'),'**Pouze storyboard; není to hotové video.**']
 for i,s in enumerate(plan['shots']):
  lines += [f"## {i+1}. {s.get('beat')} / {s.get('camera')}",s.get('action',''),
            'Lali: '+s.get('lali_emotion','')+' — '+s.get('lali_pose',''),
            'Pooli: '+s.get('pooli_emotion','')+' — '+s.get('pooli_pose',''),
            'Zvuk: '+s.get('sound','')]
 (d/'storyboard.md').write_text('\n\n'.join(lines),encoding='utf8')
 Store(STATE).remember('lali_pooli_latest_autonomous_story',
  'Jarvis samostatne rozvrhl zadani '+goal[:250]+'. 5 zaberu: '+str(not faults)+
  '. Nedostatecne produkcni podklady; nelze tvrdit kvalitni hotove video. '+str(report),
  'verified_autonomous_story_planning')
 return {'verified':True,'plan_valid':not faults,'problems':faults,'shots':len(plan['shots']),
  'title':plan.get('title'),'plot':[s.get('action') for s in plan['shots']],
  'scene':plan.get('location'),'ready_to_render':False,'quality_approved':False,
  'finished_video':False,'published':False,'draft_mp4':draft.get('preview_file') if draft else None,'render_result':draft,'manifest':str(report),'blockers':gate['blockers']}
