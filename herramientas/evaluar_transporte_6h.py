"""Servidor falso local: fallos reales de HTTP, sin herramientas ni nube."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

CASOS=[{'id':n,'modo':n,'recuperar':n in {'http500','cierre'}}
       for n in ['http500','cierre','vacia','timeout','json','permanente500','http400','tamano','secreto']]
DESTINO=Path(__file__).resolve().parents[1]/'registros/reportes/mejora_6h_20261014'

def congelar():
    DESTINO.mkdir(parents=True,exist_ok=True)
    p=DESTINO/'transporte_corpus.json'
    raw=(json.dumps(CASOS,ensure_ascii=False,indent=2)+'\n').encode()
    if p.exists() and p.read_bytes()!=raw:raise ValueError('El corpus ya está congelado y es distinto.')
    p.write_bytes(raw);(DESTINO/'transporte_corpus.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n')

def evaluar(O,modo):
    class Servidor(ThreadingHTTPServer):daemon_threads=True
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length',0)))
            self.server.llamadas+=1;primera=self.server.llamadas==1
            if modo=='cierre' and primera:
                self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
            if modo=='timeout' and primera:time.sleep(1)
            status=500 if (modo=='http500' and primera or modo in {'permanente500','secreto'}) else 400 if modo=='http400' else 200
            dato={'error':'falla sintética api_key=NO_IMPRIMIR_ABC'} if status!=200 else {'message':{'role':'assistant','content':'' if modo=='vacia' and primera else 'RESPUESTA_OK'},'done':True}
            raw=b'{' if modo=='json' and primera else b' '*2_000_001 if modo=='tamano' else json.dumps(dato).encode()
            self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers()
            try:self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
    s=Servidor(('127.0.0.1',0),Handler);s.llamadas=0
    th=threading.Thread(target=s.serve_forever,daemon=True);th.start();anterior=O.BASE;O.BASE=f'http://127.0.0.1:{s.server_port}'
    t=time.monotonic();error='';r=None
    try:
        try:r=O.solicitar('/api/chat',{'model':'sintetico','messages':[]},timeout=.7)
        except ConnectionError as e:error=str(e)
        segundos=time.monotonic()-t
    finally:O.BASE=anterior;s.shutdown();s.server_close();th.join(1)
    recuperar=modo in {'http500','cierre'}
    ok=bool(r and r.get('message',{}).get('content')=='RESPUESTA_OK') if recuperar else bool(error)
    if recuperar:ok=ok and s.llamadas==2
    if modo in {'http400','tamano','vacia','timeout','json'}:ok=ok and s.llamadas==1
    if modo in {'permanente500','secreto'}:ok=ok and s.llamadas<=2
    return {'id':modo,'ok':ok and segundos<.95 and 'NO_IMPRIMIR_ABC' not in error,'respuesta':r,'error':error,'llamadas':s.llamadas,'segundos':round(segundos,3),'tipo':'servidor falso HTTP local; no inferencia real'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--ronda',required=True);p.add_argument('--original',action='store_true');a=p.parse_args();congelar()
    with tempfile.TemporaryDirectory(prefix='jarvis-transporte-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1')
        if a.original:
            original=Path(tmp)/'cliente_original.py'
            original.write_bytes(subprocess.check_output(['git','show','db9bc66:herramientas/cliente_ollama.py'],cwd=Path(__file__).resolve().parents[1]))
            spec=importlib.util.spec_from_file_location('cliente_original',original);O=importlib.util.module_from_spec(spec);spec.loader.exec_module(O)
        else:import cliente_ollama as O
        resultados=[evaluar(O,c['modo']) for c in CASOS]
        (DESTINO/(a.ronda+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in resultados))
        print(json.dumps({'ronda':a.ronda,'correctos':sum(x['ok'] for x in resultados),'total':len(resultados),'fallos':[x['id'] for x in resultados if not x['ok']]}))

if __name__=='__main__':main()
