"""Fallo HTTP controlado y recuperación con Ollama real sobre una tanda ficticia.

No detiene el servidor real. No usa MCP, nube ni herramientas de escritura.
El primer turno usa un servidor falso; los posteriores se auditan por separado.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
RAIZ=BASE/'registros/reportes/mejora_6h_20261014/reintento_real'
CASOS=[
    {'id':'FALLO_01','pedido':'Según el anexo 3 adjunto, dime solo el identificador literal y el monto aprobado; cita el archivo. Sin herramientas ni acciones.','esperado_error':True},
    {'id':'RETOMA_02','pedido':'reintenta','oro':['ANEXO_TRES_73','473','anexo3.md']},
    {'id':'ANEXO_03','pedido':'y en el anexo 3 qué dice? conserva el identificador y el monto exactos y cita el archivo. Una frase, sin herramientas ni acciones.','oro':['ANEXO_TRES_73','473','anexo3.md']},
]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ronda',required=True);a=ap.parse_args()
    if not a.ronda.replace('_','').isalnum():raise ValueError('Ronda inválida.')
    RAIZ.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(CASOS,ensure_ascii=False,indent=2)+'\n').encode();corpus=RAIZ/'corpus.json'
    if corpus.exists() and corpus.read_bytes()!=raw:raise ValueError('El corpus congelado cambió.')
    if not corpus.exists():corpus.write_bytes(raw)
    sha=hashlib.sha256(raw).hexdigest();corpus.with_suffix('.sha256').write_text(sha+'\n')
    destino=RAIZ/(a.ronda+'.json')
    if destino.exists():raise ValueError('Se conserva la ronda anterior; usa otro nombre.')
    with tempfile.TemporaryDirectory(prefix='jarvis-retoma-real-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0')
        trabajo=Path(tmp,'trabajo');trabajo.mkdir()
        import jarvis_agente as J
        import tandas_documentales as T
        J.AJUSTES.update(num_ctx=8192,num_predict=256,timeout_modelo=120)
        J.OPCIONES.update(num_ctx=8192,num_predict=256,temperature=0)
        caso=trabajo/'caso.md';caso.write_text('Caso ficticio de tienda con 4 accesos. Los datos aprobados del anexo 3 están en anexo3.md.')
        anexo=trabajo/'anexo3.md';anexo.write_text('Anexo 3. Identificador literal ANEXO_TRES_73. Monto aprobado 473 CLP. Debe conservarse exacto.\n')
        tanda=T.indexar(T.crear([caso,anexo])['id'],False)
        estado={'_tanda_documentos':tanda['id']};historial=[{'role':'system','content':J.SISTEMA}]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length','0')));self.server.llamadas+=1
                raw=b'{"error":"Fallo HTTP controlado del arnes sintetico"}'
                self.send_response(500);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        servidor=ThreadingHTTPServer(('127.0.0.1',0),Handler);servidor.daemon_threads=True;servidor.llamadas=0
        hilo=threading.Thread(target=servidor.serve_forever,daemon=True);hilo.start()
        anterior=J.O.BASE;transporte_real=J.O.solicitar;filas=[];nube=[];acciones=[];permisos=[]
        def bloquear(nombre,*args,**kw):acciones.append(nombre);return {'ok':False,'error':'Herramientas bloqueadas en este arnés sintético.'}
        def denegar(texto):permisos.append(texto);return False
        def externa(*args,**kw):nube.append(True);raise AssertionError('IA externa bloqueada.')
        try:
            for i,c in enumerate(CASOS):
                llamadas=[]
                def auditar(ruta,cuerpo=None,**kw):
                    respuesta=transporte_real(ruta,cuerpo,**kw)
                    if ruta=='/api/chat':llamadas.append({'mensajes':cuerpo.get('messages'),
                        'tokens_entrada':respuesta.get('prompt_eval_count'),'tokens_salida':respuesta.get('eval_count')})
                    return respuesta
                J.O.BASE=f'http://127.0.0.1:{servidor.server_port}' if i==0 else anterior
                p=c['pedido'];historial[0]['content']=J.prompt_para_turno(p,estado);inicio=time.monotonic()
                with patch.object(J.IA.P,'opciones',return_value={'configurado':False,'automatico':False,'timeout_local':35,'preferido':''}),patch.object(J.IA,'preguntar_externa',side_effect=externa),patch.object(J,'ejecutar_herramienta',side_effect=bloquear),patch.object(J.O,'solicitar',side_effect=auditar):
                    manejado,texto=J.comando(p,historial,estado,bloquear,J.SISTEMA)
                    if not manejado:
                        historial.append({'role':'user','content':p})
                        texto=J.responder_con_respaldo(historial,J.enviar_a_ollama,denegar,estado,mostrar=lambda _:None)
                fallido=estado.get('_hilo_conversacion',{}).get('fallido')
                presentes=[oro for oro in c.get('oro',[]) if oro in texto]
                correcto=bool(fallido and 'reintenta' in texto and not llamadas) if i==0 else len(presentes)==len(c['oro']) and bool(llamadas) and not fallido
                correcto=correcto and estado.get('_tanda_documentos')==tanda['id'] and not nube and not acciones and not permisos
                fila={'id':c['id'],'pedido_visible':p,'respuesta':texto,'ok':correcto,'segundos':round(time.monotonic()-inicio,3),
                      'fuente_respuesta':'HTTP falso' if i==0 else 'Ollama real','literales_presentes':presentes,'llamadas_reales':llamadas,
                      'tanda_conservada':estado.get('_tanda_documentos')==tanda['id'],'fallido_pendiente':bool(fallido)}
                filas.append(fila);print(json.dumps({k:fila[k] for k in ('id','ok','segundos','fuente_respuesta')},ensure_ascii=False),flush=True)
        finally:J.O.BASE=anterior;servidor.shutdown();servidor.server_close();hilo.join(2)
        reporte={'ronda':a.ronda,'corpus_sha256':sha,'casos':filas,'correctos':sum(x['ok'] for x in filas),
                 'http_falso_solicitudes':servidor.llamadas,'escrituras_herramientas':acciones,'solicitudes_permiso':permisos,'nube':len(nube),
                 'modelo':J.MODELO,'contexto':8192,'salida_maxima':256,
                 'alcance':'Fallo HTTP500 inducido con servidor falso y retoma posterior con Ollama real, sin detener servicios ni usar datos personales. No reproduce la causa histórica desconocida del fallo de Diego.'}
        destino.write_text(json.dumps(reporte,ensure_ascii=False,indent=2)+'\n');os.chmod(destino,0o600)
        return 0 if all(x['ok'] for x in filas) else 1


if __name__=='__main__':raise SystemExit(main())
