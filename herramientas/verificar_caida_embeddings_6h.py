"""HTTP local ficticio: caída de embeddings, texto conservado y reindexación.

Usa el cliente HTTP real, no Ollama ni MCP. No detiene servicios del usuario.
"""
import argparse
from contextlib import closing
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from unittest.mock import patch


def main(salida):
    if salida.exists():raise ValueError('No sobrescribir la verificación anterior.')
    salida.parent.mkdir(parents=True,exist_ok=True);terminar=threading.Event();peticiones=[];modo={'caido':True}
    class Servidor(ThreadingHTTPServer):daemon_threads=True;block_on_close=False
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self,*_a):pass
        def do_POST(self):
            raw=self.rfile.read(min(20000,int(self.headers.get('Content-Length','0'))));peticiones.append(hashlib.sha256(raw).hexdigest())
            if modo['caido']:terminar.wait(10);return
            raw=json.dumps({'embeddings':[[1.,0.]]}).encode()
            try:self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
    resultados=[]
    def comprobar(nombre,valor,detalle=None):resultados.append({'prueba':nombre,'ok':bool(valor),'detalle':detalle})
    with tempfile.TemporaryDirectory(prefix='jarvis-embedding-http-') as tmp,Servidor(('127.0.0.1',0),Manejador) as servidor:
        hilo=threading.Thread(target=servidor.serve_forever,daemon=True);hilo.start()
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0');trabajo=Path(tmp,'trabajo');trabajo.mkdir()
        import tandas_documentales as T
        import cliente_ollama as O
        paths=[trabajo/'uno.txt',trabajo/'dos.txt']
        for i,p in enumerate(paths):p.write_text(f'MARCADOR_HTTP_{i} '+('detalle ficticio '*300))
        originales=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        try:
            with patch.object(O,'BASE',f'http://127.0.0.1:{servidor.server_port}'):
                inicio=time.monotonic();d=T.indexar(T.crear(paths)['id'],True);segundos=time.monotonic()-inicio
                comprobar('texto_disponible_tras_espera_http',all(a.get('caracteres_indexados',0)>0 and a['estado']=='parcial' for a in d['archivos']))
                comprobar('espera_acotada_en_servidor_sin_cabeceras',segundos<8,{'segundos':round(segundos,4),'limite_peticion_s':5})
                comprobar('un_intento_logico_con_dos_intentos_http',len(peticiones)==2,len(peticiones))
                antes=len(peticiones);r=T.buscar(d['id'],'MARCADOR_HTTP_1',presupuesto=6000)
                comprobar('consulta_textual_sin_repetir_http',len(peticiones)==antes and any('MARCADOR_HTTP_1' in t['texto'] for t in r['trozos']))
                with closing(sqlite3.connect(T.RAIZ/'trozos.sqlite')) as db:trozos=db.execute('SELECT count(*) FROM trozos').fetchone()[0]
                modo['caido']=False;terminar.set();final=T.indexar(d['id'],True)
                with closing(sqlite3.connect(T.RAIZ/'trozos.sqlite')) as db:
                    despues=db.execute('SELECT count(*) FROM trozos').fetchone()[0];faltantes=db.execute('SELECT count(*) FROM trozos WHERE vector IS NULL').fetchone()[0]
                comprobar('reindexacion_completa_sin_duplicar',final['estado']=='indexado' and despues==trozos and faltantes==0,{'trozos_antes':trozos,'trozos_despues':despues,'vectores_pendientes':faltantes})
                comprobar('originales_intactos',originales==[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths])
        finally:terminar.set();servidor.shutdown();hilo.join(2)
    dato={'resultados':resultados,'alcance':'Cliente HTTP y lectores reales, servidor de embeddings ficticio temporal. Sin Ollama, MCP, nube ni archivos personales. El límite observado corresponde a un servidor sin cabeceras; no prueba cancelación inmediata ni cualquier patrón de red.'}
    salida.write_text(json.dumps(dato,ensure_ascii=False,indent=2)+'\n');salida.chmod(0o600);print(json.dumps(dato,ensure_ascii=False))
    return 0 if all(x['ok'] for x in resultados) else 1


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--salida',type=Path,required=True);a=ap.parse_args();raise SystemExit(main(a.salida))
