/* Preserve the original UI. Add durable identity, task controls and local voice. */
(() => {
 const NativeWS=window.WebSocket, sockets=new Set();let seq=0,lastTask='',speechEpoch=0,playing=null;
 let client=localStorage.getItem('jarvis-companion-client');
 if(!client){client=crypto.randomUUID();localStorage.setItem('jarvis-companion-client',client);}
 const headers={'X-Jarvis-Client':client};let speech=localStorage.getItem('jarvis-companion-speech')!=='off';
 let speechQueue=Promise.resolve();
 async function speak(text,task){
  const epoch=speechEpoch;if(!speech)return;
  try{
   const response=await fetch('/api/tts',{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({text:text.slice(0,2000)})});
   if(!response.ok||epoch!==speechEpoch)return;
   const url=URL.createObjectURL(await response.blob()),audio=new Audio(url);playing=audio;
   await new Promise((resolve)=>{audio.onended=()=>{fetch('/companion/tasks/'+task.split(':resume:')[0]+'/playback',{method:'POST',headers}).catch(()=>{});URL.revokeObjectURL(url);resolve();};audio.onerror=()=>{URL.revokeObjectURL(url);resolve();};audio.onpause=()=>resolve();audio.play().catch(resolve);});
  }catch(e){console.info('JARVIS voice unavailable');}
 }
 window.WebSocket=class extends NativeWS {
  constructor(url,protocols){
   const u=new URL(url,location.href),ours=u.pathname==='/ws'&&u.host===location.host;
   if(ours){u.searchParams.set('client',client);u.searchParams.set('after',String(seq));}
   if(protocols===undefined)super(u.href);else super(u.href,protocols);
   if(ours){sockets.add(this);super.addEventListener('close',()=>sockets.delete(this));super.addEventListener('message',event=>{
    try{const m=JSON.parse(event.data);if(m.message_seq)seq=Math.max(seq,m.message_seq);if(m.task_id)lastTask=m.task_id;
     if(m.type==='assistant'&&!m.historical){speechQueue=speechQueue.then(()=>speak(m.text||'',m.task_id||lastTask));}
    }catch(e){}
   });}
  }
  send(data){
   try{const m=JSON.parse(data);if(['chat','command'].includes(m.type)&&!m.request_id){m.request_id=crypto.randomUUID();data=JSON.stringify(m);}}catch(e){}
   return super.send(data);
  }
 };
 function send(text){const socket=[...sockets].find(s=>s.readyState===NativeWS.OPEN);if(socket){socket.send(JSON.stringify({type:'chat',text}));return true;}return false;}
 window.jarvisCompanionSend=send;
 function el(tag,text,style){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(style)e.style.cssText=style;return e;}
 const buttonStyle='border:1px solid #235868;background:#0b2028;color:#bceffc;border-radius:7px;padding:7px 10px;cursor:pointer;font:12px system-ui';
 function button(text,action){const b=el('button',text,buttonStyle);b.onclick=action;return b;}
 const labels={QUEUED:'Ve frontě',RUNNING:'Pracuji',VERIFIED:'Ověřeno',ANSWERED:'Odpovězeno',PARTIAL:'Zbývá dokončit',FAILED:'Chyba',CANCELLED:'Zastaveno',NEEDS_REVIEW:'Potřebuje kontrolu',WAITING_APPROVAL:'Čeká na potvrzení'};
 document.addEventListener('DOMContentLoaded',()=>{
  const bar=el('div',undefined,'position:fixed;right:16px;bottom:12px;z-index:2147483600;display:flex;gap:5px;align-items:center;background:#06131bea;border:1px solid #235868;border-radius:10px;padding:7px;box-shadow:0 6px 22px #0008;font:12px system-ui;color:#a4dbe8');
  const status=el('span','Připojuji…','padding:0 6px;max-width:190px');bar.append(status);
  const panel=el('section',undefined,'display:none;position:fixed;right:16px;bottom:68px;width:min(460px,calc(100vw - 32px));max-height:70vh;overflow:auto;z-index:2147483600;background:#07151ff5;border:1px solid #286578;border-radius:12px;padding:16px;color:#d2eff6;font:13px system-ui;box-shadow:0 10px 40px #000b');
  document.body.append(bar,panel);
  const voice=button(speech?'Hlas zapnutý':'Hlas vypnutý',()=>{speech=!speech;localStorage.setItem('jarvis-companion-speech',speech?'on':'off');voice.textContent=speech?'Hlas zapnutý':'Hlas vypnutý';if(!speech){speechEpoch++;if(playing)playing.pause();}});
  bar.append(button('Úkoly',()=>{panel.style.display=panel.style.display==='none'?'block':'none';refresh();}),voice);
  let recorder=null,stream=null,chunks=[],timer=null;
  const mic=button('Mluvit',async()=>{
   if(recorder&&recorder.state==='recording'){recorder.stop();return;}
   try{
    stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];recorder=new MediaRecorder(stream);
    recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};recorder.onstop=async()=>{
     clearTimeout(timer);stream.getTracks().forEach(t=>t.stop());mic.textContent='Přepisuji…';mic.disabled=true;
     try{const response=await fetch('/companion/stt',{method:'POST',headers,body:new Blob(chunks,{type:recorder.mimeType})}),data=await response.json();if(!response.ok)throw Error(data.error||'Přepis se nepodařil');if(!send(data.text))throw Error('Rozhraní není připojené');}
     catch(e){status.textContent=e.message;}finally{mic.textContent='Mluvit';mic.disabled=false;recorder=null;}
    };recorder.start();mic.textContent='Dokončit větu';timer=setTimeout(()=>{if(recorder&&recorder.state==='recording')recorder.stop();},30000);
   }catch(e){status.textContent='Mikrofon není dostupný';if(stream)stream.getTracks().forEach(t=>t.stop());}
  });
  bar.append(mic,button('Stop',()=>{speechEpoch++;if(playing)playing.pause();if(recorder&&recorder.state==='recording'){recorder.onstop=()=>stream.getTracks().forEach(t=>t.stop());recorder.stop();}send('Stop');}));
  async function act(id,action){const r=await fetch('/companion/tasks/'+id+'/'+action,{method:'POST',headers});if(!r.ok){const d=await r.json();status.textContent=d.error||'Akce se nepodařila';}await refresh();}
  async function refresh(){
   try{
    const response=await fetch('/companion/state?brief=1',{headers});if(!response.ok)return;const data=await response.json();
    const active=data.tasks.filter(t=>['RUNNING','QUEUED'].includes(t.status));status.textContent=data.worker.alive?(active.length?'Pracuji · '+active.length+' úkolů':'Připraven'):'Pracovník se připojuje';
    if(panel.style.display==='none')return;
    panel.replaceChildren(el('h3','Moje úkoly','margin:0 0 12px;color:#73d7f2'));
    panel.append(el('p','Práce zůstává uložená i po zavření okna.','font-size:12px;color:#86a5b2'));
    if(!data.tasks.length)panel.append(el('p','Zatím nemám zadaný úkol.'));
    for(const task of data.tasks){
     const card=el('article',undefined,'border-top:1px solid #173c4c;padding:12px 0;overflow-wrap:anywhere');card.append(el('strong',task.goal),el('div',labels[task.status]||task.status,'font-size:12px;color:#76c9df;margin:5px 0'));
     if(task.answer)card.append(el('p',task.answer,'white-space:pre-wrap;font-size:12px;color:#b5cbd5'));
     if(task.pending){const p=task.pending,c=p.context||{};let description=(c.action||p.name)+': '+(c.label||'vybraný prvek');if(p.name==='browser_fill'||p.name==='desktop_fill')description+=' → '+p.arguments.text;card.append(el('p',description));if(c.title)card.append(el('p','Aplikace: '+c.title));if(c.url)card.append(el('p','Stránka: '+c.url));if(c.destination)card.append(el('p','Cíl: '+c.destination));}
     const actions=el('div',undefined,'display:flex;gap:6px;flex-wrap:wrap');
     if(task.status==='WAITING_APPROVAL')actions.append(button('Potvrdit tuto akci',()=>act(task.id,'approve')));
     if(['QUEUED','RUNNING','WAITING_APPROVAL'].includes(task.status))actions.append(button('Zastavit',()=>act(task.id,'cancel')));
     if(['PARTIAL','FAILED'].includes(task.status))actions.append(button('Pokračovat',()=>act(task.id,'resume')));
     actions.append(button('Výstupy',async()=>{
      const res=await fetch('/companion/tasks/'+task.id+'/artifacts',{headers}),files=await res.json();const list=el('div',undefined,'margin-top:8px');
      for(const f of files.files||[]){const a=el('a',f.name,'display:block;color:#80d7f2;padding:4px');a.href='/companion/artifacts/'+task.id+'/'+f.name.split('/').map(encodeURIComponent).join('/')+'?client='+encodeURIComponent(client);a.target='_blank';a.rel='noopener';list.append(a);}
      if(!(files.files||[]).length)list.textContent='Zatím nejsou vytvořené soubory.';card.append(list);
     }));card.append(actions);panel.append(card);
    }
    if(data.schedules.length){panel.append(el('h4','Naplánováno'));for(const s of data.schedules)panel.append(el('p',(s.enabled?'Aktivní: ':'Pozastaveno: ')+s.goal+' · '+new Date(s.next_run*1000).toLocaleString('cs-CZ')));}
   }catch(e){status.textContent='Připojení se obnovuje';}
  }
  refresh();setInterval(refresh,4000);
 });
})();
