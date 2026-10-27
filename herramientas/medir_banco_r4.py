"""60 preguntas nuevas o10 conversaciones reales locales; corpus congelado."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from contextlib import ExitStack
from unittest.mock import patch
from corpus_r4 import congelar,sesenta,conversaciones

DESTINO=Path(__file__).resolve().parents[1]/'registros/reportes/ronda4_20261021'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tipo',choices=['sesenta','continuidad'],required=True);ap.add_argument('--ronda',required=True);a=ap.parse_args()
    if not re.fullmatch('[a-z0-9_]+',a.ronda):raise ValueError('Nombre de ronda no válido')
    sha=congelar(DESTINO);salida=DESTINO/(a.tipo+'_'+a.ronda+'.jsonl')
    if salida.exists():raise ValueError('No sobrescribir las respuestas originales')
    with tempfile.TemporaryDirectory(prefix='jarvis-r4-medicion-') as temporal,ExitStack() as cierre:
        os.environ.update(JARVIS_DIR=temporal,JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0')
        from lecturas_prueba_r4 import iniciar
        leer_sensores,cerrar_sensores=iniciar(temporal)
        cierre.callback(cerrar_sensores)
        import jarvis_agente as J,cliente_ollama as O,configuracion_jarvis as C
        from interfaz_jarvis import comando
        from aislamiento_pruebas import verificar_previo
        aislamiento=verificar_previo(temporal,nativo=True,evidencias=DESTINO)
        ajustes=C.validar(dict(C.DEFAULT,seleccion_modelo='automatico',num_ctx=8192,num_predict=512,keep_alive='1m',timeout_modelo=240))
        J.AJUSTES.clear();J.AJUSTES.update(ajustes);J.OPCIONES.update(num_ctx=8192,num_predict=512)
        real=O.solicitar;llamadas=[];admisiones=[]
        def transporte(ruta,cuerpo=None,**kw):
            inicio=time.monotonic()
            try:
                with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'leer',return_value=(ajustes,'')):
                    r=real(ruta,cuerpo,**kw)
                if ruta=='/api/chat':llamadas.append({'modelo':cuerpo['model'],'respuesta_original_api':r,'segundos':time.monotonic()-inicio})
                return r
            except Exception as e:
                if ruta=='/api/chat':llamadas.append({'modelo':(cuerpo or {}).get('model'),'error':str(e),'segundos':time.monotonic()-inicio})
                raise
        def prohibido(*args,**kw):raise AssertionError('El banco no usa IA externa ni escribe recuerdos')
        import externo_zen as Z
        import control_recursos as R
        R.instantanea=leer_sensores
        R.termica=lambda:leer_sensores()['termica']
        comprobar_real=R.comprobar
        def comprobar_recursos(cliente,cuerpo,plazo_fin=None):
            inicio=time.monotonic()
            dato={'modelo':cuerpo.get('model'),'opciones':dict(cuerpo.get('options',{}))}
            try:
                resultado=comprobar_real(cliente,cuerpo,plazo_fin=plazo_fin)
                dato.update(permitido=True,evaluacion=resultado)
                return resultado
            except Exception as error:
                dato.update(permitido=False,tipo=getattr(error,'tipo',type(error).__name__),
                            recursos=getattr(error,'recursos',None))
                raise
            finally:
                dato['segundos']=round(time.monotonic()-inicio,3);admisiones.append(dato)
        fuentes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
        manifiesto=DESTINO/(a.tipo+'_'+a.ronda+'_fuentes.json')
        manifiesto.write_text(json.dumps({'fuentes':fuentes,'sensores':'broker de lectura real, antigüedad máxima 8 s'},indent=2)+'\n');manifiesto.chmod(0o600)
        with patch.object(O,'solicitar',side_effect=transporte),patch.object(R,'comprobar',side_effect=comprobar_recursos),patch.object(Z,'transporte',side_effect=prohibido),salida.open('x') as log:
            salida.chmod(0o600)
            grupos=[{'id':0,'turnos':sesenta()}] if a.tipo=='sesenta' else conversaciones()
            for grupo in grupos:
                h=[];e={'_preferencia_externa':'local'}
                for caso in grupo['turnos']:
                    if a.tipo=='sesenta':h=[];e={'_preferencia_externa':'local'}
                    import control_recursos as R,politica_termica as PT
                    espera=time.monotonic();plazo=espera+900
                    while True:
                        t=R.termica();u=PT.leer()
                        calor=any(type(t.get(k)) in {int,float} and t[k]>=u[c] for k,c in [('temperatura','gpu'),('cpu_c','cpu')])
                        if not calor:break
                        if time.monotonic()>plazo:raise RuntimeError('Banco detenido por temperatura durante 900 s; conservar parcial y repetir con otro nombre')
                        time.sleep(5)
                    pausa=round(time.monotonic()-espera,3)
                    p=caso['pregunta'];llamadas.clear();admisiones.clear();avisos=[];inicio=time.monotonic();J.ESTADISTICAS.clear()
                    try:
                        local=lambda p,h,e:J.comando_local(p,h,e,lambda _:False,ajustes,lambda:None,J.CEREBRO,J.ESTADISTICAS)
                        hecho,texto=comando(p,h,e,lambda n,args:J.ejecutar_herramienta(n,args,lambda _:False,e),J.SISTEMA,local=local,confirmar_plan=lambda _:False)
                        if not hecho:
                            if not h:h.append({'role':'system','content':J.SISTEMA})
                            h.append({'role':'user','content':p})
                            texto=J.responder_con_respaldo(h,J.enviar_a_ollama,lambda _:False,e,mostrar=avisos.append)
                        error=None
                    except Exception as ex:texto='';error=type(ex).__name__+': '+str(ex)
                    ok=bool(re.search(caso['ancla'],texto,re.I|re.S)) and error is None and e.get('_estado_respuesta') not in {'fallida','parcial'}
                    fila={'id':caso.get('id',caso.get('turno')),'conversacion':grupo['id'],'turno':caso.get('turno'),'categoria':caso['categoria'],'pregunta':p,'respuesta_original_jarvis':texto,'error':error,'decision':e.get('_ultima_decision_modelo'),'segundos':round(time.monotonic()-inicio,3),'ancla_minima':caso['ancla'],'cumple_ancla_minima':ok,'estado_respuesta':e.get('_estado_respuesta','completa'),'aislamiento':aislamiento,'corpus_sha256':sha,'llamadas_reales':list(llamadas),'estadisticas':dict(J.ESTADISTICAS),'avisos':avisos}
                    fila['pausa_previa_s']=pausa
                    fila['comprobaciones_recursos']=list(admisiones)
                    log.write(json.dumps(fila,ensure_ascii=False,default=str)+'\n');log.flush()
                    print(json.dumps({k:fila[k] for k in ('id','conversacion','categoria','segundos','cumple_ancla_minima','error')},ensure_ascii=False),flush=True)
        cerrar_sensores()

if __name__=='__main__':main()
