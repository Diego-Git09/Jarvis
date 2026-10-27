"""Escalado local real sobre preguntas fallidas; no combina sus porcentajes."""
import os,json,tempfile,time
from pathlib import Path
from unittest.mock import patch
RAIZ=Path(__file__).resolve().parents[1]
REPORTES=RAIZ/'registros/reportes/ronda_mixta_20261020'

def main():
    origen=[json.loads(l) for l in (REPORTES/'seleccion_40_r4.jsonl').read_text().splitlines()]
    destino=REPORTES/'escalado_real_r1.jsonl'
    if destino.exists():raise ValueError('No sobrescribir resultados originales')
    with tempfile.TemporaryDirectory(prefix='jarvis-escalado-real-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1')
        import cliente_ollama as O,configuracion_jarvis as C
        from interfaz_local import comando_local
        ajustes=C.validar(dict(C.DEFAULT,seleccion_modelo='automatico',keep_alive='0'))
        real=O.solicitar;llamadas=[]
        def solicitar(ruta,cuerpo=None,**kw):
            with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'leer',return_value=(ajustes,'')):
                r=real(ruta,cuerpo,**kw)
            if ruta=='/api/chat':llamadas.append({'pedido':cuerpo,'respuesta_original_api':r})
            return r
        with patch.object(O,'solicitar',side_effect=solicitar),destino.open('x') as log:
            for previo in (x for x in origen if x['id'] in {26,28,36,38,40}):
                estado={'_ultima_decision_modelo':previo['decision']};llamadas.clear()
                h=[{'role':'user','content':previo['pregunta']},{'role':'assistant','content':previo['respuesta_original_jarvis']}]
                inicio=time.monotonic()
                ok,t=comando_local('/escalar',h,estado,lambda _:False,ajustes,lambda:None,None)
                fila={'id_base':previo['id'],'base':'seleccion_40_r4.jsonl','historia':'reconstruida con el texto visible real, sin acciones; no es reproducción de herramientas','pregunta':previo['pregunta'],'segundos':time.monotonic()-inicio,'respuesta_original_jarvis':t,'decision':estado.get('_ultima_decision_modelo'),'llamadas_reales':list(llamadas),'sin_herramientas_en_payload':all(not x['pedido'].get('tools') for x in llamadas)}
                log.write(json.dumps(fila,ensure_ascii=False)+'\n');log.flush();print(json.dumps({'id_base':fila['id_base'],'segundos':fila['segundos'],'decision':fila['decision']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
