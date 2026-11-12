"""Local CLI for the isolated RealJarvis v2 prototype, not production."""
import argparse,json
from pathlib import Path
from task_engine import Engine,ROOT
from knowledge_store import NoteStore

def main():
    parser=argparse.ArgumentParser(description='RealJarvis v2 isolated task runner')
    sub=parser.add_subparsers(dest='command',required=True)
    create=sub.add_parser('create');create.add_argument('kind');create.add_argument('goal');create.add_argument('--run',action='store_true')
    for kind in ('status','run','cancel','approve'):
        sub.add_parser(kind).add_argument('id')
    sub.add_parser('remember').add_argument('text')
    sub.add_parser('recall').add_argument('query')
    sub.add_parser('forget-note').add_argument('id')
    opts=parser.parse_args()
    if opts.command in ('remember','recall','forget-note'):
        notes=NoteStore(ROOT/'BrainCore'/'user_notes.sqlite')
        if opts.command=='remember': out=notes.remember(opts.text)
        elif opts.command=='recall': out=notes.search(opts.query)
        else: out={'deleted':notes.forget(opts.id)}
        print(json.dumps(out,ensure_ascii=True,sort_keys=True));return
    db=ROOT/'BrainCore'/'tasks.sqlite'
    engine=Engine(db)
    if opts.command=='create':
        state=engine.create(opts.kind,opts.goal)
        if opts.run:state=engine.run(state['id'])
    elif opts.command=='status':state=engine.store.get(opts.id)
    elif opts.command=='run':state=engine.run(opts.id)
    elif opts.command=='cancel':state=engine.cancel(opts.id)
    else:state=engine.approve(opts.id)
    print(json.dumps(state,ensure_ascii=True,sort_keys=True))
if __name__=='__main__':main()