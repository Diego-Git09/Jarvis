"""Lectura local y acotada de adjuntos para el chat de Jarvis.

Los formatos de código y datos se tratan siempre como texto: nunca se ejecutan.
Los archivos originales no se copian ni se modifican.
"""
from __future__ import annotations

import base64
import io
import re
import shutil
import subprocess
import tempfile
from zip_acotado import ZipFileAcotado
from pathlib import Path
from xml.etree import ElementTree

MAX_ARCHIVO = 20 * 1024 * 1024
MAX_TEXTO = 10_000
MAX_IMAGEN = 8 * 1024 * 1024
EXTENSIONES_TEXTO = {'.txt', '.md', '.py', '.sql', '.csv', '.tsv', '.json', '.jsonl',
                     '.yaml', '.yml', '.toml', '.ini', '.cfg', '.log', '.html', '.htm',
                     '.css', '.js', '.ts', '.sh', '.xml', '.rst'}
EXTENSIONES_TEXTO |= {'.java','.kt','.kts','.gradle','.properties','.c','.h','.cpp','.hpp','.cs','.go','.rs','.rb','.php','.dart','.r','.scala','.jsx','.tsx','.scss','.vue','.svelte','.ipynb','.ps1','.bat','.sql','.tex','.svg'}
EXTENSIONES_IMAGEN = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}


def _acotar(texto: str) -> tuple[str, bool]:
    return (texto[:MAX_TEXTO], len(texto) > MAX_TEXTO)


def _texto_docx(datos: bytes) -> str:
    with ZipFileAcotado(io.BytesIO(datos)) as z:
        _limitar_zip_compat(z)
        raiz = ElementTree.fromstring(z.read('word/document.xml'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paras = []
    for p in raiz.findall('.//w:p', ns):
        linea = ''.join(t.text or '' for t in p.findall('.//w:t', ns)).strip()
        if linea:
            paras.append(linea)
    return '\n'.join(paras)


def _texto_xlsx(datos: bytes) -> str:
    with ZipFileAcotado(io.BytesIO(datos)) as z:
        _limitar_zip_compat(z)
        nombres = set(z.namelist())
        shared = []
        if 'xl/sharedStrings.xml' in nombres:
            raiz = ElementTree.fromstring(z.read('xl/sharedStrings.xml'))
            shared = [''.join(t.text or '' for t in item.iter()
                              if t.tag.rsplit('}', 1)[-1] == 't')
                      for item in raiz if item.tag.rsplit('}', 1)[-1] == 'si']
        workbook = ElementTree.fromstring(z.read('xl/workbook.xml'))
        rels = ElementTree.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        relmap = {r.attrib['Id']: r.attrib['Target'] for r in rels}
        out = []
        for sheet in workbook.iter():
            if sheet.tag.rsplit('}', 1)[-1] != 'sheet':
                continue
            title = sheet.attrib.get('name', 'Hoja')
            rel_id = next((v for k, v in sheet.attrib.items() if k.endswith('}id')), None)
            target = relmap.get(rel_id, '')
            ruta = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            ruta = str(Path('xl') / ruta).replace('xl/xl/', 'xl/')
            if ruta not in nombres:
                continue
            root = ElementTree.fromstring(z.read(ruta))
            filas = []
            for row in root.iter():
                if row.tag.rsplit('}', 1)[-1] != 'row':
                    continue
                celdas = []
                for cell in row:
                    if cell.tag.rsplit('}', 1)[-1] != 'c':
                        continue
                    value = next((c for c in cell if c.tag.rsplit('}', 1)[-1] == 'v'), None)
                    inline = next((c for c in cell if c.tag.rsplit('}', 1)[-1] == 'is'), None)
                    texto = ''.join(t.text or '' for t in inline.iter()
                                    if t.tag.rsplit('}', 1)[-1] == 't') if inline is not None else (value.text or '' if value is not None else '')
                    if cell.attrib.get('t') == 's' and texto.isdigit():
                        i = int(texto)
                        texto = shared[i] if i < len(shared) else texto
                    celdas.append(f"{cell.attrib.get('r', '')}={texto}")
                if celdas:
                    filas.append(' | '.join(celdas))
            out.append(f'Hoja: {title}\n' + '\n'.join(filas))
        return '\n\n'.join(out)


def _texto_pptx(datos: bytes) -> str:
    with ZipFileAcotado(io.BytesIO(datos)) as z:
        items=z.infolist()
        _limitar_zip_compat(z)
        slides=sorted((i.filename for i in items if re.fullmatch(r'ppt/slides/slide\d+\.xml',i.filename)),
                      key=lambda n:int(re.search(r'slide(\d+)',n).group(1)))
        out=[]
        for index,name in enumerate(slides,1):
            root=ElementTree.fromstring(z.read(name))
            textos=[x.text or '' for x in root.iter() if x.tag.rsplit('}',1)[-1]=='t']
            texto=' '.join(t for t in textos if t).strip()
            if texto:out.append(f'Diapositiva {index}: {texto}')
        return '\n'.join(out)


def _limitar_zip_compat(z):
    """Los adaptadores privados de bytes solo admiten documentos diminutos.

    Las rutas públicas usan el lector progresivo aislado. Se conservan estos
    adaptadores por compatibilidad, con un máximo expandido total de 1 MiB.
    """
    if sum(i.file_size for i in z.infolist())>1024**2:
        raise ValueError('El adaptador de bytes admite hasta 1 MiB expandido; usa leer_adjunto para lectura progresiva.')


def _extraer_aislado(archivo,maximo,pagina=None):
    """Acumula solo el prefijo autorizado de un lector local aislado.

    EI redacta antes del IPC y mata su grupo al cerrar este generador. El byte
    extra distingue una extracción exacta del recorte, sin reservar el archivo.
    """
    import extraccion_aislada as EI
    import tandas_documentales as T
    from lectores_adjuntos import extension
    limites=T.limites();limites['mb_archivo']=min(limites['mb_archivo'],MAX_ARCHIVO//1024**2)
    # El lector conserva el límite de fuente configurado. Una unidad XML se
    # valida antes de emitirla; el padre solo acumula ``maximo`` caracteres y
    # cierra el proceso en cuanto llega una continuación fuera de ese prefijo.
    item={'ruta':str(archivo),'nombre':archivo.name,'tipo':extension(archivo.name)}
    if pagina is not None:item['_pagina_documento']=pagina
    unidades=EI.unidades(item,limites,recursos=T.recursos());partes=[];cantidad=0;cortado=False;anterior='';hoja_anterior=''
    ext=extension(archivo.name)
    try:
        for ref,texto in unidades:
            fragmentado=re.search(r' · fragmento (\d+), desde carácter \d+$',ref)
            unidad=re.sub(r' · fragmento \d+, desde carácter \d+$','',ref)
            separador=''
            if ext in {'.xlsx','.xlsm'}:
                m=re.search(r' · hoja (.+?) · filas \d+-\d+',ref)
                if m:
                    hoja=m[1]
                    if hoja!=hoja_anterior:
                        texto='Hoja: '+hoja+'\n'+texto;hoja_anterior=hoja
                    texto=re.sub(r'(?m)^Fila \d+: ','',texto)
                if partes and anterior!=unidad:separador='\n'
            elif ext=='.pptx':
                m=re.search(r' · diapositiva (\d+)',ref)
                if m and unidad!=anterior:texto='Diapositiva '+m[1]+': '+texto
                if partes and anterior!=unidad:separador='\n'
                elif partes and (not fragmentado or fragmentado[1]=='1'):separador=' '
            elif ext not in EXTENSIONES_TEXTO and partes and anterior!=unidad:
                separador='\n'
            fragmento=separador+texto;restante=maximo-cantidad
            partes.append(fragmento[:restante]);cantidad+=min(restante,len(fragmento));anterior=unidad
            if len(fragmento)>restante:cortado=True;break
    finally:unidades.close()
    item['cortado']=bool(item.get('cortado') or cortado)
    return ''.join(partes),item


def _texto_pdf(ruta: Path) -> str:
    exe = shutil.which('pdftotext')
    if not exe:
        raise ValueError('No está instalado pdftotext; el PDF no se ha enviado ni convertido.')
    with tempfile.TemporaryDirectory(prefix='jarvis-pdf-') as tmp:
        salida = Path(tmp) / 'documento.txt'
        p = subprocess.run([exe, '-enc', 'UTF-8', str(ruta), str(salida)],
                           capture_output=True, text=True, timeout=25, check=False)
        if p.returncode != 0:
            raise ValueError('No pude extraer el texto del PDF; puede estar protegido o ser solo imagen.')
        if not salida.exists():
            return ''
        with salida.open('rb') as f:
            raw=f.read(MAX_TEXTO*4+1)
        return raw.decode('utf-8', errors='replace')


def _convertir_office(ruta: Path, formato: str) -> str:
    # Un único adaptador, incluso para llamadas heredadas: sin fallback a
    # LibreOffice fuera de su perfil privado, namespaces y límites propios.
    from office_seguro import convertir
    return convertir(ruta,formato,max_caracteres=MAX_TEXTO)


def leer_adjunto(ruta: str | Path, modelo: str = '') -> dict:
    import acceso_archivos
    if acceso_archivos.protegida(ruta):raise ValueError('El adjunto pertenece a una ruta protegida; no se leyó.')
    archivo = Path(ruta).expanduser().resolve(strict=True)
    if not archivo.is_file():
        raise ValueError('El adjunto no es un archivo normal.')
    tamano = archivo.stat().st_size
    if tamano > MAX_ARCHIVO:
        raise ValueError('El archivo supera el límite local de 20 MB.')
    ext = archivo.suffix.lower()
    if ext in EXTENSIONES_IMAGEN:
        if tamano > MAX_IMAGEN:
            raise ValueError('La imagen supera el límite local de 8 MB.')
        vision = bool(re.search(r'(?:vision|vl|llava|bakllava|moondream|minicpm-v|gemma3)', modelo, re.I))
        if not vision:
            return {'nombre': archivo.name, 'tipo': 'imagen', 'texto': '', 'imagen': None,
                    'aviso': 'El modelo actual no anuncia capacidad visual. Elige un modelo multimodal (VL/Vision/LLaVA) para analizarla.'}
        # Base64 necesita el contenido completo, pero la lectura también queda
        # acotada si el archivo crece después de consultar su tamaño.
        with archivo.open('rb') as f:datos=f.read(MAX_IMAGEN+1)
        if len(datos)>MAX_IMAGEN:raise ValueError('La imagen supera el límite local de 8 MB.')
        encoded = base64.b64encode(datos).decode('ascii')
        return {'nombre': archivo.name, 'tipo': 'imagen', 'texto': '', 'imagen': encoded, 'aviso': ''}
    antes=archivo.stat();firma=(antes.st_size,antes.st_mtime_ns,antes.st_ino)
    texto,item=_extraer_aislado(archivo,MAX_TEXTO)
    despues=archivo.stat()
    if firma!=(despues.st_size,despues.st_mtime_ns,despues.st_ino):raise ValueError('El adjunto cambió durante la lectura; vuelve a abrirlo.')
    cortado=item.get('cortado',False)
    if not texto.strip():
        raise ValueError(item.get('aviso') or 'No encontré texto extraíble en el archivo.')
    return {'nombre': archivo.name, 'ruta':str(archivo), 'tipo': 'texto', 'texto': texto,
            'imagen': None, 'cortado': cortado,
            'aviso': (str(item.get('aviso',''))+' '+('Texto recortado al límite local.' if cortado else '')).strip()}


def modelo_con_vision(nombre: str) -> bool:
    return bool(re.search(r'(?:vision|vl|llava|bakllava|moondream|minicpm-v|gemma3)', nombre or '', re.I))


def recordar_referencia(adjuntos,estado):
    """Un documento inequívoco reemplaza al anterior; varios no eligen uno."""
    if not adjuntos:return
    anteriores=estado.get('_adjuntos_orden',[])
    estado['_adjuntos_anteriores']=anteriores
    estado['_adjuntos_orden']=[{'nombre':str(a.get('nombre','')),'ruta':str(a['ruta'])} for a in adjuntos if a.get('ruta')]
    for clave in ('_documento_tramo','_referencia_documental','_objetivo_documental','_archivo_foco'):estado.pop(clave,None)
    documentos=[a for a in adjuntos if a.get('ruta') and Path(a['ruta']).suffix.casefold() in {'.pdf','.docx','.xlsx','.pptx','.doc','.xls','.ppt'}]
    if len(documentos)!=1:return
    import herramientas_lectura as L
    from documentos_jarvis import firma
    try:
        ruta=L._resolver(documentos[0]['ruta'])
        adjunto=documentos[0]
        siguiente=({'inicio':1,'offset':0 if ruta.suffix.casefold()=='.pdf' else len(adjunto.get('texto',''))} if adjunto.get('cortado') else None)
        estado['_documento_tramo']={'ruta':str(ruta),'firma':firma(ruta),'siguiente':siguiente}
        estado['_archivo_foco']=str(ruta)
    except (OSError,ValueError,L.FueraDeAlcance):return


def resolver_adjunto(texto,estado):
    """Referencia al último lote por posición o nombre, sin leer ni autorizar."""
    from normalizacion_entrada import plegar
    n=plegar(texto).strip(' ¿?¡!.')
    n=re.sub(r'^(?:el|la|archivo|documento|adjunto)\s+','',n)
    n=re.sub(r'^(?:archivo|documento|adjunto)\s+','',n)
    if n in {'de antes','anterior','el de antes','lo de antes'}:
        candidatos=estado.get('_adjuntos_anteriores',[])
    else:
        lote=estado.get('_adjuntos_orden',[])
        ordinales={'primero':0,'primera':0,'segundo':1,'segunda':1,'tercero':2,'tercera':2,'cuarto':3,'cuarta':3,'quinto':4,'quinta':4}
        if n in ordinales:
            i=ordinales[n]
            if i>=len(lote):raise ValueError('Entendí la posición '+str(i+1)+', pero no existe en el último lote. Elige: 1. Adjuntar ese archivo. 2. Indicar su nombre o ruta.')
            return lote[i]['ruta']
        candidatos=[a for a in lote if n==plegar(a['nombre']) or n==plegar(Path(a['nombre']).stem) or n in {'antes de iniciar','despues de iniciar'} and n in plegar(a['nombre'])]
    if len(candidatos)==1:return candidatos[0]['ruta']
    if candidatos:raise ValueError('Entendí una referencia a un adjunto, pero coincide con varios. Elige su nombre: '+', '.join(a['nombre'] for a in candidatos[:3]))
    return None
