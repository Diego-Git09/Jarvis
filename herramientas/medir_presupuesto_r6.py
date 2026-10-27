"""52 sondas locales de tokens: sin herramientas, historial, memoria ni red externa.

No evalúa calidad: num_predict=1. Conserva la respuesta original y las métricas
de cada entrada sintética; declara posibles truncamientos por separado.
"""
import json,time,hashlib,os,sys
from pathlib import Path
import cliente_ollama as O
import presupuesto_contexto as P
from prompt_jarvis import BASE
from metricas_presupuesto_r6 import propuesta

class CapturaRespuesta:
    """Observa las métricas antes del control de salida, sin cambiar sus bytes."""
    def __init__(self,respuesta,captura):self.respuesta=respuesta;self.captura=captura
    def __enter__(self):self.respuesta.__enter__();return self
    def __exit__(self,*args):return self.respuesta.__exit__(*args)
    def read(self,n):
        raw=self.respuesta.read(n)
        try:self.captura.update(json.loads(raw))
        except (ValueError,TypeError):pass
        return raw

def ejecutar():
    casos=json.loads(Path(__file__).with_name('corpus_r5.json').read_text())['casos']
    con_herramientas='--herramientas' in sys.argv
    nombre='presupuesto52_herramientas_real.json' if con_herramientas else 'presupuesto52_real.json'
    destino=Path(__file__).resolve().parents[1]/'registros/reportes/ronda6_20261023'/nombre
    filas=[];datos={'tipo':'sondas de tokenización local, salida de un token; no prueba de calidad ni ejecución de herramientas','modelo':'qwen3:8b','contexto':8192,'coeficiente_actual':P.BYTES_POR_TOKEN,'esquemas_herramientas':con_herramientas,'pausa_entre_sondas_segundos':5,'casos':filas}
    if '--reanudar' in sys.argv and destino.exists():
        anterior=json.loads(destino.read_text())
        if anterior.get('modelo')!='qwen3:8b' or anterior.get('contexto')!=8192 or bool(anterior.get('esquemas_herramientas'))!=con_herramientas:raise ValueError('Banco previo incompatible')
        filas.extend(f for f in anterior['casos'] if f.get('ok'))
        datos['intentos_previos_fallidos']=[f for f in anterior['casos'] if not f.get('ok')]
    terminadas={f['numero'] for f in filas}
    captura={};abrir_original=O.ABRIR
    def abrir(req,*args,**kwargs):
        r=abrir_original(req,*args,**kwargs)
        return CapturaRespuesta(r,captura) if req.full_url.endswith('/api/chat') else r
    O.ABRIR=abrir
    for caso in casos:
        if caso['numero'] in terminadas:continue
        if filas:time.sleep(5)
        pregunta=caso['pasos'][0]['pregunta']
        mensajes=[{'role':'system','content':BASE},{'role':'user','content':pregunta}]
        cuerpo={'model':'qwen3:8b','messages':mensajes,'stream':False,'think':False,'options':{'num_ctx':8192,'num_predict':1,'temperature':0},'keep_alive':'1m'}
        if con_herramientas:
            import jarvis_agente as J
            cuerpo['tools']=J.herramientas_para_turno(mensajes)
        # Los esquemas se anuncian, pero nunca se ejecutan sus propuestas.
        comp=P.componentes(cuerpo,8192,1)
        bytes_comp=sum(len(json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()) for x in ([mensajes[0]],[mensajes[1]],[],{'tools':cuerpo.get('tools',[]),'format':{}}))
        from enrutador_modelos import clasificar_peticion
        clase=clasificar_peticion(pregunta)
        f={'numero':caso['numero'],'categoria':clase['clase']+' / '+str(clase.get('intencion') or 'general'),'sha256_pregunta':hashlib.sha256(pregunta.encode()).hexdigest(),'bytes_componentes':bytes_comp,'tokens_estimados':comp['entrada_tokens_estimados'],'riesgo_truncado':comp['entrada_tokens_estimados']>=8191}
        inicio=time.monotonic()
        f['intentos']=[]
        for intento in range(3):
            captura.clear()
            try:
                r=O.solicitar('/api/chat',cuerpo,timeout=120)
                f.update(ok=True,tokens_reales=r.get('prompt_eval_count'),tokens_salida=r.get('eval_count'),respuesta_original=r.get('message',{}),herramientas_anunciadas=len(cuerpo.get('tools',[])),acciones_ejecutadas=False,fin=r.get('done_reason'))
                f.pop('tipo_error',None);f.pop('error',None)
                break
            except O.ErrorOllama as error:
                if error.tipo=='vacia' and type(captura.get('prompt_eval_count')) is int and captura['prompt_eval_count']>0:
                    f.update(ok=True,tokens_reales=captura['prompt_eval_count'],tokens_salida=captura.get('eval_count'),respuesta_original=captura.get('message',{}),herramientas_anunciadas=len(cuerpo.get('tools',[])),acciones_ejecutadas=False,fin=captura.get('done_reason'),rechazo_controlador='salida vacía o incompleta; solo se acredita el recuento de entrada')
                    f.pop('tipo_error',None);f.pop('error',None)
                    break
                f.update(ok=False,tipo_error=error.tipo,error=str(error));f['intentos'].append({'tipo':error.tipo,'error':str(error)})
                if error.tipo!='recursos' or intento==2:break
                print('Esperando 10s por la admisión, sin cambiar umbrales.',flush=True)
                time.sleep(10)
                import cache_recursos
                cache_recursos.invalidar()
        f['segundos']=round(time.monotonic()-inicio,4);filas.append(f)
        datos['propuesta']=propuesta(filas)
        fd=os.open(destino,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as salida:json.dump(datos,salida,ensure_ascii=False,indent=2);salida.write('\n')
        print(json.dumps({'caso':f['numero'],'ok':f['ok'],'segundos':f['segundos'],'reales':f.get('tokens_reales'),'estimados':f['tokens_estimados']},ensure_ascii=False),flush=True)
        if not f['ok'] and f.get('tipo_error') in {'recursos','politica'}:break
    return datos

if __name__=='__main__':ejecutar()
