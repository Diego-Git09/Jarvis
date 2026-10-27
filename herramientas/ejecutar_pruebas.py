"""Ejecuta todas las pruebas en un Jarvis temporal; no ensucia los archivos del usuario."""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def ejecutar_archivo(prueba):
    inicio=time.monotonic();carpeta=Path(__file__).resolve().parent
    # Cada proceso recibe su propia raíz; no comparte sesiones, cambios o DB.
    with tempfile.TemporaryDirectory(prefix='jarvis-'+prueba.stem+'-') as root:
        proyecto=Path(root)/'Jarvis';trabajo=proyecto/'trabajo';trabajo.mkdir(parents=True)
        (trabajo/'prueba.txt').write_text('hola\n',encoding='utf-8')
        env=dict(os.environ,JARVIS_DIR=str(proyecto),JARVIS_PRUEBAS='1',PYTHONDONTWRITEBYTECODE='1',NO_COLOR='1')
        try:
            p=subprocess.run([sys.executable,'-B',str(carpeta/'ejecutar_prueba_aislada.py'),str(prueba)],env=env,capture_output=True,text=True,timeout=90)
            salida=p.stdout+'\n'+p.stderr
            legacy=re.search(r'(\d+) de (\d+) pruebas pasaron',salida)
            unit=re.search(r'Ran (\d+) tests?',salida)
            total=int(legacy[2]) if legacy else int(unit[1]) if unit else 0
            ok=p.returncode==0 and 'FALLÓ ' not in salida and 'FAILED (' not in salida
            return {'archivo':prueba.name,'total':total,'ok':ok,'codigo':p.returncode,'segundos':round(time.monotonic()-inicio,4),'salida':salida}
        except subprocess.TimeoutExpired:
            return {'archivo':prueba.name,'total':0,'ok':False,'codigo':None,'segundos':round(time.monotonic()-inicio,4),'salida':'Excedió 90 segundos'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--solo',help='Nombre o fragmento del archivo de prueba')
    parser.add_argument('--procesos',type=int,default=min(4,os.cpu_count() or 1),help='Procesos de prueba simultáneos (1 = serial; máximo 8)')
    parser.add_argument('--json',help='Guardar también los resultados por archivo en JSON privado')
    args=parser.parse_args()
    carpeta=Path(__file__).resolve().parent
    pruebas=sorted(p for p in carpeta.glob('prueba_*.py') if not args.solo or args.solo in p.name)
    if not pruebas:
        print('No encontré pruebas con ese nombre.');return 2
    if not 1<=args.procesos<=8:parser.error('--procesos debe estar entre 1 y 8')
    total=0;fallos=[];resultados=[];inicio=time.monotonic()
    with ThreadPoolExecutor(max_workers=args.procesos) as cola:
        # map conserva el orden al presentar; la ejecución ocurre en procesos.
        for r in cola.map(ejecutar_archivo,pruebas):
            resultados.append(r);total+=r['total']
            print(('✓' if r['ok'] else '✗')+f" {r['archivo']}: {r['total']} pruebas",flush=True)
            if not r['ok']:fallos.append(r['archivo']);print(r['salida'],flush=True)
    print(f'\nTotal: {total} pruebas. Archivos con fallos: {len(fallos)}.')
    if args.json:
        dato={'total':total,'fallos':fallos,'procesos':args.procesos,'segundos':round(time.monotonic()-inicio,4),'resultados':resultados}
        fd=os.open(args.json,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:json.dump(dato,f,ensure_ascii=False,indent=2);f.write('\n')
    return 1 if fallos else 0


if __name__=='__main__':raise SystemExit(main())
