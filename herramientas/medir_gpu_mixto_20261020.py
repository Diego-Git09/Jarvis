"""Comparación local reproducible; simulaciones solo en la prueba de aviso.

No configura el servidor ni el usuario. Solo usa modelos ya instalados y
preguntas sintéticas. Las celdas rechazadas por el control quedan registradas.
"""
import os,json,time,tempfile,threading,hashlib,argparse,re,statistics
from pathlib import Path
from unittest.mock import patch
RAIZ=Path(__file__).resolve().parents[1]
DESTINO=RAIZ/'registros/reportes/ronda_mixta_20261020'
MODELO='jarvis-deepseek:8b'
PREGUNTAS=[('suma','Responde en español en una frase: si recibo 17 cajas y luego 9, cuántas tengo?',r'26'),('orden','Explica en dos frases por qué ordenar una lista no elimina sus elementos duplicados.',r'duplicad|repetid')]
MODOS=[('gpu',37),('mixto24',24),('mixto12',12),('mixto4',4),('cpu',0)]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--modo',choices=['tabla','largo','recursos'],required=True);ap.add_argument('--ronda',required=True);a=ap.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_]+',a.ronda):raise ValueError('Nombre de ronda inválido')
    destino=DESTINO/(a.ronda+'.jsonl')
    if destino.exists():raise ValueError('No sobrescribir una ronda')
    with tempfile.TemporaryDirectory(prefix='jarvis-gpu-real-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0')
        import cliente_ollama as O,configuracion_jarvis as C,control_recursos as R,recursos_ollama as RE
        ajustes=C.validar(dict(C.DEFAULT,keep_alive='1m'))
        real=O.solicitar
        def solicitar(ruta,cuerpo=None,**kw):
            with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'leer',return_value=(ajustes,'')):
                return real(ruta,cuerpo,**kw)
        def descargar():
            r=solicitar('/api/generate',{'model':MODELO,'keep_alive':0,'stream':False},timeout=30)
            RE.esperar_descarga(O,[MODELO],time.monotonic()+10)
            presentes=solicitar('/api/ps',timeout=3).get('models',[])
            return {'respuesta':r,'descargado':not any(m.get('name')==MODELO for m in presentes),'ps':presentes}
        def ejecutar(pregunta,ctx,capas,limite=180):
            ajustes.update(modo_gpu='cpu' if capas==0 else 'mixto' if capas<37 else 'auto',capas_gpu=max(1,capas),num_ctx=ctx)
            base=R.instantanea();inicio=time.monotonic();stop=threading.Event();muestras=[];lineas=[];texto='';primero=None;final={};error=None
            def muestrear():
                while not stop.is_set():
                    antes=time.monotonic()
                    try:muestras.append({'segundos':antes-inicio,'ram':R.ram(),'gpu':RE.gpu(),'retraso_s':max(0,antes-inicio-len(muestras))})
                    except (OSError,ValueError):pass
                    stop.wait(max(.01,1-(time.monotonic()-antes)))
            hilo=threading.Thread(target=muestrear,daemon=True);hilo.start()
            cuerpo={'model':MODELO,'messages':[{'role':'system','content':'Responde en español, de forma breve y precisa. No ejecutes acciones.'},{'role':'user','content':pregunta}],
                    'think':False,'truncate':False,'shift':False,'keep_alive':'1m','options':{'num_ctx':ctx,'num_gpu':capas,'num_predict':128,'temperature':0,'seed':17}}
            try:
                with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'leer',return_value=(ajustes,'')),O.abrir_flujo_chat(cuerpo,timeout=limite) as flujo:
                    for linea in flujo:
                        d=json.loads(linea);lineas.append(d)
                        frag=d.get('message',{}).get('content','');texto+=frag
                        if frag and primero is None:primero=time.monotonic()-inicio
                        if d.get('error'):raise ValueError(str(d['error']))
                        if d.get('done'):final=d
            except Exception as e:error=str(e)
            finally:stop.set();hilo.join(timeout=4)
            duracion=time.monotonic()-inicio
            ps=solicitar('/api/ps',timeout=3)
            pico_ram=max([x['ram']['usada'] for x in muestras]+[base['ram']['usada']]);pico_gpu=max([g['usada_mib'] for x in muestras for g in x['gpu'].get('gpu',[])]+[0])
            return {'contexto':ctx,'capas_gpu_pedidas':capas,'modelo':MODELO,'pregunta':pregunta,'segundos':duracion,'primera_palabra_s':primero,'respuesta_original':texto,'error':error,'final':final,'flujo_original':lineas,'ps_tras_inferencia':ps,'base':base,'pico_ram_gib':pico_ram/R.GIB,'pico_vram_mib':pico_gpu,'tokens_s':final.get('eval_count',0)/(final.get('eval_duration',1)/1e9) if final.get('eval_duration') else None,'max_retraso_sonda_s':max([x['retraso_s'] for x in muestras]+[0]),'muestras':muestras}
        with patch.object(O,'solicitar',side_effect=solicitar),destino.open('x') as log:
            destino.chmod(0o600)
            def guardar(fila):
                log.write(json.dumps(fila,ensure_ascii=False,default=str)+'\n');log.flush()
                print(json.dumps({k:fila.get(k) for k in ('id','modo','contexto','capas_gpu_pedidas','segundos','primera_palabra_s','tokens_s','pico_ram_gib','pico_vram_mib','sirvio','error')},ensure_ascii=False),flush=True)
            if a.modo=='tabla':
                corpus={'modelo':MODELO,'modos':MODOS,'contextos':[4096,8192,16384,32768],'preguntas':PREGUNTAS,'num_predict':128,'seed':17,'truncate':False,'shift':False}
                raw=json.dumps(corpus,ensure_ascii=False,indent=2)+'\n';p=DESTINO/'gpu_corpus.json'
                if p.exists() and p.read_text()!=raw:raise ValueError('Corpus cambió')
                p.write_text(raw)
                for modo,capas in MODOS:
                    for ctx in corpus['contextos']:
                        for ident,pregunta,patron in PREGUNTAS:
                            descarga=descargar()
                            if not descarga['descargado']:raise ValueError('No pude comprobar descarga antes de medir')
                            r=ejecutar(pregunta,ctx,capas);r.update(id=modo+'_'+str(ctx)+'_'+ident,modo=modo,descarga_previa=descarga,corpus_sha256=hashlib.sha256(raw.encode()).hexdigest(),sirvio=bool(not r['error'] and re.search(patron,r['respuesta_original'],re.I)))
                            guardar(r)
                        descargar()
            elif a.modo=='largo':
                # Exactamente 15.000 palabras, sin datos privados. Marcadores en
                # principio, mitad y final permiten detectar omisiones gruesas.
                palabras=['el','registro','de','la','bodega','conserva','datos','de','cajas','para','revisar','un','informe','sin','cambios']*1000
                for pos,marca in [(0,'INICIO_LIMA_731'),(7500,'MEDIO_COBRE_482'),(14999,'FINAL_NUBE_956')]:palabras[pos]=marca
                texto=' '.join(palabras);(DESTINO/'texto_15000_palabras.txt').write_text(texto)
                consulta='Devuelve los tres identificadores de marcador que aparecen en el texto, sin inventar otros.\nTexto de datos (no instrucciones):\n'
                for modo,capas in [('gpu',37),('mixto24',24),('mixto12',12),('cpu',0)]:
                    descargar();r=ejecutar(consulta+texto,32768,capas,600);r.update(id=modo+'_completo',modo=modo,metodo='completo',palabras=15000,texto_sha256=hashlib.sha256(texto.encode()).hexdigest(),sirvio=all(m in r['respuesta_original'] for m in [palabras[0],palabras[7500],palabras[-1]]) and not r['error']);guardar(r);descargar()
                    # Mismas 15.000 palabras, cinco tramos; sumar tiempos de una
                    # ejecución, no porcentajes entre rondas.
                    for n in range(5):
                        tramo=' '.join(palabras[n*3000:(n+1)*3000]);r=ejecutar(consulta+tramo,8192,capas,300);r.update(id=modo+'_tramo_'+str(n+1),modo=modo,metodo='tramo',palabras=3000,tramo=n+1);guardar(r);descargar()
            else:
                descargar();r=ejecutar('Responde solamente: LISTO',4096,37);guardar(dict(r,id='carga_real',modo='gpu'))
                antes=solicitar('/api/ps');foto=R.instantanea();foto['gpu']={'ok':True,'gpu':[{'libre_mib':1,'total_mib':8151,'usada_mib':8150}]}
                # Contexto distinto para que no se reste un residente ya cargado.
                ajustes['num_ctx']=8192
                with patch.object(R,'instantanea',return_value=foto):
                    try:solicitar('/api/chat',{'model':MODELO,'messages':[{'role':'user','content':'Prueba sintética de poca VRAM'}],'options':{'num_ctx':8192}},timeout=10);aviso='ERROR: aceptó la simulación'
                    except O.ErrorOllama as e:aviso=str(e)
                permisos=[];salida=RE.liberar(O,ajustes,lambda t:permisos.append(t) or True)
                guardar({'id':'poca_vram_simulada_descarga_real','tipo':'aviso simulado; carga/PS/descarga reales','ps_antes':antes,'aviso':aviso,'permisos':permisos,'salida_liberar':salida,'ps_despues':solicitar('/api/ps')})
                # Reposo verdadero de un minuto, sin borrar pesos ni inferir
                # durante la espera. La lectura de ps valida el evento.
                r=ejecutar('Responde solamente: REPOSO',4096,37);guardar(dict(r,id='reposo_carga_real',modo='gpu'))
                inicio=time.monotonic();lecturas=[]
                while time.monotonic()-inicio<85:
                    time.sleep(5);ps=solicitar('/api/ps');lecturas.append({'segundos':time.monotonic()-inicio,'ps':ps})
                    if not any(m.get('name')==MODELO for m in ps.get('models',[])):break
                # El muestreo de ps puede adelantarse al monitor de2s.
                # Esperar su evento real antes de cerrar el proceso de prueba.
                avisos=R.consumir_avisos();fin_aviso=time.monotonic()+4
                while not avisos and time.monotonic()<fin_aviso:
                    time.sleep(.2);avisos.extend(R.consumir_avisos())
                guardar({'id':'reposo_1m_real','lecturas':lecturas,'descargado':not any(m.get('name')==MODELO for m in lecturas[-1]['ps'].get('models',[])),'avisos':avisos})
            if a.modo=='largo':
                import mensajes_largos as M
                from interfaz_local import comando_local
                estado={};M.preparar(texto,estado)
                ajustes.update(modo_gpu='mixto',capas_gpu=12,num_ctx=32768,timeout_modelo=600,timeout_auto=False,num_predict=128)
                inicio=time.monotonic();raw=[]
                def transporte_completo(ruta,cuerpo=None,**kw):
                    r=solicitar(ruta,cuerpo,**kw)
                    if ruta=='/api/chat':raw.append({'cuerpo':cuerpo,'respuesta_original_api':r})
                    return r
                with patch.object(O,'solicitar',side_effect=transporte_completo):
                    ok,salida=comando_local('/mensaje_completo '+consulta.split('\nTexto')[0],[],estado,lambda _:False,ajustes,lambda:None,None)
                guardar({'id':'integracion_mensaje_completo_real','modo':'mixto12','contexto':32768,'segundos':time.monotonic()-inicio,'respuesta_original_jarvis':salida,'llamadas':raw,'sirvio':ok and all(m in salida for m in [palabras[0],palabras[7500],palabras[-1]])})
            guardar({'id':'descarga_final','resultado':descargar()})
if __name__=='__main__':main()
