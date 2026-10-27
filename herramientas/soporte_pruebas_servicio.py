"""Servidor HTTP sintético para comprobar vida y propiedad de procesos locales."""
import os
from pathlib import Path
import socket
import sys
import time

def puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));return s.getsockname()[1]

def ejecutable(raiz,demora=0,fallar=False):
    p=Path(raiz)/'ollama-falso'
    p.write_text('#!'+sys.executable+"""
import json,os,sys,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
time.sleep("""+str(float(demora))+""")
if """+str(bool(fallar))+""":sys.exit(2)
url=urlsplit(os.environ['OLLAMA_HOST'])
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  d={'version':'sintetica'} if self.path=='/api/version' else {'models':[]}
  self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(d).encode())
servidor=ThreadingHTTPServer((url.hostname,url.port),H)
p=Path(os.environ['HOME']);p.mkdir(parents=True,exist_ok=True)
(p/'arranque.json').write_text(json.dumps({'pid':os.getpid(),'cloud':os.environ.get('OLLAMA_NO_CLOUD'),'secretos_presentes':any(k in os.environ for k in ('OPENCODE_API_KEY','ZEN_API_KEY','SECRET_LAB')),'host':url.hostname}))
servidor.serve_forever(poll_interval=.05)
""")
    p.chmod(0o700);return str(p)

def esperar(condicion,timeout=5):
    fin=time.monotonic()+timeout
    while time.monotonic()<fin:
        if condicion():return True
        time.sleep(.04)
    return bool(condicion())
