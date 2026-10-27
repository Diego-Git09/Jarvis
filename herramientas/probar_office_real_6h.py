"""Prueba Office local aislada con un ODT generado, sin macros ni datos reales."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import tempfile
import threading
import time
import zipfile

RAIZ=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--ronda',required=True);p.add_argument('--as-mib',type=int,choices=[128,256,512,1024],default=1024);a=p.parse_args()
    if not a.ronda.replace('_','').isalnum():raise ValueError('Ronda inválida.')
    salida=RAIZ/'registros/reportes/mejora_6h_20261014/office'/(a.ronda+'.json')
    if salida.exists():raise ValueError('La ronda anterior se conserva.')
    with tempfile.TemporaryDirectory(prefix='jarvis-office-probe-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1')
        base=Path(tmp);trabajo=base/'trabajo';trabajo.mkdir()
        import office_seguro as O
        O.MAX_AS=a.as_mib*1024**2
        fuente=trabajo/'fuente.odt'
        with zipfile.ZipFile(fuente,'w') as z:
            z.writestr('mimetype','application/vnd.oasis.opendocument.text',compress_type=zipfile.ZIP_STORED)
            z.writestr('META-INF/manifest.xml','''<?xml version="1.0"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>''')
            z.writestr('content.xml','''<?xml version="1.0"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2"><office:body><office:text><text:p>PROBE_ORO_A17 presupuesto 271</text:p></office:text></office:body></office:document-content>''')
        original=hashlib.sha256(fuente.read_bytes()).hexdigest()
        perfil=base/'perfil';destino=base/'salida';perfil.mkdir();destino.mkdir();O._perfil(perfil)
        registro=base/'conversion.log';bwrap,prlimit=O._herramientas()
        cmd=O._comando(fuente,destino,perfil,O.FORMATOS['txt:Text'][0],bwrap,prlimit)
        inicio=time.monotonic();error='';muestras=[];raices=[];detener=threading.Event()
        real_popen=O.subprocess.Popen
        def lanzar(*args,**kw):
            proc=real_popen(*args,**kw);raices.append(proc.pid);return proc
        def muestrear():
            while not detener.wait(.01):
                vistos=set();cola=list(raices);rss=0;vm=0
                while cola:
                    pid=cola.pop()
                    if pid in vistos:continue
                    vistos.add(pid)
                    try:
                        meta={l.split(':',1)[0]:l.split(':',1)[1].strip() for l in Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in l}
                        rss+=int(meta.get('VmRSS','0 kB').split()[0]);vm+=int(meta.get('VmSize','0 kB').split()[0])
                        for t in Path(f'/proc/{pid}/task').glob('*/children'):
                            try:cola.extend(int(p) for p in t.read_text().split())
                            except (OSError,ValueError):pass
                    except (OSError,ValueError):pass
                muestras.append({'rss_arbol_kib':rss,'vm_arbol_kib':vm,'procesos':len(vistos)})
        hilo=threading.Thread(target=muestrear,daemon=True);hilo.start();O.subprocess.Popen=lanzar
        try:
            try:O._ejecutar(cmd,registro,perfil)
            except (OSError,ValueError) as e:error=type(e).__name__+': '+str(e)
        finally:O.subprocess.Popen=real_popen;detener.set();hilo.join(1)
        texto=(destino/'fuente.txt').read_text(errors='replace') if (destino/'fuente.txt').is_file() else ''
        d={'ronda':a.ronda,'sintetico':True,'sin_macros':True,'ok':'PROBE_ORO_A17' in texto and not error,
           'error':error,'salida':texto[:4000],'log':registro.read_text(errors='replace')[:16000] if registro.exists() else '',
           'segundos':round(time.monotonic()-inicio,4),'rss_max_hijo_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
           'rss_arbol_max_mib':round(max((x['rss_arbol_kib'] for x in muestras),default=0)/1024,2),'muestras':len(muestras),
           'vm_arbol_max_mib':round(max((x['vm_arbol_kib'] for x in muestras),default=0)/1024,2),
           'as_max_configurado_mib':O.MAX_AS//1024**2,'original_intacto':original==hashlib.sha256(fuente.read_bytes()).hexdigest(),
           'montajes_lectura':[(cmd[i+1],cmd[i+2]) for i,x in enumerate(cmd) if x=='--ro-bind'],
           'alcance':'Conversión real de un ODT mínimo. No prueba todos los formatos ni bloqueo de una macro real. RSS del árbol sumado cada10ms (puede contar memoria compartida varias veces); no es cota continua. Solo rutas temporales autorizadas.'}
        salida.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.chmod(salida,0o600)
        print(json.dumps(d,ensure_ascii=False))
        return 0 if d['ok'] and d['original_intacto'] else 1


if __name__=='__main__':raise SystemExit(main())
