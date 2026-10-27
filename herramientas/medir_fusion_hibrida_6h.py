"""Compara memoria/latencia en5000 trozos, usando la misma base temporal.

Un vector real registrado se repite para aislar el coste de lectura y fusión.
No representa5000 embeddings distintos ni calidad semántica; no usa red/MCP.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import tempfile
import time

REPORTES=Path(__file__).resolve().parents[1]/'registros/reportes/mejora_6h_20261014/recuperacion_semantica'


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def worker(raiz,config,fase,baseline=None):
    os.environ.update(JARVIS_DIR=str(raiz),JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0')
    if baseline:sys.path.insert(0,str(baseline))
    import tandas_documentales as T
    import cliente_ollama as O
    from unittest.mock import patch
    cfg=json.loads(config.read_text());especificacion=cfg['especificacion'];trabajo=raiz/'trabajo';trabajo.mkdir(exist_ok=True)
    if fase=='preparar':
        p=trabajo/'referencias.txt'
        with p.open('w') as f:
            for i in range(especificacion['filas']):f.write(f'OROHIB{i:05d} Existencias {i+7}. '+('relleno seguro '*50)+'\n')
        T.configurar(dict(T.DEFAULT,trozo=400));d=T.indexar(T.crear([p])['id'],False)
        with closing(T._conexion()) as db:
            db.execute('UPDATE trozos SET vector=?',(json.dumps(cfg['vector']),));db.commit();cantidad=db.execute('SELECT count(*) FROM trozos').fetchone()[0]
        if cantidad!=5000:raise ValueError(f'La especificación esperaba5000 trozos, recibió{cantidad}. No se cambia el oro.')
        d['modelo_embeddings']='nomic-embed-text:latest';d['version_embeddings']=2
        for a in d['archivos']:a['version_embeddings']=2;a['embeddings_completos']=True
        T._atomic(T._ruta(d['id']),d);(raiz/'tanda.json').write_text(json.dumps({'id':d['id']}))
        return {'trozos':cantidad,'bytes_fuente':p.stat().st_size,'fuente_sha256':sha(p),'base_sha256':sha(T.RAIZ/'trozos.sqlite')}
    ident=json.loads((raiz/'tanda.json').read_text())['id'];p=trabajo/'referencias.txt';antes=sha(p);db_antes=sha(T.RAIZ/'trozos.sqlite');filas=[]
    with patch.object(O,'solicitar',side_effect=AssertionError('Sin llamadas al modelo en esta medición.')):
        for n in especificacion['consultas_lineas']:
            consulta=f'OROHIB{n:05d}';inicio=time.monotonic();r=T.buscar(ident,consulta,limite=8,presupuesto=6000,embedding=lambda *_:cfg['vector']);dt=time.monotonic()-inicio
            oro=[t for t in r['trozos'] if consulta in t['texto'] and f'Existencias {n+7}.' in t['texto'] and f'línea {n+1},' in t['referencia']]
            filas.append({'linea':n+1,'recall_8':bool(oro),'cita_correcta':bool(oro),'segundos':round(dt,6),'metodo':r['metodo'],'candidatos':r.get('estadisticas_busqueda')})
    return {'corpus_especificacion_sha256':cfg['especificacion_sha256'],'sha256_buscador':sha(Path(T.__file__)),'sha256_fusion':sha(Path(T.HIBRIDA.__file__)) if hasattr(T,'HIBRIDA') else None,'baseline':str(baseline) if baseline else None,
        'casos':len(filas),'recall_8':sum(x['recall_8'] for x in filas),'citas_correctas':sum(x['cita_correcta'] for x in filas),
        'mediana_segundos':round(statistics.median(x['segundos'] for x in filas),6),'fuente_intacta':antes==sha(p),'base_intacta':db_antes==sha(T.RAIZ/'trozos.sqlite'),'consultas':filas}


def medir(cmd,env):
    import psutil
    inicio=time.monotonic();p=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    proceso=psutil.Process(p.pid);rss=arbol=0
    while p.poll() is None:
        if time.monotonic()-inicio>180:os.killpg(p.pid,signal.SIGKILL);p.communicate();raise TimeoutError('La medición excedió180s.')
        try:
            valor=proceso.memory_info().rss;rss=max(rss,valor)
            for hijo in proceso.children(recursive=True):
                try:valor+=hijo.memory_info().rss
                except psutil.Error:pass
            arbol=max(arbol,valor)
        except psutil.Error:pass
        time.sleep(.01)
    out,err=p.communicate()
    if p.returncode:raise ValueError('Fallo del worker de evaluación: '+err[-2500:])
    return {**json.loads(out),'segundos_proceso':round(time.monotonic()-inicio,4),'rss_max_muestreado_mib':round(rss/1024**2,3),'rss_arbol_muestreado_mib':round(arbol/1024**2,3),'muestreo_ms':10}


def main(salida,baseline):
    if salida.exists():raise ValueError('No sobrescribir una medición anterior.')
    if not baseline or not (baseline/'tandas_documentales.py').is_file():raise ValueError('Falta el módulo base para la comparación.')
    registrados=json.loads((REPORTES/'prefijos_experimento.recursos.json').read_text())['embeddings'];vector=registrados[0]['vector']
    especificacion={'version':1,'filas':2500,'trozos_esperados':5000,'trozo':400,'consultas_lineas':list(range(0,2500,100)),
        'vector_dimensiones':len(vector),'vector_sha256':hashlib.sha256(json.dumps(vector).encode()).hexdigest(),'vector_repetido':True,'fuente_vector':'prefijos_experimento.recursos.json,registro0',
        'criterio':'Marcador, valor y cita de la línea oro entre8; fuente y base idénticas. No se evalúa comprensión semántica.'}
    raw=(json.dumps(especificacion,ensure_ascii=False,indent=2)+'\n').encode();spec=REPORTES/'especificacion_5000.json'
    if spec.exists() and spec.read_bytes()!=raw:raise ValueError('No cambiar especificación congelada.')
    if not spec.exists():spec.write_bytes(raw);spec.chmod(0o600)
    huella=hashlib.sha256(raw).hexdigest();spec.with_suffix('.sha256').write_text(huella+'\n')
    with tempfile.TemporaryDirectory(prefix='jarvis-fusion-5000-') as tmp:
        raiz=Path(tmp);config=raiz/'config.json';config.write_text(json.dumps({'especificacion':especificacion,'especificacion_sha256':huella,'vector':vector}));config.chmod(0o600)
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');prefijo=[sys.executable,'-B',str(Path(__file__).resolve()),'--raiz',str(raiz),'--config',str(config)]
        preparacion=medir(prefijo+['--worker','preparar'],env);resultados=[]
        for nombre,base in [('anterior',baseline),('actual',None)]:
            cmd=prefijo+['--worker','consultar']+(['--baseline',str(base)] if base else [])
            r=medir(cmd,env);r['version']=nombre;resultados.append(r)
        dato={'especificacion_sha256':huella,'preparacion_fuera_de_comparacion':preparacion,'resultados':resultados,
            'alcance':'Misma base de5000 trozos y25 consultas, en procesos nuevos secuenciales. Un vector real se repite para aislar lectura/parseo/fusión; no equivale a5000 embeddings reales diferentes. Sin modelo/MCP/red. RSS muestreado10ms, no pico continuo garantizado.'}
        salida.parent.mkdir(parents=True,exist_ok=True);salida.write_text(json.dumps(dato,ensure_ascii=False,indent=2)+'\n');salida.chmod(0o600)
        print(json.dumps({**dato,'resultados':[{k:v for k,v in r.items() if k!='consultas'} for r in resultados]},ensure_ascii=False))
        return 0 if all(r['recall_8']==25 and r['citas_correctas']==25 and r['fuente_intacta'] and r['base_intacta'] for r in resultados) else 1


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--salida',type=Path);ap.add_argument('--baseline',type=Path);ap.add_argument('--worker');ap.add_argument('--raiz',type=Path);ap.add_argument('--config',type=Path);a=ap.parse_args()
    if a.worker:print(json.dumps(worker(a.raiz,a.config,a.worker,a.baseline),ensure_ascii=False))
    elif a.salida:raise SystemExit(main(a.salida,a.baseline))
    else:ap.error('Indica --salida.')
