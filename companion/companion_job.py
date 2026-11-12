"""One owned process per durable task; safe to terminate on a user Stop."""
import sys,argparse
from companion_store import Store
from companion_tools import build_registry
from companion_agent import Agent,Ollama
import companion_settings as settings
def main():
 parser=argparse.ArgumentParser();parser.add_argument('task_id');parser.add_argument('--db',default=str(settings.STATE));args=parser.parse_args()
 store=Store(args.db);task=store.get(args.task_id)
 if task['status']!='RUNNING':return
 registry=build_registry(store,task,settings)
 Agent(store,registry,Ollama(settings),task,hold_approvals=True).run()
if __name__=='__main__':main()
