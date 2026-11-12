"""One typed catalog drives model calls, permission decisions and UI self-knowledge."""
from __future__ import annotations
import json,time
class ToolError(ValueError):pass

def validate_schema(value,schema,path='arguments'):
 kind=schema.get('type')
 valid={'object':lambda:isinstance(value,dict),'string':lambda:isinstance(value,str),'integer':lambda:type(value) is int,'number':lambda:type(value) in (int,float),'boolean':lambda:type(value) is bool,'array':lambda:isinstance(value,list)}
 if kind not in valid or not valid[kind]():raise ToolError(path+': wrong type')
 if 'enum' in schema and value not in schema['enum']:raise ToolError(path+': invalid choice')
 if kind=='object':
  props=schema.get('properties',{})
  if any(k not in value for k in schema.get('required',[])):raise ToolError(path+': missing argument')
  if schema.get('additionalProperties') is False and any(k not in props for k in value):raise ToolError(path+': unknown argument')
  for key,entry in value.items():
   if key in props:validate_schema(entry,props[key],path+'.'+key)
 if kind=='string' and not schema.get('minLength',0)<=len(value)<=schema.get('maxLength',20000):raise ToolError(path+': invalid length')
 if kind in ('number','integer') and not schema.get('minimum',-1e100)<=value<=schema.get('maximum',1e100):raise ToolError(path+': out of range')
 if kind=='array':
  if len(value)>schema.get('maxItems',30):raise ToolError(path+': too many entries')
  for v in value:validate_schema(v,schema['items'],path+'[]')

class Registry:
 def __init__(self):self.entries={};self.observed={}
 def add(self,name,description,parameters,function,*,verifier,write=False,approval=False,available=True):
  self.entries[name]={'name':name,'description':description,'parameters':parameters,'function':function,'verifier':verifier,'write':write,'approval':approval,'available':bool(available)}
 def validate(self,name,args):
  if name not in self.entries:raise ToolError('unknown_tool:'+str(name))
  t=self.entries[name]
  if not t['available']:raise ToolError('tool_unavailable:'+name)
  validate_schema(args,t['parameters']);return t
 def execute(self,name,args):
  t=self.validate(name,args);start=time.time()
  try:
   value=t['function'](**args);verified=bool(t['verifier'](value))
   result={'ok':verified,'verified':verified,'value':value,'tool':name}
  except ToolError:raise
  except Exception as exc:
   result={'ok':False,'verified':False,'error':type(exc).__name__+': '+str(exc)[:300],'tool':name}
  self.observed[name]={'ok':result['ok'],'at':time.time(),'seconds':round(time.time()-start,3)}
  return result
 def schemas(self):
  return [{'type':'function','function':{k:t[k] for k in ('name','description','parameters')}} for t in self.entries.values() if t['available']]
 def catalog(self):
  return [{**{k:t[k] for k in ('name','description','write','approval','available')},'last_check':self.observed.get(t['name'])} for t in self.entries.values()]

def obj(properties=None,required=None):return {'type':'object','properties':properties or {},'required':required if required is not None else list(properties or {}),'additionalProperties':False}
def text_schema(maximum=1200):return {'type':'string','minLength':1,'maxLength':maximum}
