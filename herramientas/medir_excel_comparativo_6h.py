"""Contraste aislado con el lector del commit base y el lector actual.

Ejecuta únicamente código del repositorio, nunca código de los documentos.
Fuente sintética idéntica y extracción de 2 M caracteres en ambas versiones.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

def worker(d):
    p=Path(d['archivo']);inicio=time.monotonic()
    if d['lector']=='base':
        spec=importlib.util.spec_from_file_location('libros_base',d['codigo_base']);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    else:import libros_jarvis as mod
    r=mod.estadisticas(p) if d.get('estadisticas') else mod.extraer(p)
    texto='\n'.join(t for _,t in r.get('textos',[]))
    print(json.dumps({'lector':d['lector'],'accion':'estadisticas' if d.get('estadisticas') else 'extraer_2M','segundos':round(time.monotonic()-inicio,4),'filas':r.get('filas',sum(h['filas_leidas'] for h in r['hojas'])) if not d.get('estadisticas') else r['filas'],'texto_sha256':hashlib.sha256(texto.encode()).hexdigest() if texto else None,'texto_caracteres':len(texto),'cortado':r.get('cortado',not r.get('completo')),'suma_A':r['hojas'][0].get('sumas_numericas',{}).get('A')}))

def main(salida):
    import psutil
    from medir_adjuntos_pesados_6h import xlsx
    with tempfile.TemporaryDirectory(prefix='jarvis-excel-comparativo-') as tmp:
        raiz=Path(tmp);trabajo=raiz/'trabajo';trabajo.mkdir();p=trabajo/'100001_filas.xlsx';xlsx(p)
        viejo=raiz/'libros_base.py';viejo.write_text(subprocess.check_output(['git','show','db9bc66:herramientas/libros_jarvis.py'],text=True));env=dict(os.environ,JARVIS_DIR=str(raiz),JARVIS_PRUEBAS='1',PYTHONDONTWRITEBYTECODE='1');rs=[]
        for lector,stats in [('base',False),('actual',False),('actual',True)]:
            d={'archivo':str(p),'lector':lector,'estadisticas':stats,'codigo_base':str(viejo)};proc=subprocess.Popen([sys.executable,'-B',__file__,'--worker',json.dumps(d)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);ps=psutil.Process(proc.pid);rss=0
            while proc.poll() is None:
                try:rss=max(rss,ps.memory_info().rss)
                except psutil.Error:pass
                time.sleep(.005)
            out,err=proc.communicate()
            if proc.returncode:raise ValueError(err[-2000:])
            r=json.loads(out);r['rss_observado_mib']=round(rss/1024**2,2);rs.append(r)
        resultado={'sintetico':True,'ollama':False,'aislado_secuencial':True,'muestreo_ms':5,'commit_base':'db9bc66','codigo_base_sha256':hashlib.sha256(viejo.read_bytes()).hexdigest(),'fuente_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'resultados':rs,'extraccion_equivalente':rs[0]['texto_sha256']==rs[1]['texto_sha256'],'estadisticas_100001_correctas':rs[2]['filas']==100001 and rs[2]['suma_A']==str(100001*100002//2)}
        salida.write_text(json.dumps(resultado,ensure_ascii=False,indent=2));os.chmod(salida,0o600);print(json.dumps(resultado,ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--worker');ap.add_argument('--salida',type=Path);a=ap.parse_args()
    if a.worker:worker(json.loads(a.worker))
    elif a.salida:main(a.salida)
