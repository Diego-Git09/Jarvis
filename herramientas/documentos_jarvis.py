"""Extrae documentos autorizados por tramos locales; no envía nada a una API."""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import adjuntos_jarvis as A

EXTENSIONES={'.pdf','.docx','.xlsx','.xlsm','.pptx','.doc','.xls','.ppt','.odt','.ods','.odp','.epub'}
MAX_TRAMO=4000
MAX_EXTRAIDO=500_000


def firma(archivo):
    s=archivo.stat();return f'{s.st_size}:{s.st_mtime_ns}:{s.st_ino}'


def _error_pdf(detalle):
    # El diagnóstico se usa para clasificar; no se muestra el stderr, que
    # puede incluir rutas, fragmentos del documento o miles de advertencias.
    texto=(detalle.decode('utf-8',errors='replace') if isinstance(detalle,bytes) else str(detalle))[:4096].casefold()
    if re.search(r'(?:^|\n)(?:(?:command line|syntax) error:\s*)?(?:incorrect password|password (?:is )?required)\b',texto):
        return 'El PDF requiere una contraseña para leerlo. Adjunta una copia que puedas abrir sin clave.'
    if re.search(r'(?:^|\n)permission error:',texto):
        return 'El PDF restringe la extracción de texto. Adjunta una copia que permita extraerlo.'
    if re.search(r'(?:^|\n)i/o error:.*permission denied',texto):
        return 'El sistema no permite leer este PDF. Revisa los permisos del archivo.'
    return 'No pude leer el PDF: puede estar incompleto, dañado o tener una estructura no admitida.'


def _pdf(archivo,inicio):
    info=shutil.which('pdfinfo');exe=shutil.which('pdftotext')
    if not info or not exe:raise ValueError('Necesito pdfinfo y pdftotext para leer el PDF localmente.')
    meta=subprocess.run([info,str(archivo)],capture_output=True,text=True,timeout=20,env=dict(os.environ,LC_ALL='C'))
    m=re.search(r'^Pages:\s+(\d+)',meta.stdout,re.M)
    if meta.returncode or not m:raise ValueError(_error_pdf(meta.stderr))
    total=int(m[1])
    if inicio>total:raise ValueError(f'El PDF tiene {total} páginas. Elige una página entre 1 y {total}.')
    with tempfile.TemporaryDirectory(prefix='jarvis-documento-') as tmp:
        salida=Path(tmp)/'pagina.txt'
        r=subprocess.run([exe,'-f',str(inicio),'-l',str(inicio),'-enc','UTF-8',str(archivo),str(salida)],capture_output=True,timeout=25)
        if r.returncode or not salida.exists():raise ValueError(_error_pdf(r.stderr))
        with salida.open('rb') as f:datos=f.read(MAX_EXTRAIDO*4+1)
        texto=datos.decode('utf-8',errors='replace').rstrip('\f\n')
        return texto[:MAX_EXTRAIDO],total,len(texto)>MAX_EXTRAIDO


def leer(archivo,inicio=1,offset=0):
    if type(inicio) is not int or inicio<1 or type(offset) is not int or offset<0:raise ValueError('Página/tramo y desplazamiento deben ser enteros válidos.')
    if archivo.stat().st_size>A.MAX_ARCHIVO:raise ValueError('El documento supera el límite local de 20 MB.')
    antes=firma(archivo);ext=archivo.suffix.lower()
    if ext=='.pdf':
        texto,item=A._extraer_aislado(archivo,MAX_EXTRAIDO,pagina=inicio)
        total=item.get('paginas')
        if type(total) is not int or total<inicio:raise ValueError('El lector no confirmó el número de páginas del PDF.')
        limitado=item.get('cortado',False);unidad='página'
    else:
        if inicio!=1:raise ValueError('Para este formato continúa con /mas_documento o usa un desplazamiento de texto.')
        if ext not in EXTENSIONES:raise ValueError('Formato de documento no admitido.')
        texto,item=A._extraer_aislado(archivo,MAX_EXTRAIDO)
        limitado=item.get('cortado',False);total=1;unidad='documento'
    if firma(archivo)!=antes:raise ValueError('El documento cambió durante la lectura. Vuelve a abrirlo.')
    if offset>len(texto):raise ValueError('Ese desplazamiento está fuera del texto extraído.')
    contenido=texto[offset:offset+MAX_TRAMO]
    restante=offset+len(contenido)<len(texto)
    siguiente={'inicio':inicio,'offset':offset+len(contenido)} if restante else {'inicio':inicio+1,'offset':0} if ext=='.pdf' and inicio<total else None
    aviso=str(item.get('aviso',''))
    if not texto.strip() and item.get('soporte')!='SOLO METADATOS':aviso=(aviso+' '+('Esta página' if ext=='.pdf' else 'Este documento')+' no tiene texto extraíble. Puede contener imágenes escaneadas; no hice OCR.').strip()
    if limitado:aviso+=' Se alcanzó el límite de extracción de esta página/documento; puede faltar texto.'
    return {'contenido':contenido,'inicio':inicio,'offset':offset,'total_paginas':total if ext=='.pdf' else None,
            'unidad':unidad,'siguiente_documento':siguiente,'firma':antes,'cortado':bool(siguiente or limitado),'aviso':aviso.strip()}
