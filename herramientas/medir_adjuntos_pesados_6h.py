"""Medición aislada de lectores con datos sintéticos; sin Ollama ni MCP.

La generación se realiza antes de medir cada proceso lector. No aumenta los
límites de indexación: los archivos de 201 MiB se inspeccionan por streaming.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

def pdf(p,n=301):
    objetos=[b'<< /Type /Catalog /Pages 2 0 R >>',('<< /Type /Pages /Kids ['+' '.join(f'{4+i*2} 0 R' for i in range(n))+f'] /Count {n} >>').encode(),b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    for i in range(n):
        contenido=f'BT /F1 12 Tf 40 700 Td (PAGINA_ORO_{i+1} EXISTENCIAS {i+7}) Tj ET'.encode()
        objetos.extend([f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {5+i*2} 0 R >>'.encode(),b'<< /Length '+str(len(contenido)).encode()+b' >>\nstream\n'+contenido+b'\nendstream'])
    with p.open('wb') as f:
        f.write(b'%PDF-1.4\n');offsets=[0]
        for i,obj in enumerate(objetos,1):offsets.append(f.tell());f.write(str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n')
        inicio=f.tell();f.write(f'xref\n0 {len(objetos)+1}\n0000000000 65535 f \n'.encode());f.write(b''.join(f'{x:010d} 00000 n \n'.encode() for x in offsets[1:]));f.write(f'trailer\n<< /Size {len(objetos)+1} /Root 1 0 R >>\nstartxref\n{inicio}\n%%EOF\n'.encode())

def xlsx(p,n=100001):
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('xl/workbook.xml','<workbook xmlns:r="urn:r"><sheets><sheet name="Ventas" r:id="r1"/></sheets></workbook>');z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        with z.open('xl/worksheets/sheet1.xml','w') as f:
            f.write(b'<worksheet><sheetData>')
            for i in range(1,n+1):f.write(f'<row r="{i}"><c r="A{i}"><v>{i}</v></c><c r="B{i}"><v>7</v></c></row>'.encode())
            f.write(b'</sheetData></worksheet>')

def texto_grande(p,linea,minimo=201*1024**2):
    filas=(minimo+len(linea)-1)//len(linea);bloque=linea*4096
    with p.open('wb') as f:
        for _ in range(filas//4096):f.write(bloque)
        f.write(linea*(filas%4096))
    return filas

def preparar(base,solo_pdf=False):
    casos=[];p=base/'301_paginas.pdf';pdf(p);casos.append({'id':'PESADO_PDF301','archivo':str(p),'accion':'pdf','oro':301})
    if solo_pdf:return casos
    p=base/'100001_filas.xlsx';xlsx(p);casos.append({'id':'PESADO_XLSX100001','archivo':str(p),'accion':'excel','oro':100001,'suma':str(100001*100002//2)})
    datos={'csv':b'7,producto ficticio,'+b'x'*190+b'\n','jsonl':b'{"cantidad":7,"texto":"'+b'x'*190+b'"}\n','log':b'INFO evento sintetico '+b'x'*190+b'\n','sql':b"INSERT INTO inventario VALUES(7,'"+b'x'*190+b"');\n"}
    for ext,linea in datos.items():
        p=base/('201_mib.'+ext);filas=texto_grande(p,linea);casos.append({'id':'PESADO_'+ext.upper(),'archivo':str(p),'accion':'texto','oro':filas,'suma':str(filas*7) if ext in {'csv','jsonl'} else None})
    p=base/'201_mib.json'
    with p.open('wb') as f:
        f.write(b'{"dato":"');bloque=b'x'*(1024**2)
        for _ in range(201):f.write(bloque)
        f.write(b'"}')
    casos.append({'id':'PESADO_JSON','archivo':str(p),'accion':'texto','oro':1})
    semilla=base/'miembro.txt'
    # Datos pseudoaleatorios reproducibles: la compresión no simula una bomba.
    bloque=b''.join(hashlib.sha256(str(i).encode()).digest() for i in range(32768))
    with semilla.open('wb') as f:
        for _ in range(19):f.write(bloque)
    for ext in ('zip','tar','tgz'):
        p=base/('190_mib.'+ext)
        if ext=='zip':
            with zipfile.ZipFile(p,'w') as z:
                for i in range(10):z.write(semilla,f'nota_{i}.txt')
        else:
            with tarfile.open(p,'w:gz' if ext=='tgz' else 'w') as z:
                for i in range(10):z.add(semilla,arcname=f'nota_{i}.txt',recursive=False)
        casos.append({'id':'PESADO_'+ext.upper(),'archivo':str(p),'accion':'archivo','oro':10})
    repo=base/'repo';repo.mkdir();(repo/'.gitignore').write_text('*.secret\ncache/\n')
    for i in range(150):(repo/f'codigo_{i}.py').write_text(f'# NO EJECUTAR\nDATO_REPO_{i} = {i}\n')
    for carpeta in ('node_modules','venv','.git','build','cache'):
        (repo/carpeta).mkdir();(repo/carpeta/'omitido.py').write_text('NO_LEER')
    (repo/'privado.secret').write_text('NO_LEER');casos.append({'id':'PESADO_REPO','archivo':str(repo),'accion':'repo','oro':151})
    return casos

def worker(c,aislado=False):
    import tandas_documentales as T
    import lectores_adjuntos as R
    p=Path(c['archivo']);inicio=time.monotonic()
    if c['accion']=='pdf':
        d=T.indexar(T.crear([p])['id'],False);r=T.buscar(d['id'],'PAGINA_ORO_301',presupuesto=5000);a=d['archivos'][0]
        ok=a.get('paginas_leidas')==301 and a['estado']=='indexado' and any('página 301' in x['referencia'] and 'PAGINA_ORO_301' in x['texto'] for x in r['trozos']);detalle={'fuente':a,'recuperacion':r}
    elif c['accion']=='repo':
        d=T.indexar(T.crear([p])['id'],False);ok=len(d['archivos'])==c['oro'] and all(a['estado']=='indexado' for a in d['archivos']);detalle={'archivos':len(d['archivos']),'nombres':[a['nombre'] for a in d['archivos']]}
    else:
        if aislado:
            from extraccion_aislada import analizar
            detalle=analizar(p)
        else:detalle=R.analizar(p)
        ok=detalle.get('completo',False)
        if c['accion']=='excel':ok=ok and detalle.get('filas')==c['oro'] and detalle['hojas'][0]['sumas_numericas'].get('A')==c['suma']
        elif c['accion']=='archivo':ok=ok and len(detalle.get('miembros',[]))==c['oro']
        else:
            ok=ok and detalle.get('lineas')==c['oro']
            if c.get('suma'):ok=ok and detalle.get('sumas_numericas_fisicas',{}).get('cantidad' if p.suffix=='.jsonl' else '1')==c['suma']
    print(json.dumps({'id':c['id'],'ok':ok,'segundos_lector':round(time.monotonic()-inicio,4),'detalle':detalle},ensure_ascii=False))

def main(salida,solo_pdf=False,aislado=False):
    import psutil
    if salida.exists():raise ValueError('La medición existe; usa otro nombre para conservarla.')
    with tempfile.TemporaryDirectory(prefix='jarvis-pesados-') as tmp:
        base=Path(tmp);trabajo=base/'trabajo';trabajo.mkdir();g=time.monotonic();casos=preparar(trabajo,solo_pdf);generacion=time.monotonic()-g;rs=[]
        env=dict(os.environ,JARVIS_DIR=str(base),JARVIS_PRUEBAS='1',PYTHONDONTWRITEBYTECODE='1')
        for caso in casos:
            comando=[sys.executable,'-B',__file__,'--worker',json.dumps(caso)]+(['--aislado'] if aislado else [])
            inicio=time.monotonic();p=subprocess.Popen(comando,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);proceso=psutil.Process(p.pid);rss=0;rss_arbol=0;hijos_vistos=set()
            while p.poll() is None:
                try:
                    memoria=proceso.memory_info().rss;rss=max(rss,memoria)
                    for hijo in proceso.children(recursive=True):
                        try:memoria+=hijo.memory_info().rss;hijos_vistos.add(hijo.name())
                        except psutil.Error:pass
                    rss_arbol=max(rss_arbol,memoria)
                except psutil.Error:pass
                time.sleep(.01)
            out,err=p.communicate();r=json.loads(out) if p.returncode==0 else {'id':caso['id'],'ok':False,'error':err[-2000:]};r.update(rss_max_mib=round(rss/1024**2,2),rss_arbol_observado_mib=round(rss_arbol/1024**2,2),hijos_observados=sorted(hijos_vistos),muestreo_ms=10,segundos_proceso=round(time.monotonic()-inicio,4),bytes=Path(caso['archivo']).stat().st_size);rs.append(r)
            print(caso['id'],r['ok'],r['rss_max_mib'],flush=True)
        salida.parent.mkdir(parents=True,exist_ok=True);salida.write_text(json.dumps({'sintetico':True,'ollama':False,'aislado_y_secuencial':True,'analisis_en_worker_limitado':aislado,'generacion_fuera_de_medicion_segundos':round(generacion,4),'resultados':rs},ensure_ascii=False,indent=2));os.chmod(salida,0o600)
        return 0 if all(x['ok'] for x in rs) else 1

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--worker');ap.add_argument('--salida',type=Path);ap.add_argument('--solo-pdf',action='store_true');ap.add_argument('--aislado',action='store_true');a=ap.parse_args()
    if a.worker:worker(json.loads(a.worker),a.aislado)
    elif a.salida:raise SystemExit(main(a.salida,a.solo_pdf,a.aislado))
