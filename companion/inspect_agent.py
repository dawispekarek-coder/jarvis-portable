"""Bounded, read-only ForeverRoute goal planner with independent evidence.
Model never chooses shell commands; execution is fixed to three audited tools.
"""
from __future__ import annotations
import hashlib,re,subprocess,time,uuid
from pathlib import Path
from typing import TypedDict
from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.sqlite import SqliteSaver
import project_tools
from task_engine import ROOT,LUA,FIXTURE

TEST=FIXTURE/'tests'/'now_card_objectives.lua'
SOURCE=FIXTURE/'ForeverRoute_UIv2.lua'
CHECKPOINT_DB=ROOT/'BrainCore'/'inspections.graph.sqlite'
INTENTS=('prover','prověř','projed','zkontrol','zjisti','analyz','audit','otest','chyby','oprav','najdi problém','najdi problem','prohledej')
PROJECT_WORDS=('foreverroute','planner','routu','routy','lua addon','lua kód','lua kod')
SYMBOL=re.compile(r'\b(FR_[A-Za-z_][A-Za-z0-9_]{2,70})\b')
class InspectState(TypedDict,total=False):
    goal:str
    intent:str
    steps:list[str]
    symbol:str
    git:dict
    matches:dict
    lua:dict
    verified:bool
    error:str

def extract_goal(goal:str)->bool:
    if not isinstance(goal,str) or not 6<=len(goal)<=950:return False
    lower=goal.casefold()
    return (any(p in lower for p in PROJECT_WORDS) and
            any(v in lower for v in INTENTS))

def plan(s:InspectState)->InspectState:
    raw=s['goal'];lower=raw.casefold()
    symbol_match=SYMBOL.search(raw)
    steps=['git_status']
    if symbol_match:steps.append('lua_symbol_search')
    if any(k in lower for k in ('test','chyb','oprav','audit','lua','kontrol','prověř','prover')):
        steps.append('isolated_lua_regression')
    return {**s,'intent':'review_only','steps':steps,
            'symbol':symbol_match.group(1) if symbol_match else ''}

def _hash(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def native_audit()->dict:
    before=(_hash(SOURCE),_hash(TEST))
    run=subprocess.run([str(LUA),str(TEST),str(FIXTURE)],cwd=FIXTURE,
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20)
    after=(_hash(SOURCE),_hash(TEST))
    combined=run.stdout[-1400:]
    summary=re.search(r'(\d+)\s+checks,\s*(\d+)\s+failed',combined)
    if not summary:
        raise RuntimeError('native_test_summary_missing')
    return {'checks':int(summary.group(1)),'failures':int(summary.group(2)),
        'return_code':run.returncode,'fixture_unchanged':before==after,
        'fixture_only':True,'tail':combined[-350:]}

def execute(s:InspectState)->InspectState:
    if s.get('intent')!='review_only':return {**s,'error':'invalid_intent'}
    before=project_tools.status()
    result={**s,'git':before}
    if 'lua_symbol_search' in s['steps']:
        result['matches']=project_tools.search_lua(s['symbol'])
    if 'isolated_lua_regression' in s['steps']:
        result['lua']=native_audit()
    after=project_tools.status()
    result['verified']=(before['commit']==after['commit'] and
        before['branch']==after['branch'] and
        before['changed_count']==after['changed_count'] and
        (result.get('lua') is None or result['lua']['fixture_unchanged']))
    if not result['verified']:result['error']='source_changed_during_review'
    return result

def verify(s:InspectState)->InspectState:
    if not s.get('git') or not s.get('verified'):
        return {**s,'verified':False,'error':s.get('error','evidence_missing')}
    if s['intent']!='review_only' or not s.get('steps'):
        return {**s,'verified':False,'error':'plan_not_read_only'}
    return s

def graph():
    g=StateGraph(InspectState)
    g.add_node('plan',plan)
    g.add_node('execute',execute)
    g.add_node('verify',verify)
    g.add_edge(START,'plan')
    g.add_edge('plan','execute')
    g.add_edge('execute','verify')
    g.add_edge('verify',END)
    return g

def inspect(goal:str)->dict:
    if not extract_goal(goal):raise ValueError('unsupported_project_goal')
    try:
        with SqliteSaver.from_conn_string(str(CHECKPOINT_DB)) as saver:
            compiled=graph().compile(checkpointer=saver)
            state=compiled.invoke({'goal':goal},
                config={'configurable':{'thread_id':str(uuid.uuid4())}})
    except (subprocess.SubprocessError,OSError,ValueError,RuntimeError) as exc:
        raise RuntimeError('read_only_inspection_unavailable') from exc
    if not state.get('verified'):raise RuntimeError('unverified_inspection')
    return state

def format_report(s:dict)->str:
    git=s['git']
    lines=['Jarvis provedl ověřenou, POUZE ČTECÍ kontrolu ForeverRoute.',
       f"Git: {git['branch']} / {git['commit']} ({git['date']})",
       'Pracovní strom: '+('čistý' if git['clean'] else
           'změněné položky: '+str(git['changed_count']))]
    if 'matches' in s:
        matches=s['matches']['matches']
        lines.append('Lua symbol '+s['symbol']+': '+str(len(matches))+' nalezených výskytů.')
        lines.extend(f"- {m['file']}:{m['line']} {m['excerpt']}" for m in matches[:4])
    if 'lua' in s:
        lua=s['lua']
        lines.append(f"IZOLOVANÝ TEST (nikoli hra): {lua['checks']} kontrol, "
          f"{lua['failures']} chyb; původní testovací soubory nezměněny.")
    lines.append('Vykonané kroky: '+', '.join(s['steps']))
    lines.append('Oprava ani zápis do produkčního addonu nebyly provedeny.')
    return '\n'.join(lines)
