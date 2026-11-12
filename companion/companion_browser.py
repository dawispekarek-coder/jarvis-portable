"""Bounded Playwright browser with observed element references and public-only requests."""
from __future__ import annotations
import importlib.util,json,hashlib,socket,ipaddress,time,uuid
from pathlib import Path
from urllib.parse import urlparse
from companion_registry import ToolError

def public_destination(url):
 try:p=urlparse(url);host=(p.hostname or '').lower();port=p.port
 except (ValueError,TypeError) as exc:raise ToolError('invalid_url') from exc
 if p.scheme!='https' or not host or p.username or p.password or port not in (None,443) or '\\' in url:raise ToolError('public_https_only')
 if host=='localhost' or host.endswith(('.local','.internal','.lan','.home')):raise ToolError('private_destination')
 try:addresses={ipaddress.ip_address(x[4][0].split('%')[0]) for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)}
 except (ValueError,OSError) as exc:raise ToolError('dns_unavailable') from exc
 if not addresses or any(not x.is_global for x in addresses):raise ToolError('private_destination')
 return url

def validate_approval(expected,observed):
 if expected!=observed:raise ToolError('approved_document_or_action_changed')

class Browser:
 def __init__(self,profile,out):
  self.profile=Path(profile);self.out=Path(out);self.available=bool(importlib.util.find_spec('playwright'))
  self.context=None;self.page=None;self.driver=None;self.refs={};self.url='';self.cache={};self.document_id=uuid.uuid4().hex;self.state_hash=''
 def _start(self):
  if self.context:return
  if not self.available:raise ToolError('playwright_not_installed')
  from playwright.sync_api import sync_playwright
  self.profile.mkdir(parents=True,exist_ok=True);self.out.mkdir(parents=True,exist_ok=True)
  self.driver=sync_playwright().start()
  self.context=self.driver.chromium.launch_persistent_context(str(self.profile),channel='msedge',headless=True,accept_downloads=False,service_workers='block',permissions=[],viewport={'width':1200,'height':850},args=['--disable-background-networking'])
  def guard(route):
   try:
    u=urlparse(route.request.url)
    if u.scheme in ('data','blob'):route.continue_();return
    key=(u.scheme,u.hostname,u.port)
    if self.cache.get(key,0)<time.time():public_destination(route.request.url);self.cache[key]=time.time()+20
    route.continue_()
   except Exception:route.abort()
  self.context.route('**/*',guard)
  if hasattr(self.context,'route_web_socket'):self.context.route_web_socket('**/*',lambda ws:ws.close())
  self.page=self.context.pages[0] if self.context.pages else self.context.new_page()
  self.page.set_default_timeout(12000)
 def open(self,url):
  public_destination(url);self._start();self.document_id=uuid.uuid4().hex;self.page.goto(url,wait_until='domcontentloaded',timeout=20000)
  public_destination(self.page.url);return self.snapshot()
 def snapshot(self):
  self.url=self.page.url
  elements=self._elements()
  text=self.page.locator('body').inner_text()[:6500]
  self.state_hash=hashlib.sha256(json.dumps([self.url,elements,text],sort_keys=True).encode()).hexdigest()
  self.refs={}
  for e in elements:
   if not e['visible']:continue
   ref='e'+hashlib.sha256((self.document_id+'|'+json.dumps(e,sort_keys=True)).encode()).hexdigest()[:14]
   self.refs[ref]=e
  data={'url':self.url,'title':self.page.title(),'text':text,'document_id':self.document_id,'state_hash':self.state_hash,'elements':[{'ref':ref,**e} for ref,e in self.refs.items()],'verified':True}
  (self.out/'browser_snapshot.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
  self.page.screenshot(path=str(self.out/'browser.png'),full_page=False)
  return data
 def _elements(self):
  return self.page.locator('a,button,input,textarea,select,[role="button"]').evaluate_all('''els=>els.slice(0,100).map((e,i)=>({index:i,tag:e.tagName.toLowerCase(),name:(e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||e.getAttribute('name')||'').trim().slice(0,100),type:e.getAttribute('type')||'',href:e.href||'',form_action:e.form?e.form.action:'',value:e.type==='password'?'':(e.value||''),visible:!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)}))''')
 def action_context(self,name,args):
  self._locate(args['ref'],args['document_id'],args['state_hash'])
  e=self.refs[args['ref']]
  return {'url':self.url,'label':e['name'],'destination':e.get('href') or e.get('form_action') or self.url,'action':'Vyplnit pole' if name=='browser_fill' else 'Kliknout na prvek','value':args.get('text',''),'document_id':self.document_id,'state_hash':self.state_hash}
 def _locate(self,ref,document_id=None,state_hash=None):
  if not self.page:
   raise ToolError('browser_session_lost_observe_again')
  if ref not in self.refs:raise ToolError('unknown_or_stale_reference')
  elements=self._elements();text=self.page.locator('body').inner_text()[:6500]
  observed_hash=hashlib.sha256(json.dumps([self.page.url,elements,text],sort_keys=True).encode()).hexdigest()
  validate_approval({'document_id':document_id,'state_hash':state_hash},{'document_id':self.document_id,'state_hash':observed_hash})
  expected=self.refs[ref]
  if expected['type'].casefold() in ('password','file'):raise ToolError('sensitive_input_not_supported')
  item=self.page.locator('a,button,input,textarea,select,[role="button"]').nth(expected['index'])
  current=item.evaluate("e=>({tag:e.tagName.toLowerCase(),name:(e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||e.getAttribute('name')||'').trim().slice(0,100)})")
  if current['tag']!=expected['tag'] or current['name']!=expected['name']:raise ToolError('element_changed_observe_again')
  return item
 def click(self,ref,document_id=None,state_hash=None):
  item=self._locate(ref,document_id,state_hash);item.click();self.page.wait_for_timeout(250);public_destination(self.page.url);self.document_id=uuid.uuid4().hex
  return self.snapshot()
 def fill(self,ref,text,document_id=None,state_hash=None):
  item=self._locate(ref,document_id,state_hash);item.fill(text)
  if item.input_value()!=text:raise ToolError('field_value_not_verified')
  return {**self.snapshot(),'field_value_verified':True}
 def close(self):
  if self.context:self.context.close()
  if self.driver:self.driver.stop()
  self.context=None;self.page=None;self.driver=None
