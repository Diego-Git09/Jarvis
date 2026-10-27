"""Lectura incremental equivalente: revisión anterior y actual, sin modelos."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

RAIZ=Path(__file__).resolve().parents[1]/'registros/reportes/mejora_6h_20261014/redaccion_bordes'
ESPECIFICACION={'version':1,'caracteres_fuente':2_000_000,'repeticiones_por_proceso':3,'mb_proceso':256,
               'revision_anterior':'8b2934b','casos':['texto_publico_sin_saltos','campo_sensible_abierto'],'rss_muestreo_ms':5,
               'regla':'Procesos nuevos secuenciales sobre las mismas fuentes. SHA de salida pública igual; en fuente sensible cambia la salida por redacción, sin guardar sus valores.'}


def congelar():
    raw=(json.dumps(ESPECIFICACION,ensure_ascii=False,indent=2)+'\n').encode();sha=hashlib.sha256(raw).hexdigest();RAIZ.mkdir(parents=True,exist_ok=True);RAIZ.chmod(0o700);p=RAIZ/'comparacion_especificacion.json'
    if p.exists() and p.read_bytes()!=raw:raise ValueError('No modificar especificación congelada.')
    if not p.exists():p.write_bytes(raw)
    p.chmod(0o600);p.with_suffix('.sha256').write_text(sha+'\n');p.with_suffix('.sha256').chmod(0o600);return sha


def worker(a):
    import resource
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import extraccion_aislada as E
    E._limitar({'mb_proceso':256,'segundos_archivo':60})
    if a.lector=='anterior':
        spec=importlib.util.spec_from_file_location('lector_anterior',a.baseline);L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)
    else:import lectores_adjuntos as L
    filas=[]
    for _ in range(ESPECIFICACION['repeticiones_por_proceso']):
        item={'nombre':'fuente.txt'};sha=hashlib.sha256();caracteres=0;unidades=0;inseguro=False;publico=False;inicio=time.monotonic()
        with Path(a.fuente).open('rb') as f:
            for _,txt in L.bloques_texto(f,item,ESPECIFICACION['caracteres_fuente']):
                sha.update(txt.encode());caracteres+=len(txt);unidades+=1
                inseguro=inseguro or 'FICTICIO_SIN_USO_73' in txt;publico=publico or 'FIN_PUBLICO_STREAM' in txt
        filas.append({'segundos':round(time.monotonic()-inicio,6),'salida_sha256':sha.hexdigest(),'caracteres_salida':caracteres,'unidades':unidades,
                      'valor_ficticio_visible':inseguro,'marcador_publico_visible':publico,'parcial':bool(item.get('cortado'))})
    print(json.dumps({'lector':a.lector,'caso':a.caso,'repeticiones':filas,'mediana_segundos':statistics.median(x['segundos'] for x in filas),
          'ru_maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'sha256_lector':hashlib.sha256(Path(L.__file__).read_bytes()).hexdigest()}))


def main(salida=None):
    sha=congelar()
    if salida is None:print(json.dumps({'especificacion_sha256':sha}));return
    if salida.exists():raise ValueError('No sobrescribir mediciones anteriores.')
    import psutil
    with tempfile.TemporaryDirectory(prefix='jarvis-comparacion-redaccion-') as tmp:
        base=Path(tmp);(base/'trabajo').mkdir();viejo=base/'lector_anterior.py'
        viejo.write_bytes(subprocess.check_output(['git','show','8b2934b:herramientas/lectores_adjuntos.py']));viejo.chmod(0o600)
        longitud=ESPECIFICACION['caracteres_fuente'];frase='Revisión pública de archivos y líneas sin datos privados. '
        texto=(frase*(longitud//len(frase)+1))[:longitud-20]+'FIN_PUBLICO_STREAM\n';texto=texto.ljust(longitud,' ')
        fuentes={'texto_publico_sin_saltos':texto,
          'campo_sensible_abierto':('x '*500000)+'PASSWORD'+(' '*20000)+'=VALOR_FICTICIO_SIN_USO_73\nFIN_PUBLICO_STREAM\n'}
        resultados=[];huellas={}
        for caso,contenido in fuentes.items():
            p=base/'trabajo'/(caso+'.txt');p.write_text(contenido);antes=hashlib.sha256(p.read_bytes()).hexdigest();huellas[caso]=antes
            for lector in ['anterior','actual']:
                cmd=[sys.executable,'-I','-B',str(Path(__file__).resolve()),'--worker','--lector',lector,'--fuente',str(p),'--baseline',str(viejo),'--caso',caso]
                env={'PATH':os.defpath,'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','JARVIS_DIR':tmp,'JARVIS_PRUEBAS':'1'}
                proc=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);ps=psutil.Process(proc.pid);rss=0;inicio=time.monotonic()
                while proc.poll() is None:
                    if time.monotonic()-inicio>90:proc.kill();raise TimeoutError('La medición excedió90s.')
                    try:rss=max(rss,ps.memory_info().rss)
                    except psutil.Error:pass
                    time.sleep(.005)
                out,err=proc.communicate()
                if proc.returncode:raise ValueError('Falló el proceso comparativo; salida de diagnóstico no publicada.')
                r=json.loads(out);r.update(rss_max_muestreado_mib=round(rss/1024**2,3),fuente_intacta=hashlib.sha256(p.read_bytes()).hexdigest()==antes)
                resultados.append(r)
        publicos=[x for x in resultados if x['caso']=='texto_publico_sin_saltos'];actual=next(x for x in resultados if x['caso']=='campo_sensible_abierto' and x['lector']=='actual')
        r={'especificacion_sha256':sha,'fuentes_sha256':huellas,'resultados':resultados,'publico_sha_igual':len({z['salida_sha256'] for x in publicos for z in x['repeticiones']})==1,
           'sensible_actual_redactado':all(not z['valor_ficticio_visible'] and z['marcador_publico_visible'] for z in actual['repeticiones']),
           'alcance':'Dos fuentes ficticias,3 repeticiones por proceso, procesos nuevos secuenciales con256MiBAS. Sin modelo/MCP/red; RSS muestreado5ms, no pico continuo garantizado. Preparación fuera del cronómetro.'}
        salida.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');salida.chmod(0o600);print(json.dumps(r,ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');ap.add_argument('--salida',type=Path);ap.add_argument('--lector');ap.add_argument('--fuente');ap.add_argument('--baseline');ap.add_argument('--caso');a=ap.parse_args()
    if a.worker:worker(a)
    else:main(a.salida)
