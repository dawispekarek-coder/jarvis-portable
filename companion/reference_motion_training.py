from pathlib import Path
import numpy as np,io,base64,urllib.request,json,time
from PIL import Image,ImageDraw,ImageFont
from companion_store import Store
from companion_settings import STATE
study=Path(r'H:\RealJarvis\OptionalPlugins\JarvisGodot2D\study_examples')
clips=['bubu_dudu_hug_motion_REFERENCE_ONLY.gif','kiss_reference_only.gif','bedroom_reference_only.gif']
board=Image.new('RGB',(900,3*206),(246,241,236))
d=ImageDraw.Draw(board)
proof=[]
for row,filename in enumerate(clips):
 im=Image.open(study/filename)
 positions=[0,max(1,im.n_frames//4),im.n_frames//2,(im.n_frames*3)//4,im.n_frames-1]
 bits=[]
 for col,index in enumerate(positions):
  im.seek(index);frame=im.convert('RGB')
  frame.thumbnail((169,167))
  board.paste(frame,(col*180+(180-frame.width)//2,row*206+28))
  d.text((col*180+5,row*206+4),f'#{row+1}  f{index}/{im.n_frames}',fill=(33,28,23))
  bits.append(np.array(frame.resize((128,128))).astype(np.int16))
 movement=[round(float(np.mean(np.abs(a-b)))/255,4) for a,b in zip(bits,bits[1:])]
 proof.append({'clip':filename,'frames':im.n_frames,'indexes':positions,
               'diff_score_mean':round(float(np.mean(movement)),4),
               'changed_across_sample':max(movement)>0.012,
               'row':row+1})
file=study/'three_gifs_temporal_sequence_vision_ONLY.jpg'
board.save(file,quality=80)
b=io.BytesIO();board.save(b,format='JPEG',quality=65)
prompt=('Observe THIS TRAINING CONTACT SHEET OF 3 DIFFERENT SHORT ANIMATED GIF LOOPS. '
        'Each row is one loop, five sequential sample frames left to right. '
        'Describe in Czech WHAT CHANGES frame-to-frame in each row and what remains unchanged. '
        'Do NOT tell a longer story you cannot see; these are THREE separate single-scene loops, '
        'not connected scenes with cuts. Mention pose anticipation/exaggeration and expression. '
        'Say how 4-6 DISTINCT camera shots could form a longer ORIGINAL story for '
        'Lali & Pooli without copying these existing copyrighted characters or scenes. '
        'Never use Bubu or Dudu art in produced video. Do not overclaim motion. '
        'Answer short Czech, 5-7 sentences.')
req={'model':'qwen3.5:4b-q4_K_M','messages':[{'role':'user','content':prompt,
      'images':[base64.b64encode(b.getvalue()).decode('ascii')]}],'stream':False,
     'think':False,'options':{'num_predict':345,'temperature':0.15}}
request=urllib.request.Request('http://127.0.0.1:11434/api/chat',
    data=json.dumps(req).encode('utf8'),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=110) as f:
 ans=json.load(f)['message']['content']
if not ans.strip(): raise RuntimeError('no vision observation')
report={'date':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'ref_motion_proof':proof,
        'vision_model_interpretation_unverified':ans,'reference_only':True,
        'no_full_story_cut_claim':True,'board':str(file)}
outfile=study/'temporal_gif_learning_result.json'
outfile.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
Store(STATE).remember('lali_pooli_reference_motion_3clips',
 'Prostudoval jsem tri verejne dostupne 2D animovane GIFy pouze pro vyuku pohybu a emoci, jejich sekvence 5 snimku na radek (gif ma '+','.join(str(i['frames']) for i in proof)+
 ' snimku). Obrazovy model analyzoval zmeny gest, zvyrazneni reakci a staticke pozadi, ale jeho popis muze byt nepresny. Tyto smycky nemaji skutecne filmove STRIHY. Delší příběh se skládá z 4-6 vlastních odlišných záběrů; viz COMPANION storyboard video. Cast filmu originalnimu uzivateli pouze z původních postav. Studie: '+str(outfile),
 'observed_reference_motion_learning')
print('DONE',json.dumps({'references':[{'name':x['clip'],'frames':x['frames'],'motion_score':x['diff_score_mean'],'changed':x['changed_across_sample']} for x in proof],
    'vision_excerpt':ans[:750],'file':str(outfile)},ensure_ascii=False))
