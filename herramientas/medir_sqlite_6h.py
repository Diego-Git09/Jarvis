"""Compara muestras equivalentes de SQLite sintético, en procesos sucesivos.

Generación fuera de la medición; sin Ollama, MCP ni archivos personales.
El RSS muestreado y ru_maxrss no son límites globales del árbol.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time

BASE=Path(__file__).resolve().parents[1]
RAIZ=BASE/'registros/reportes/mejora_6h_20261014/sqlite'
ESPECIFICACION={'id':'SQLITE_CELDAS_16M','publico_bytes':4*1024**2,'secreto_bytes':4*1024**2,
    'blob_bytes':8*1024**2,'prefijo_publico':'DATO_SQLITE_LITERAL_73 ',
    'oro':['DATO_SQLITE_LITERAL_73','473','[BLOB 8388608 bytes]','[REDACTADO]'],
    'prohibido':'SECRETO_SINTETICO_73','limite_texto':1000,'tablas':1,'filas':1}


def preparar(p):
    with closing(sqlite3.connect(p)) as db,db:
        db.execute('CREATE TABLE inventario(nombre TEXT,monto INTEGER,detalle TEXT,api_key TEXT,adjunto BLOB)')
        texto=ESPECIFICACION['prefijo_publico']+'x'*(ESPECIFICACION['publico_bytes']-len(ESPECIFICACION['prefijo_publico']))
        secreto=ESPECIFICACION['prohibido']+'s'*(ESPECIFICACION['secreto_bytes']-len(ESPECIFICACION['prohibido']))
        db.execute('INSERT INTO inventario VALUES(?,?,?,?,zeroblob(?))',('Mañana',473,texto,secreto,ESPECIFICACION['blob_bytes']))


def worker(p):
    import resource
    import lectores_adjuntos as R
    def huella():
        with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    antes=huella();item={'nombre':p.name,'tipo':'.sqlite'}
    inicio=time.monotonic();partes=list(R._sqlite(p,item,2_000_000));segundos=time.monotonic()-inicio
    texto='\n'.join(t for _,t in partes)
    presentes=[x for x in ESPECIFICACION['oro'] if x in texto]
    print(json.dumps({'id':ESPECIFICACION['id'],'segundos_lector':round(segundos,6),
        'rss_max_proceso_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'anclas_presentes':presentes,'ok':len(presentes)==len(ESPECIFICACION['oro']) and ESPECIFICACION['prohibido'] not in texto,
        'salida_sha256':hashlib.sha256(texto.encode()).hexdigest(),'caracteres_salida':len(texto),
        'aviso':item.get('aviso',''),'original_intacto':antes==huella()},ensure_ascii=False))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ronda');ap.add_argument('--worker',type=Path);a=ap.parse_args()
    if a.worker:worker(a.worker);return 0
    if not a.ronda or not a.ronda.replace('_','').isalnum():raise ValueError('Ronda requerida y válida.')
    RAIZ.mkdir(parents=True,exist_ok=True);destino=RAIZ/(a.ronda+'.json')
    if destino.exists():raise ValueError('No sobrescribir rondas anteriores.')
    raw=(json.dumps(ESPECIFICACION,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    corpus=RAIZ/'especificacion.json'
    if corpus.exists() and corpus.read_bytes()!=raw:raise ValueError('La especificación congelada cambió.')
    if not corpus.exists():corpus.write_bytes(raw)
    sha=hashlib.sha256(raw).hexdigest();corpus.with_suffix('.sha256').write_text(sha+'\n')
    import psutil
    with tempfile.TemporaryDirectory(prefix='jarvis-sqlite-medida-') as tmp:
        p=Path(tmp,'muestra.sqlite');preparar(p);env=dict(os.environ,JARVIS_DIR=tmp,JARVIS_PRUEBAS='1')
        proceso=subprocess.Popen([sys.executable,'-B',__file__,'--worker',str(p)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        monitor=psutil.Process(proceso.pid);rss=0;inicio=time.monotonic()
        while proceso.poll() is None:
            try:rss=max(rss,monitor.memory_info().rss)
            except psutil.Error:pass
            if time.monotonic()-inicio>60:proceso.kill();raise TimeoutError('Lector excedió el plazo de la medición.')
            time.sleep(.01)
        salida,error=proceso.communicate();dato=json.loads(salida) if proceso.returncode==0 else {'ok':False,'error':error[-1200:]}
        dato.update(ronda=a.ronda,especificacion_sha256=sha,sqlite_version=sqlite3.sqlite_version,
            bytes_fuente=p.stat().st_size,rss_python_mib_muestreado=round(rss/1024**2,3),
            alcance='Lector SQLite directo en proceso nuevo; RSS cada10ms, no pico continuo ni límite global. Generación previa excluida. Sin modelo ni red.')
        destino.write_text(json.dumps(dato,ensure_ascii=False,indent=2)+'\n');destino.chmod(0o600);print(json.dumps(dato,ensure_ascii=False))
        return 0 if dato['ok'] else 1


if __name__=='__main__':raise SystemExit(main())
