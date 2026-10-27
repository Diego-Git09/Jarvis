"""40 peticiones congeladas por el controlador real, sin datos personales ni MCP.

Las rúbricas son comprobaciones mínimas por anclas, no un juicio universal de
calidad. Cada caso es una conversación independiente. No sobrescribe rondas.
"""
import os,json,time,tempfile,hashlib,re
from pathlib import Path
from unittest.mock import patch
RAIZ=Path(__file__).resolve().parents[1]
DESTINO=RAIZ/'registros/reportes/ronda_mixta_20261020'
ANTES_DE_CLIENTE=None
CASOS=[
 ('hola','simple',r'hola'),('wena po','simple',r'hola|wena'),('buenas tardes','simple',r'hola|buenas'),('gracias','simple',r'nada|gusto|ayudar|gracias'),
 ('Qué es un byte?','simple',r'8|ocho'),('Cuántos días tiene una semana?','simple',r'siete|7'),('Cuál es la capital de Chile?','simple',r'santiago'),('Dime un sinónimo de rápido','simple',r'veloz|ágil|agil|ligero'),
 ('Traduce casa al inglés','simple',r'house|home'),('Qué significa CPU?','simple',r'central|procesamiento'),('Cuánto es 13 por 7?','simple',r'91'),('Cuántos lados tiene un triángulo?','simple',r'tres|3'),
 ('/hora','comando',r'Chile'),('/contexto','comando',r'tokens'),('/gpu','comando',r'GPU'),('/reposo','comando',r'Reposo'),
 ('Explícame qué es una variable usando una caja como ejemplo. No escribas código.','media',r'caja'),('Dame tres consejos para organizar un escritorio sin comprar nada.','media',r'1|primero|orden'),
 ('Explica la diferencia entre memoria RAM y disco en palabras sencillas.','media',r'RAM'),('Escribe una invitación breve para una reunión de amigos el sábado, sin inventar una dirección.','media',r'sábado|sabado'),
 ('Dame un ejemplo cotidiano de causa y efecto.','media',r'causa|efecto|si'),('Explica qué es una copia de seguridad en dos frases.','media',r'copia|respaldo'),
 ('Cómo hiervo agua para una taza de té?','media',r'agua'),('Dime qué es el reciclaje en una oración.','media',r'reutil|residu|material|transform'),
 ('Escribe una función Python que devuelva el mayor de una lista, sin ejecutarla.','compleja',r'def |max\('),('Escribe una consulta SQL SELECT de la tabla ventas agrupada por region y suma monto. No la ejecutes.','compleja',r'group by'),
 ('Escribe una clase Java Persona con un campo nombre. No crees archivos.','compleja',r'class Persona'),('Crea un ejemplo Kotlin de función que suma dos Int. Solo texto.','compleja',r'fun '),
 ('Analiza por qué 2*x + 3 = 11 tiene solución x=4.','compleja',r'4'),('Demuestra que la suma de dos enteros pares es par.','compleja',r'2'),
 ('Compara una búsqueda lineal y una binaria, con sus requisitos.','compleja',r'orden'),('Diagnostica conceptualmente un deadlock entre dos bloqueos. No ejecutes comandos.','compleja',r'bloque|lock'),
 ('Diseña un algoritmo para detectar duplicados en una lista. Solo explica.','compleja',r'conjunto|set|lista|diccionario'),('Depura este Python como texto: for i in range(3) print(i). No lo ejecutes.','compleja',r':'),
 ('Razona: todas las cajas azules son grandes; esta caja es azul. Qué concluyes?','compleja',r'grande'),('Evalúa el riesgo de borrar un archivo sin respaldo. No borres nada.','compleja',r'perd|recuper|respaldo'),
 ('Explica el dato del adjunto.\n[Adjunto: ficha sintética]\nEl código de la bodega es NUBE_731 y hay 27 cajas.','adjunto',r'NUBE_731'),
 ('Encuentra la contradicción del adjunto.\n[Adjunto: ficha sintética]\nFuente A: 14 cajas. Fuente B: 19 cajas. No se ha validado ninguna.','adjunto',r'14'),
 ('Resume la condición del adjunto sin omitirla.\n[Adjunto: ficha sintética]\nLa entrega RIO_912 se realiza solo si se aprueba el permiso. Todavía no está aprobado.','adjunto',r'aprob|permiso'),
 ('Analiza el total del adjunto.\n[Adjunto: ficha sintética]\nLunes: 7 cajas; martes: 11 cajas. No hay otros días en esta ficha.','adjunto',r'18')]

def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--ronda',required=True);a=ap.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_]+',a.ronda):raise ValueError('Nombre de ronda inválido')
    destino=DESTINO/(a.ronda+'.jsonl');destino.parent.mkdir(parents=True,exist_ok=True)
    corpus=DESTINO/'seleccion_corpus_40.json';raw=json.dumps(CASOS,ensure_ascii=False,indent=2)+'\n'
    if corpus.exists() and corpus.read_text()!=raw:raise ValueError('Corpus congelado distinto')
    corpus.write_text(raw);sha=hashlib.sha256(raw.encode()).hexdigest()
    if destino.exists():raise ValueError('No sobrescribir respuestas originales')
    with tempfile.TemporaryDirectory(prefix='jarvis-seleccion-real-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0')
        if ANTES_DE_CLIENTE:ANTES_DE_CLIENTE()
        import jarvis_agente as J,cliente_ollama as O,configuracion_jarvis as C
        import entorno_jarvis
        if entorno_jarvis.PROYECTO!=Path(tmp).resolve() or C.ARCHIVO!=Path(tmp)/'datos/configuracion.json':raise RuntimeError('El medidor importó rutas fuera de su carpeta temporal; se cancela antes de generar o guardar hilos.')
        from aislamiento_pruebas import verificar_previo
        aislamiento=verificar_previo(tmp,nativo=True,evidencias=DESTINO)
        from interfaz_jarvis import comando
        ajustes=C.validar(dict(C.DEFAULT,seleccion_modelo='automatico',num_predict=1024,keep_alive='0',timeout_modelo=240))
        J.AJUSTES.clear();J.AJUSTES.update(ajustes);J.OPCIONES.update(num_ctx=8192,num_predict=1024)
        real=O.solicitar;llamadas=[]
        def transporte(ruta,cuerpo=None,**kw):
            inicio=time.monotonic()
            try:
                with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'leer',return_value=(ajustes,'')):
                    r=real(ruta,cuerpo,**kw)
                if ruta=='/api/chat':llamadas.append({'pedido':cuerpo,'respuesta_original_api':r,'segundos':time.monotonic()-inicio})
                return r
            except Exception as e:
                if ruta=='/api/chat':llamadas.append({'pedido':cuerpo,'error':str(e),'recursos':getattr(e,'recursos',None),'segundos':time.monotonic()-inicio})
                raise
        with patch.object(O,'solicitar',side_effect=transporte),destino.open('x') as log:
            destino.chmod(0o600)
            for i,(pregunta,grupo,ancla) in enumerate(CASOS,1):
                h=[];e={'_adjuntos_turno':True} if grupo=='adjunto' else {};llamadas.clear();avisos=[];inicio=time.monotonic();J.ESTADISTICAS.clear()
                try:
                    local=lambda p,h,e:J.comando_local(p,h,e,lambda _:False,ajustes,lambda:None,J.CEREBRO,J.ESTADISTICAS)
                    manejado,texto=comando(pregunta,h,e,lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,e),J.SISTEMA,local=local,confirmar_plan=lambda _:False)
                    if not manejado:
                        h.extend([{'role':'system','content':J.SISTEMA},{'role':'user','content':pregunta}])
                        texto=J.responder_con_respaldo(h,J.enviar_a_ollama,lambda _:False,e,mostrar=avisos.append)
                    error=None
                except Exception as exc:texto='';error=str(exc)
                sirve=bool(re.search(ancla,texto,re.I)) and not e.get('_estado_respuesta')=='fallida' and error is None
                fila={'id':i,'grupo':grupo,'pregunta':pregunta,'corpus_sha256':sha,'aislamiento':aislamiento,'segundos':round(time.monotonic()-inicio,3),'decision':e.get('_ultima_decision_modelo'),'respuesta_original_jarvis':texto,'error':error,'rubrica_ancla':ancla,'sirvio_segun_ancla_minima':sirve,'avisos':avisos,'llamadas_reales':list(llamadas),'estadisticas':dict(J.ESTADISTICAS)}
                log.write(json.dumps(fila,ensure_ascii=False,default=str)+'\n');log.flush()
                print(json.dumps({k:fila[k] for k in ('id','grupo','segundos','decision','sirvio_segun_ancla_minima','error')},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
