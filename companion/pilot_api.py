"""RealJarvis V2 pilot API, strictly loopback, sandbox tasks only."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path
import json
from task_engine import Engine,ROOT
ENGINE=Engine(ROOT/'BrainCore'/'tasks.sqlite')
PORT=7352

class Api(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):
        pass
    def respond(self,status:int,body:dict):
        raw=json.dumps(body,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/health':
            return self.respond(200,{'status':'online','service':'RealJarvis V2 pilot',
                       'production_attached':False,'coding_agent_enabled':False,'tool_scope':['arithmetic','lua_audit']})
        if path.startswith('/tasks/') and len(path.split('/'))==3:
            try:return self.respond(200,ENGINE.store.get(path.split('/')[-1]))
            except KeyError:return self.respond(404,{'error':'not_found'})
        return self.respond(404,{'error':'not_found'})
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=4096:return self.respond(413,{'error':'invalid_body_size'})
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):return self.respond(400,{'error':'json_object_required'})
        except (ValueError,TypeError):return self.respond(400,{'error':'invalid_json'})
        if path=='/tasks':
            kind=data.get('kind')
            goal=data.get('goal')
            if kind not in {'arithmetic','lua_audit','coding_proposal'} or not isinstance(goal,str) or not 1<=len(goal)<=1200:
                return self.respond(400,{'error':'invalid_task'})
            task=ENGINE.create(kind,goal)
            if data.get('run') is True:task=ENGINE.run(task['id'])
            return self.respond(201,task)
        if path.startswith('/tasks/') and path.endswith('/cancel'):
            task_id=path.split('/')[-2]
            try:return self.respond(200,ENGINE.cancel(task_id))
            except KeyError:return self.respond(404,{'error':'not_found'})
        return self.respond(404,{'error':'not_found'})

if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',PORT),Api)
    server.daemon_threads=True
    print('REALJARVIS_V2_PILOT_127.0.0.1:7352',flush=True)
    server.serve_forever(poll_interval=0.5)