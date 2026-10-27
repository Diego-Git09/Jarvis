"""Calidad/citas/caché con Ollama real, corpus congelado y fuentes ficticias.

Cada ronda se conserva. No usa MCP, herramientas de escritura ni IA externa.
Las medidas de GPU son muestras cada segundo, no un pico continuo garantizado.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import tempfile
import threading
import time

RAIZ=Path(__file__).resolve().parents[1]
INFORMES=RAIZ/'registros/reportes/mejora_6h_20261014/resumen_real'
CASOS=[
 {'id':'SUM01','fuentes':[('md','Proyecto MAPA_ROJO_41. Presupuesto aprobado: 271. Fecha de entrega: 2031-04-17.')],'oro':['MAPA_ROJO_41','271','2031-04-17']},
 {'id':'SUM02','fuentes':[('txt','Proyecto NORTE_A12. Presupuesto aprobado: 157.'),('md','Proyecto SUR_B93. Presupuesto aprobado: 389.')],'oro':['NORTE_A12','SUR_B93','157','389']},
 {'id':'SUM03','fuentes':[('docx','Proyecto LUZ_VERDE_C31. Inventario confirmado: 273 unidades. No hay otras cifras aprobadas.')],'oro':['LUZ_VERDE_C31','273']},
 {'id':'SUM04','fuentes':[('xlsx','Pedido PLANILLA_D64. Total aprobado: 1057. Moneda: CLP.')],'oro':['PLANILLA_D64','1057','CLP']},
 {'id':'SUM05','fuentes':[('db','Contrato LLUVIA_E58. Cantidad confirmada: 809 cajas.')],'oro':['LLUVIA_E58','809']},
 {'id':'SUM06','fuentes':[('eml','Proyecto CORREO_F76. Fecha aprobada: 2032-02-21.'),('md','Proyecto CORREO_F76. Presupuesto aprobado: 473.')],'oro':['CORREO_F76','2032-02-21','473']},
 {'id':'SUM07','fuentes':[('txt','La fuente A fija presupuesto 42 para CONTRASTE_G17.'),('md','La fuente B fija presupuesto 61 para CONTRASTE_G17. Son versiones distintas; no se ha decidido cuál es válida.')],'oro':['CONTRASTE_G17','42','61']},
 {'id':'SUM08','fuentes':[('txt',('Proyecto REPETIDO_H86. Presupuesto confirmado 777. Solo estos datos son requisitos aprobados.\n'*60))],'oro':['REPETIDO_H86','777']},
]


def congelar():
    INFORMES.mkdir(parents=True,exist_ok=True)
    p=INFORMES/'corpus.json';datos=(json.dumps(CASOS,ensure_ascii=False,indent=2)+'\n').encode()
    if p.exists() and p.read_bytes()!=datos:raise ValueError('El corpus congelado no se sobrescribe.')
    if not p.exists():p.write_bytes(datos)
    sha=hashlib.sha256(datos).hexdigest();p.with_suffix('.sha256').write_text(sha+'\n')
    return sha


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ronda',required=True);a=ap.parse_args()
    if not a.ronda.replace('_','').isalnum():raise ValueError('Nombre de ronda inválido.')
    sha=congelar();salida=INFORMES/(a.ronda+'.jsonl')
    if salida.exists():raise ValueError('La ronda ya existe; no se sobrescriben resultados.')
    with tempfile.TemporaryDirectory(prefix='jarvis-resumen-real-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0')
        base=Path(tmp,'trabajo');base.mkdir()
        import cliente_ollama as O
        import resumen_documental as R
        import tandas_documentales as T
        from evaluar_adjuntos_6h import preparar
        from medir_rendimiento_jarvis import recursos
        filas=[]
        with salida.open('x') as log:
            os.chmod(salida,0o600)
            for caso in CASOS:
                carpeta=base/caso['id'];carpeta.mkdir();paths=[]
                for n,(ext,texto) in enumerate(caso['fuentes']):
                    dato={'id':f'fuente{n+1}','extension':ext,'codificacion':'utf-8','clave':'DATO_DOCUMENTAL','dato':texto}
                    paths.append(preparar(carpeta,dato)[0])
                tanda=T.indexar(T.crear(paths)['id'],False)
                auditoria=[]
                def transporte(ruta,cuerpo=None,**kw):
                    r=O.solicitar(ruta,cuerpo,**kw)
                    if ruta=='/api/chat':auditoria.append({'mensajes':cuerpo['messages'],'respuesta':r.get('message',{}),'tokens_entrada':r.get('prompt_eval_count'),'tokens_salida':r.get('eval_count')})
                    return r
                muestras=[recursos()];detener=threading.Event()
                def muestrear():
                    while not detener.wait(1):muestras.append(recursos())
                hilo=threading.Thread(target=muestrear,daemon=True);hilo.start()
                try:
                    r=R.resumir(tanda['id'],max_trozos=3,solicitar=transporte)
                    cache=R.resumir(tanda['id'],max_trozos=3,solicitar=transporte)
                finally:detener.set();hilo.join(4)
                permitidas={x['id']:x['referencia'] for x in r['seleccion']}
                citas=bool(r['refs']) and all(permitidas.get(x['id'])==x['referencia'] for x in r['refs'])
                # Los valores oro nunca están en los nombres de archivo. Una
                # alternativa extractiva no cuenta como generación correcta.
                presentes=[x for x in caso['oro'] if x in r['texto']]
                calidad=bool(r['generacion_completa'] and citas and len(presentes)==len(caso['oro']))
                fila={'id':caso['id'],'fuentes':[p.name for p in paths],'corpus_sha256':sha,'ok':calidad,
                      'oro_presente':presentes,'oro_faltante':[x for x in caso['oro'] if x not in presentes],
                      'citas_correctas':citas,'cache_sin_generacion':cache['llamadas_generacion']==0 and cache['texto']==r['texto'],
                      'resultado':r,'segunda_lectura':cache,'auditoria_llamadas_sinteticas':auditoria,'recursos_muestras':muestras,
                      'rss_max_padre_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2)}
                filas.append(fila);log.write(json.dumps(fila,ensure_ascii=False)+'\n');log.flush()
                print(json.dumps({'id':caso['id'],'ok':calidad,'faltantes':fila['oro_faltante'],'segundos':r['segundos'],'cache':fila['cache_sin_generacion'],'fallos':r['fallos']},ensure_ascii=False),flush=True)
        resumen={'ronda':a.ronda,'casos':len(filas),'aprobados':sum(x['ok'] for x in filas),'fallos':[x['id'] for x in filas if not x['ok']],
                 'citas_correctas':sum(x['citas_correctas'] for x in filas),'cache_sin_generacion':sum(x['cache_sin_generacion'] for x in filas),
                 'oro_total':sum(len(c['oro']) for c in CASOS),'oro_presente':sum(len(x['oro_presente']) for x in filas),
                 'segundos_mediana':statistics.median(x['resultado']['segundos'] for x in filas),
                 'vram_max_muestreada_mib':max((m.get('vram_mib',0) for x in filas for m in x['recursos_muestras']),default=0),
                 'vram_total_mib':max((m.get('vram_total_mib',0) for x in filas for m in x['recursos_muestras']),default=0),
                 'corpus_sha256':sha,'modelo':'qwen3:8b','opciones':R.OPCIONES,
                 'alcance':'Ollama real, ocho tandas sintéticas; retención literal de22 datos, citas estructurales y repetición de caché. No prueba comprensión universal ni causalidad de todos los hechos. GPU muestreada cada1s; RAM sistema no equivale a RSS del lector.'}
        salida.with_suffix('.resumen.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2)+'\n');print(json.dumps(resumen,ensure_ascii=False))


if __name__=='__main__':main()
