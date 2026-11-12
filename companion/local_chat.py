"""Opt-in isolated local-only conversational LLM. NEVER executes tools."""
from __future__ import annotations
import json,urllib.request
MODEL='qwen3.5:4b-q4_K_M'
ENDPOINT='http://127.0.0.1:11434/api/chat'
PREFIXES=('/local ','lokálně:','lokalne:')
MAX_PROMPT=700

class LocalModelUnavailable(Exception):
    pass

def extract_request(text):
    if not isinstance(text,str):return None
    text=text.strip()
    lower=text.casefold()
    for prefix in PREFIXES:
        if lower.startswith(prefix):
            return text[len(prefix):].strip()
    return None

def answer_local(text):
    if not isinstance(text,str) or not 1<=len(text.strip())<=MAX_PROMPT:
        raise ValueError('Prompt must have 1-700 characters')
    body={'model':MODEL,'stream':False,'think':False,'keep_alive':'2m',
      'options':{'num_predict':260,'temperature':0.2},
      'messages':[{'role':'system','content':
        'Jsi experimentální lokální chat v češtině. Nemáš internet, externí nástroje, '
        'přístup k souborům ani právo vykonat příkaz. Netvrď, že jsi něco provedl nebo '
        'ověřil. Když uživatel chce vykonání, řekni, že v tomto režimu můžeš jen poradit. '
        'Odpovídej česky, přímo, stručně a bez interních úvah.'},
        {'role':'user','content':text.strip()}]}
    req=urllib.request.Request(ENDPOINT,data=json.dumps(body,ensure_ascii=False).encode('utf-8'),
         headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=55) as rsp:
            data=json.load(rsp)
    except (OSError,ValueError) as exc:
        raise LocalModelUnavailable('Ollama offline, timeout or invalid reply') from exc
    answer=data.get('message',{}).get('content')
    if not isinstance(answer,str) or not answer.strip():
        raise LocalModelUnavailable('Empty model response')
    return answer.strip()[:2000]