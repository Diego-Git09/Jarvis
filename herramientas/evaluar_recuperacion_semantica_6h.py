"""Recuperación real con nomic local: corpus congelado, sin generación ni MCP.

Compara FTS/texto con la mezcla actual de texto/vectores. Los vectores de las
consultas se calculan antes de cronometrar la búsqueda; su coste va separado.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time

RAIZ=Path(__file__).resolve().parents[1]/'registros/reportes/mejora_6h_20261014/recuperacion_semantica'
TEMAS=[
 ('Los avisos del escritorio aparecen dos días antes del certamen y siguen visibles hasta completarlos.', '¿Cuándo aparecen los avisos del certamen?', '¿Cómo veo una nota anticipada para una prueba antes de que llegue el día?'),
 ('Para recuperar una tanda interrumpida, usa el índice parcial y conserva las páginas ya confirmadas.', '¿Qué conserva una tanda interrumpida?', '¿Cómo retomo la lectura donde quedó sin empezar de cero?'),
 ('La bitácora de incidencias almacena fallos, su causa comprobada y la solución aplicada.', '¿Qué almacena la bitácora de incidencias?', '¿Dónde dejo anotado qué salió mal y cómo se arregló?'),
 ('El presupuesto de la obra se expresa en pesos chilenos; el monto reservado es 682 unidades.', '¿En qué moneda está el presupuesto de la obra?', '¿Cuánta plata se apartó para la construcción?'),
 ('Las facturas vencidas se revisan en el listado de cuentas por cobrar a clientes.', '¿Dónde se revisan las facturas vencidas?', '¿En qué parte encuentro la plata que aún me deben los compradores?'),
 ('La pantalla móvil usa Kotlin y componentes visuales declarativos dentro de Android Studio.', '¿Con qué se desarrolla la pantalla móvil?', '¿Cómo está hecha la vista de la aplicación del teléfono?'),
 ('La migración de base de datos agrega una columna de inventario sin borrar registros existentes.', '¿Qué agrega la migración de base de datos?', '¿Cómo se amplía el almacenamiento de existencias conservando las filas anteriores?'),
 ('Las pruebas unitarias de Python comprueban funciones aisladas con entradas ficticias.', '¿Qué comprueban las pruebas unitarias de Python?', '¿Cómo verifico por separado una función sin usar datos de verdad?'),
 ('El sistema de copias recupera archivos desde una instantánea anterior y comprueba su huella.', '¿Cómo se recuperan archivos desde una instantánea?', '¿Cómo vuelvo a una versión de antes y compruebo que quedó idéntica?'),
 ('Las notas sin categoría permanecen pendientes hasta elegir un proyecto de destino.', '¿Dónde quedan las notas sin categoría?', '¿Dónde encuentro los apuntes que todavía no he ordenado en una carpeta de trabajo?'),
 ('La consulta meteorológica distingue temperatura actual, lluvia y pronóstico del día siguiente.', '¿Qué distingue la consulta meteorológica?', '¿Cómo averiguo si mañana necesitaré paraguas?'),
 ('Los documentos escaneados requieren reconocimiento óptico para convertir letras de una imagen en texto.', '¿Qué requieren los documentos escaneados?', '¿Cómo saco las palabras de una foto de una hoja?'),
 ('La autenticación usa una credencial guardada en el llavero; los informes ocultan su valor.', '¿Dónde se guarda la credencial de autenticación?', '¿Cómo se conserva una llave de acceso sin mostrarla en los reportes?'),
 ('La agenda admite posponer una reunión y cambiar su fecha sin crear otro evento.', '¿Qué permite hacer la agenda con una reunión?', '¿Cómo corro para después una cita que ya tenía programada?'),
 ('La lectura SQLite ofrece esquema y muestras sin ejecutar instrucciones procedentes del archivo.', '¿Qué ofrece la lectura SQLite?', '¿Cómo veo las tablas y unas filas sin correr las órdenes incluidas en la base?'),
 ('El historial de trabajo conserva decisiones tempranas y recupera el objetivo tras reiniciar.', '¿Qué conserva el historial de trabajo?', '¿Cómo recuerda el asistente lo acordado al principio después de volver a abrirlo?'),
 ('El consumo gráfico se mide como memoria de vídeo ocupada por los modelos instalados.', '¿Cómo se mide el consumo gráfico?', '¿Cuánta VRAM están usando las inteligencias del equipo?'),
 ('Las carpetas del repositorio excluyen dependencias descargadas y archivos compilados al adjuntarse.', '¿Qué se excluye al adjuntar carpetas del repositorio?', '¿Cómo evito cargar las librerías ajenas y los resultados del build?'),
 ('El control de versiones mantiene cambios locales confirmados y compara diferencias entre archivos.', '¿Qué mantiene el control de versiones?', '¿Cómo veo qué líneas cambiaron respecto de la revisión anterior?'),
 ('La selección múltiple permite marcar un rango con Shift y elementos separados con Control.', '¿Cómo se usa la selección múltiple?', '¿Cómo marco varios recuadros juntos o algunos sueltos con el teclado?'),
]
DISTRACTORES=[
 'La receta del almuerzo enumera verduras, arroz y tiempos de cocción.',
 'El catálogo de películas distingue reparto, director y año de estreno.',
 'El piano se afina por octavas y conserva una referencia de frecuencia.',
 'Los árboles del parque se registran por especie y altura aproximada.',
 'Las rutas de senderismo incluyen desnivel, distancia y dificultad.',
 'El calendario lunar indica fases y fechas de observación nocturna.',
 'Los boletos del tren se ordenan por estación de salida y asiento.',
 'El diccionario de cocina explica utensilios para amasar pan.',
 'La biblioteca municipal presta novelas por catorce días.',
 'La cancha de tenis distingue líneas laterales y zonas de servicio.',
 'El taller de cerámica registra hornos y temperaturas de cocción.',
 'Los mapas históricos representan antiguas fronteras y ciudades.',
 'La colección de monedas conserva diámetro, metal y país de origen.',
 'El cultivo de tomates necesita riego y luz solar suficiente.',
 'La revista de astronomía describe órbitas y tipos de estrellas.',
 'La reparación de bicicletas revisa frenos, cadena y presión de ruedas.',
 'La exposición de pintura agrupa obras por autor y técnica.',
 'La ruta de buses urbanos conecta terminales y paraderos.',
 'El ejercicio de natación alterna estilos y distancias por sesión.',
 'La tienda de mascotas informa alimentos adecuados para animales.',
]
METADATOS={0:'Para el anexo, revisa exclusivamente fuente_01.txt.',
 4:'Muéstrame lo que dice fuente_05.txt sobre el plan, aunque otros documentos hablen de bases de datos.',
 9:'Del contenido de fuente_10.txt necesito saber las instrucciones, no de los demás.',
 14:'La respuesta debe salir de fuente_15.txt, incluso si encuentro algo parecido en Android.'}


def corpus():
    fuentes=[{'id':f'SEM{i+1:02d}','nombre':f'fuente_{i+1:02d}.txt','texto':f'FICHA_SEM_{i+1:02d}. '+t[0]} for i,t in enumerate(TEMAS)]
    fuentes.extend({'id':f'DIST{i+1:02d}','nombre':f'fuente_{i+21:02d}.txt','texto':f'FICHA_DIST_{i+1:02d}. '+t} for i,t in enumerate(DISTRACTORES))
    preguntas=[]
    for i,(_,literal,sinonimo) in enumerate(TEMAS):
        for clase,q in [('literal',literal),('metadatos' if i in METADATOS else 'parafrasis',METADATOS.get(i,sinonimo))]:
            preguntas.append({'id':f'SEMQ{len(preguntas)+1:02d}','clase':clase,'consulta':q,'fuente_oro':fuentes[i]['nombre'],'marca_oro':f'FICHA_SEM_{i+1:02d}'})
    return {'fuentes':fuentes,'consultas':preguntas,'rubrica':{'version':1,'recall_k':8,'top1':True,'cita':'La referencia y el marcador deben corresponder al archivo oro; una paráfrasis no cambia el oro.'}}


def congelar():
    RAIZ.mkdir(parents=True,exist_ok=True);RAIZ.chmod(0o700);d=corpus();raw=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode();p=RAIZ/'corpus.json'
    if p.exists() and p.read_bytes()!=raw:raise ValueError('No modificar el corpus congelado.')
    if not p.exists():p.write_bytes(raw)
    p.chmod(0o600);sha=hashlib.sha256(raw).hexdigest();p.with_suffix('.sha256').write_text(sha+'\n');p.with_suffix('.sha256').chmod(0o600);return d,sha


def main(ronda=None,prefijos=False,baseline=None):
    d,sha=congelar()
    if not ronda:print(json.dumps({'fuentes':len(d['fuentes']),'consultas':len(d['consultas']),'sha256':sha}));return
    if not ronda.replace('_','').isalnum():raise ValueError('Nombre de ronda inválido.')
    destino=RAIZ/(ronda+'.jsonl')
    if destino.exists():raise ValueError('No sobrescribir una ronda anterior.')
    with tempfile.TemporaryDirectory(prefix='jarvis-recuperacion-semantica-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0')
        base=Path(tmp,'trabajo');base.mkdir()
        if baseline:sys.path.insert(0,str(baseline))
        import cliente_ollama as O
        import tandas_documentales as T
        from medir_rendimiento_jarvis import recursos
        tags=O.solicitar('/api/tags',timeout=5);modelo=next((x for x in tags.get('models',[]) if x.get('name')=='nomic-embed-text:latest'),None)
        if not modelo:raise ValueError('Falta el modelo local instalado; no se descargó otro.')
        paths=[]
        for f in d['fuentes']:
            p=base/f['nombre'];p.write_text(f['texto']);paths.append(p)
        def residentes():
            r=O.solicitar('/api/ps',timeout=5)
            return [{k:m.get(k) for k in ('name','digest','size_vram','context_length')} for m in r.get('models',[])]
        modelos_antes=residentes();muestras=[recursos()];detener=threading.Event()
        def muestrear():
            while not detener.wait(1):muestras.append(recursos())
        hilo=threading.Thread(target=muestrear,daemon=True);hilo.start();vectores={};tiempos=[];llamadas=[]
        def vector(t,m,tipo='documento'):
            if t.startswith('search_query: '):tipo='consulta';entrada=t;t=t[len('search_query: '):]
            elif t.startswith('search_document: '):tipo='documento';entrada=t;t=t[len('search_document: '):]
            else:entrada=(('search_query: ' if tipo=='consulta' else 'search_document: ')+t) if prefijos else t
            inicio=time.monotonic();v=T._vector(entrada,m);dt=time.monotonic()-inicio
            llamadas.append({'modelo':m,'tipo':tipo,'sha256_texto':hashlib.sha256(t.encode()).hexdigest(),'dimension':len(v),'segundos':round(dt,6),'vector':v})
            return v
        filas=[]
        try:
            inicio=time.monotonic();tanda=T.indexar(T.crear(paths)['id'],True,embedding=vector);segundos_indexacion=time.monotonic()-inicio
            for c in d['consultas']:
                entrada=T._entrada_embedding(c['consulta'],tanda['modelo_embeddings'],True) if hasattr(T,'_entrada_embedding') else c['consulta']
                inicio=time.monotonic();vectores[c['consulta']]=vector(entrada,tanda['modelo_embeddings'],'consulta');tiempos.append(time.monotonic()-inicio)
            with destino.open('x') as log:
                destino.chmod(0o600)
                for modo in ('lexical','hibrida_actual'):
                    for c in d['consultas']:
                        inicio=time.monotonic();r=T.buscar(tanda['id'],c['consulta'],limite=8,presupuesto=6000,
                            embedding=(lambda *_:None) if modo=='lexical' else (lambda t,_m:vectores[t.removeprefix('search_query: ')]))
                        dt=time.monotonic()-inicio
                        buenos=[i for i,t in enumerate(r['trozos']) if t['referencia']==c['fuente_oro']+' · líneas 1-1' and c['marca_oro'] in t['texto']]
                        fila={'id':c['id'],'modo':modo,'clase':c['clase'],'consulta':c['consulta'],'fuente_oro':c['fuente_oro'],
                            'recall_8':bool(buenos),'top1':bool(buenos and buenos[0]==0),'rango_oro':buenos[0]+1 if buenos else None,
                            'segundos_busqueda_sin_embedding':round(dt,6),'resultado':r,'corpus_sha256':sha}
                        filas.append(fila);log.write(json.dumps(fila,ensure_ascii=False)+'\n');log.flush()
        finally:detener.set();hilo.join(3)
        resumen={'ronda':ronda,'corpus_sha256':sha,'modelo':modelo['name'],'digest':modelo.get('digest'),'prefijos_experimentales':prefijos,'fuentes':len(paths),'consultas':len(d['consultas']),
            'version_embeddings':getattr(T,'EMBEDDING_VERSION',None),'sha256_buscador':hashlib.sha256(Path(T.__file__).read_bytes()).hexdigest(),
            'sha256_fusion':hashlib.sha256(Path(T.HIBRIDA.__file__).read_bytes()).hexdigest() if hasattr(T,'HIBRIDA') else None,
            'baseline_solo_modulo':str(baseline) if baseline else None,'modelos_residentes_antes':modelos_antes,'modelos_residentes_despues':residentes(),
            'llamadas_embedding':len(llamadas),'segundos_indexacion':round(segundos_indexacion,4),'embedding_consulta_mediana_s':round(statistics.median(tiempos),6),
            'vram_max_muestreada_mib':max((m.get('vram_mib',0) for m in muestras),default=0),'muestreo_s':1,'modos':[],
            'alcance':'Solo recuperación y citas; nomic local real en40 fuentes ficticias y40 consultas. Sin generación/MCP/nube. Búsqueda cronometra acceso al índice con vectores de consulta ya calculados; su coste se informa por separado. No demuestra calidad semántica universal.'}
        for modo in ('lexical','hibrida_actual'):
            xs=[x for x in filas if x['modo']==modo]
            resumen['modos'].append({'modo':modo,'casos':len(xs),'recall_8':sum(x['recall_8'] for x in xs),'top1':sum(x['top1'] for x in xs),
                'mediana_busqueda_sin_embedding':round(statistics.median(x['segundos_busqueda_sin_embedding'] for x in xs),6),
                'fallos_recall':[x['id'] for x in xs if not x['recall_8']],'fallos_top1':[x['id'] for x in xs if not x['top1']],
                'por_clase':{clase:{'casos':sum(x['clase']==clase for x in xs),'recall_8':sum(x['recall_8'] for x in xs if x['clase']==clase),'top1':sum(x['top1'] for x in xs if x['clase']==clase)} for clase in ('literal','parafrasis','metadatos')}})
        destino.with_suffix('.resumen.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2)+'\n')
        destino.with_suffix('.resumen.json').chmod(0o600)
        destino.with_suffix('.recursos.json').write_text(json.dumps({'muestras':muestras,'embeddings':llamadas},ensure_ascii=False,indent=2)+'\n')
        destino.with_suffix('.recursos.json').chmod(0o600)
        print(json.dumps(resumen,ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--ronda');ap.add_argument('--congelar',action='store_true');ap.add_argument('--prefijos',action='store_true');ap.add_argument('--baseline',type=Path);a=ap.parse_args();main(a.ronda,a.prefijos,a.baseline)
