"""Registro y lectores locales acotados. Los contenidos son datos, nunca órdenes.

Cada lector produce unidades pequeñas con referencias. No extrae comprimidos al
disco, no evalúa SQL/macros y no interpreta instrucciones incrustadas.
"""
import codecs
import csv
import gzip
import io
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import zipfile
from zip_acotado import ZipFileAcotado
from xml.parsers import expat
from decimal import Decimal,InvalidOperation

TEXTO=set('.txt .md .rst .log .csv .tsv .json .jsonl .yaml .yml .toml .ini .cfg .xml .tex .srt .vtt .sql .py .java .kt .kts .gradle .js .ts .jsx .tsx .c .cpp .h .hpp .cs .go .rs .php .rb .sh .bat .ps1 .properties .css .scss .dart .r .scala .vue .svelte .svg'.split())
REGISTRO={e:('COMPLETO','Texto por bloques; sin ejecutar código ni consultas.') for e in TEXTO}
REGISTRO.update({e:('COMPLETO','Texto seguro por unidades; estilos/objetos incrustados no se interpretan.') for e in {'.html','.htm','.rtf','.ipynb','.eml','.mbox','.vcf','.ics','.env'}})
REGISTRO.update({e:('PARCIAL','Texto/celdas/páginas; no imágenes, macros, fórmulas ejecutadas ni formato visual.') for e in {'.pdf','.docx','.xlsx','.xlsm','.pptx','.odt','.ods','.odp','.epub'}})
REGISTRO.update({e:('PARCIAL','Esquema y hasta 20 filas de 100 tablas; texto hasta 1000 caracteres por celda, binarios solo tamaño y campos sensibles redactados. No ejecuta SQL del adjunto.') for e in {'.db','.sqlite','.sqlite3'}})
REGISTRO.update({e:('PARCIAL','Miembros seguros sin extracción al disco; límites de expansión y tiempo.') for e in {'.zip','.tar','.tgz','.gz'}})
REGISTRO.update({e:('PARCIAL','Texto por LibreOffice aislado, si existe con bwrap y perfil de memoria de al menos 512 MiB. Sin macros; XLS con fórmulas/nombres/vínculos se rechaza. Sin condiciones seguras, solo metadatos.') for e in {'.doc','.xls','.ppt'}})
REGISTRO.update({e:('SOLO METADATOS','El índice textual no ve imágenes. Usa un modelo visual instalado; /adjuntos ocr comprueba disponibilidad, sin ejecutar ni instalar OCR.') for e in {'.png','.jpg','.jpeg','.webp','.bmp','.gif','.tiff','.tif'}})
REGISTRO.update({e:('SOLO METADATOS','Tamaño/huella y, si ffprobe existe, códec/duración; sin transcripción.') for e in {'.mp3','.wav','.ogg','.m4a','.flac','.mp4','.mkv','.webm','.avi','.mov'}})
REGISTRO.update({e:('PARCIAL','Cabeceras/cuerpo literales; MIME, base64, quoted-printable y adjuntos internos sin decodificar.') for e in {'.eml','.mbox'}})
REGISTRO['.rtf']=('PARCIAL','Extracción aproximada de controles; Unicode enriquecido y formato no garantizados.')

def formatos():
    return 'Estado del lector por extensión (COMPLETO describe texto, no interpretación del modelo):\n'+'\n'.join(e+' · '+s+' · '+r for e,(s,r) in sorted(REGISTRO.items()))+'\nOtras extensiones: NO SOPORTADO · hash/tamaño, sin ejecutar.'

def extension(nombre):
    p=Path(nombre)
    if p.name.casefold() in {'.gitignore','.dockerignore','dockerfile','makefile','license','readme'}:return '.txt'
    return '.env' if p.name=='.env' or p.name.endswith('.env') else p.suffix.casefold()

def detectar(p,ext):
    with p.open('rb') as f:raw=f.read(8192)
    real=''
    if raw.startswith(b'%PDF-'):real='.pdf'
    elif raw.startswith(b'SQLite format 3\0'):real='.sqlite'
    elif raw.startswith(b'\x89PNG\r\n\x1a\n'):real='.png'
    elif raw.startswith(b'\xff\xd8\xff'):real='.jpg'
    elif raw.startswith((b'GIF87a',b'GIF89a')):real='.gif'
    elif raw[:4]==b'RIFF' and raw[8:12]==b'WEBP':real='.webp'
    elif raw.startswith(b'\x1f\x8b'):real='.tgz' if ext=='.tgz' or p.name.endswith('.tar.gz') else '.gz'
    elif raw.startswith(b'PK\x03\x04'):
        with ZipFileAcotado(p) as z:
            nombres=z.namelist()
            real='.docx' if 'word/document.xml' in nombres else '.xlsm' if 'xl/vbaProject.bin' in nombres else '.xlsx' if 'xl/workbook.xml' in nombres else '.pptx' if any(n.startswith('ppt/slides/') for n in nombres) else ext if 'content.xml' in nombres and ext in {'.odt','.ods','.odp'} else '.epub' if any(n.endswith('.xhtml') for n in nombres) and ext=='.epub' else '.zip'
    elif len(raw)>262 and raw[257:262]==b'ustar':real='.tar'
    elif raw.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):real=ext if ext in {'.doc','.xls','.ppt'} else '.doc'
    aviso=''
    equivalentes=real in {'.sqlite','.jpg'} and ext in {'.db','.sqlite','.sqlite3','.jpg','.jpeg'}
    if real and real!=ext and not equivalentes:aviso=f'Extensión {ext or "sin extensión"} distinta del contenido {real}; usé el tipo detectado.'
    return real or ext,aviso

def codificacion(raw):
    if raw.startswith((codecs.BOM_UTF16_LE,codecs.BOM_UTF16_BE)):return 'utf-16'
    if raw.startswith(codecs.BOM_UTF8):return 'utf-8-sig'
    if b'\0' in raw:
        # UTF-16 sin BOM solo si el patrón alternado es inequívoco.
        pares=raw[:8192]
        if len(pares)>4 and pares[1::2].count(0)>len(pares[1::2])*.65:return 'utf-16-le'
        if len(pares)>4 and pares[0::2].count(0)>len(pares[0::2])*.65:return 'utf-16-be'
        raise ValueError('Archivo binario, sin texto legible.')
    try:codecs.getincrementaldecoder('utf-8')(errors='strict').decode(raw,final=False);return 'utf-8-sig'
    except UnicodeDecodeError:
        try:raw.decode('cp1252');return 'cp1252'
        except UnicodeDecodeError:return 'latin-1'


_CAMPO_SENSIBLE_TRAMO=re.compile(r'(?i)(?:password|passwd|contrase[ñn]a|api[_ -]?key|access[_ -]?token|auth[_ -]?token|secret(?:[_ -]?key)?|private[_ -]?key|token|authorization|cookie)')
_SUFIJO_CAMPO_TRAMO=re.compile(r'[A-Za-z0-9_.-]{0,80}["\']?\s*(?:[:=]\s*["\']?|$)')
_TOKEN_TRAMO=re.compile(r'(?i)\b(?:Bearer\s+[A-Za-z0-9._~+/=-]{12,}|sk-[a-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|AKIA[0-9A-Z]{16}|hf_[0-9A-Za-z]{20,}|xox[baprs]-[0-9A-Za-z-]{12,}|gh[pousr]_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,}|eyJ[A-Za-z0-9_-]{10,})')
_URL_TRAMO=re.compile(r'(?i)https?://[^\s/@]+:[^\s/@]*(?:@|$)')
_MARCADOR_PRIVADO_TRAMO=re.compile(r'-----(?:BEGIN|END) [^-]*PRIVATE KEY-----')


def _inicio_sensible_pendiente(unidad,siguiente,env=False):
    """Localiza una posible credencial en la línea que aún no ha terminado.

    Hasta256 caracteres adicionales permiten reconocer un prefijo partido.
    Un campo abierto no necesita acumular sus espacios ni su valor completo:
    se omite la continuación hasta el fin de esa línea y se declara parcial.
    """
    inicio=unidad.rfind('\n')+1;actual=unidad[inicio:]
    if not actual:return None
    if env:return inicio  # Todos los valores .env son privados.
    ventana=(actual+siguiente[:256]).split('\n',1)[0];posiciones=[]
    # Filtro solo negativo: cada alternativa del detector detallado contiene
    # al menos una de estas señales. Evita tres búsquedas regex sobre el caso
    # habitual de texto público, sin decidir que un valor sea seguro.
    menor=ventana.casefold()
    if not any(s in menor for s in ('pass','contrase','api','token','secret','private','authoriz','cookie','bearer','sk-','aiza','akia','hf_','xox','gh','github','eyj','http')):return None
    for m in _CAMPO_SENSIBLE_TRAMO.finditer(ventana):
        if m.start()<len(actual) and _SUFIJO_CAMPO_TRAMO.match(ventana,m.end()):posiciones.append(m.start())
    for patron in (_TOKEN_TRAMO,_URL_TRAMO):
        posiciones.extend(m.start() for m in patron.finditer(ventana) if m.start()<len(actual))
    return inicio+min(posiciones) if posiciones else None


def _decodificar_bloque(dec,enc,raw,final,item):
    """No silencia bytes incompatibles que aparecen después del prefijo.

    Conserva lo ya decodificado y el prefijo válido del bloque fallido. Para
    texto de un byte intentaCP1252/Latin1; UTF16 dañado usa reemplazo marcado.
    La lectura pasa a parcial: esta recuperación no verifica la codificación
    de un archivo mixto ni cambia el original.
    """
    estado=dec.getstate()
    try:return dec,enc,dec.decode(raw,final=final)
    except UnicodeDecodeError as error:
        if enc.startswith('utf-16'):
            dec.setstate(estado);dec.errors='replace'
            try:texto=dec.decode(raw,final=final)
            finally:dec.errors='strict'
        else:
            datos=bytes(error.object);prefijo=datos[:error.start].decode('utf-8' if enc.startswith('utf-8') else enc)
            resto=datos[error.start:]
            try:resto.decode('cp1252');nueva='cp1252'
            except UnicodeDecodeError:nueva='latin-1'
            dec=codecs.getincrementaldecoder(nueva)(errors='strict');texto=prefijo+dec.decode(resto,final=final)
            if nueva!=enc:item['codificacion']=item.get('codificacion',enc)+' → '+nueva
            enc=nueva
        item['cortado']=True;item['soporte']='PARCIAL'
        item['aviso']=combinar(item.get('aviso',''),'Se encontraron bytes incompatibles con la codificación inicial; lectura parcial o mixta. Guarda una copia en UTF-8 y vuelve a indexar para comprobarla.')
        return dec,enc,texto

def bloques_texto(f,item,tope,control=None):
    """Lectura incremental; una línea enorme no provoca una reserva proporcional."""
    ext=extension(item['nombre'].split('!')[-1])
    if ext in {'.csv','.tsv','.jsonl'}:
        yield from _bloques_registros(f,item,tope,control,ext);return
    raw=f.read(8192);item['bytes_leidos']=len(raw);enc=codificacion(raw);item['codificacion']=enc
    dec=codecs.getincrementaldecoder(enc)(errors='strict');total=0;linea=1;pendiente='';fin=False;ocultar_linea=False;ocultar_privada=False
    while not fin:
        if control:control()
        dec,enc,texto=_decodificar_bloque(dec,enc,raw,not raw,item);fin=not raw;pendiente+=texto
        # Límite de unidad 16 KiB, redacción antes de cortar al índice.
        while len(pendiente)>=16384 or fin and pendiente:
            if total>=tope:item['cortado']=True;return
            n=min(16384,len(pendiente),tope-total)
            corte=pendiente.rfind('\n',0,n)
            if corte>0:n=corte+1
            elif not fin and n>256:n-=256 # conserva claves/marcadores que cruzan el borde
            # Una cabecera/cierre privado partido debe quedar entero para que
            # el estado de redacción no pierda su inicio o su fin.
            for m in _MARCADOR_PRIVADO_TRAMO.finditer(pendiente[:n+256]):
                if 0<m.start()<n<m.end():n=m.start();break
            original=pendiente[:n];pendiente=pendiente[n:];ref=item['nombre']+f' · desde línea {linea}';unidad=original
            from conversaciones_jarvis import _redactar
            if ocultar_privada:
                m=re.search(r'-----END [^-]*PRIVATE KEY-----',unidad)
                if m:unidad=unidad[m.end():];ocultar_privada=False
                else:unidad=''
            if ocultar_linea:
                pos=unidad.find('\n')
                if pos>=0:unidad=unidad[pos:];ocultar_linea=False
                else:unidad=''
            m=re.search(r'-----BEGIN [^-]*PRIVATE KEY-----',unidad)
            if m and not re.search(r'-----END [^-]*PRIVATE KEY-----',unidad[m.end():]):
                unidad=unidad[:m.start()]+'[CLAVE PRIVADA REDACTADA]';ocultar_privada=True
            antes=unidad
            if extension(item['nombre'].split('!')[-1])=='.env':
                unidad=re.sub(r'(?m)^(\s*(?:export\s+)?[A-Za-z_][\w]*\s*=).*$',r'\1[REDACTADO]',unidad)
            if unidad and not ocultar_privada and not original.endswith('\n') and (pendiente or not fin):
                sensible=_inicio_sensible_pendiente(unidad,pendiente,ext=='.env')
                if sensible is not None:
                    unidad=unidad[:sensible]+'[CONTINUACIÓN SENSIBLE OMITIDA]';ocultar_linea=True
                    item['cortado']=True;item['soporte']='PARCIAL'
                    item['aviso']=combinar(item.get('aviso',''),'Se omitió una continuación de línea con un posible campo sensible para evitar exponer un valor dividido entre bloques.')
            unidad=_redactar(unidad)
            if not original.endswith('\n') and antes.rsplit('\n',1)[-1]!=unidad.rsplit('\n',1)[-1]:ocultar_linea=True
            yield ref,unidad;total+=n;linea+=original.count('\n')
        if fin:break
        raw=f.read(8192);item['bytes_leidos']=item.get('bytes_leidos',0)+len(raw)
    item['caracteres_leidos']=total


_SENSIBLE=re.compile(r'(?i)(?:api.?key|token|secret|password|passwd|contrase[ñn]a|authorization|credential|private.?key)')


def _json_sin_secretos(valor):
    """Protege valores completos, también objetos/listas bajo claves privadas."""
    if isinstance(valor,dict):
        return {k:'[REDACTADO]' if _SENSIBLE.search(k) else _json_sin_secretos(v) for k,v in valor.items()}
    if isinstance(valor,list):return [_json_sin_secretos(v) for v in valor]
    return valor


def _bloques_registros(f,item,tope,control,ext):
    """CSV/TSV por registros acotados y JSONL por objetos acotados.

    Las columnas sensibles se descubren en la cabecera antes de emitir datos.
    CSV entrecomillado puede ocupar varias líneas; ninguna parte del registro
    se emite hasta validarlo y redactarlo. Un registro mayor de 64 KiB se
    rechaza con motivo, sin incorporarlo parcialmente al índice.
    """
    from conversaciones_jarvis import _redactar
    raw=f.read(8192);item['bytes_leidos']=len(raw);enc=codificacion(raw);item['codificacion']=enc
    dec=codecs.getincrementaldecoder(enc)(errors='strict')
    estado={'linea':0,'registro':0,'caracteres':0};max_registro=65536
    def lineas():
        nonlocal dec,enc
        pendiente='';bloque=raw
        while True:
            if control:control()
            dec,enc,texto=_decodificar_bloque(dec,enc,bloque,not bloque,item);pendiente+=texto
            while '\n' in pendiente or not bloque and pendiente:
                pos=pendiente.find('\n');n=pos+1 if pos>=0 else len(pendiente)
                if n>max_registro or estado['registro']+n>max_registro:
                    raise ValueError('Un registro tabular/JSONL supera 64 KiB; divide ese registro antes de indexarlo.')
                linea=pendiente[:n];pendiente=pendiente[n:]
                estado['linea']+=1;estado['registro']+=n;estado['caracteres']+=n
                yield linea
            if len(pendiente)>max_registro:
                raise ValueError('Un registro tabular/JSONL supera 64 KiB; divide ese registro antes de indexarlo.')
            if not bloque:break
            bloque=f.read(8192);item['bytes_leidos']=item.get('bytes_leidos',0)+len(bloque)
    origen=lineas();lector=origen if ext=='.jsonl' else csv.reader(origen,delimiter='\t' if ext=='.tsv' else ',',strict=True)
    privadas=set();primera=True;partes=[];tam=0;inicio=1;total=0;privada=False
    while True:
        desde=estado['linea']+1
        try:registro=next(lector)
        except StopIteration:break
        except (csv.Error,UnicodeError,RecursionError) as e:
            raise ValueError('Registro tabular/JSONL dañado; no incorporé su contenido sin redactar.') from e
        consumido=estado['registro'];estado['registro']=0
        if total+consumido>tope:item['cortado']=True;break
        if ext=='.jsonl':
            try:limpio=json.dumps(_json_sin_secretos(json.loads(registro)),ensure_ascii=False,separators=(',',':'))+'\n'
            except (ValueError,RecursionError) as e:
                # Algunos adjuntos tienen extensión JSONL pero son texto simple.
                # Se conserva ese texto con aviso; un objeto dañado o una clave
                # sensible nunca se incorpora mediante un fallback sin estructura.
                if registro.lstrip().startswith(('{','[')) or _SENSIBLE.search(registro):
                    raise ValueError('Registro JSONL dañado o demasiado anidado; no incorporé su contenido sin redactar.') from e
                limpio=registro;item['soporte']='PARCIAL';item['aviso']=combinar(item.get('aviso',''),'JSONL no estructurado: se leyó como texto, sin validar objetos ni registros.')
        else:
            if primera:privadas={i for i,v in enumerate(registro) if _SENSIBLE.search(v)}
            valores=[];etiqueta_anterior=False
            for i,v in enumerate(registro):
                sensible=bool(_SENSIBLE.search(v) and re.fullmatch(r'[\w .-]{1,120}',v.strip()))
                ocultar=(not primera and i in privadas) or etiqueta_anterior and not sensible
                valores.append('[REDACTADO]' if ocultar else v);etiqueta_anterior=sensible
            buf=io.StringIO();csv.writer(buf,delimiter='\t' if ext=='.tsv' else ',',lineterminator='\n').writerow(valores);limpio=buf.getvalue()
        if privada:
            m=re.search(r'-----END [^-]*PRIVATE KEY-----',limpio)
            if m:limpio=limpio[m.end():];privada=False
            else:limpio=''
        m=re.search(r'-----BEGIN [^-]*PRIVATE KEY-----',limpio)
        if m and not re.search(r'-----END [^-]*PRIVATE KEY-----',limpio[m.end():]):
            limpio=limpio[:m.start()]+'[CLAVE PRIVADA REDACTADA]\n';privada=True
        limpio=_redactar(limpio);primera=False;total+=consumido
        if partes and tam+len(limpio)>16384:
            yield item['nombre']+f' · desde línea {inicio}',''.join(partes);partes=[];tam=0
        if not partes:inicio=desde
        partes.append(limpio);tam+=len(limpio)
    if partes:yield item['nombre']+f' · desde línea {inicio}',''.join(partes)
    item['caracteres_leidos']=total

class _HTML(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.ignorar=0;self.partes=[]
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style'}:self.ignorar+=1
    def handle_endtag(self,tag):
        if tag in {'script','style'} and self.ignorar:self.ignorar-=1
    def handle_data(self,data):
        if not self.ignorar:self.partes.append(data)
    def vaciar(self):t=' '.join(self.partes);self.partes=[];return t

def xml_unidades(f,tags,tope,control=None):
    from tandas_documentales import recursos
    # SAX evita árboles enteros. Una unidad estructural demasiado grande se
    # rechaza con motivo, en lugar de reservar memoria proporcional al archivo.
    limite=min(tope,recursos()['mb_buffer']*1024**2);estado={'prof':0,'activa':None,'partes':[],'tam':0,'numero':0,'ignorar':0};cola=[];total=0
    parser=expat.ParserCreate(namespace_separator='}');parser.ExternalEntityRefHandler=lambda *args:0
    def inicio(n,a):
        n=n.rsplit('}',1)[-1];estado['prof']+=1
        if n in {'script','style'}:estado['ignorar']+=1
        if n in tags and estado['activa'] is None:estado.update(activa=estado['prof'],partes=[],tam=0);estado['numero']+=1
    def dato(t):
        if estado['activa'] is not None and not estado['ignorar']:
            estado['tam']+=len(t)
            if estado['tam']>limite:raise ValueError('Una unidad XML supera el buffer autorizado; divide ese párrafo/sección.')
            estado['partes'].append(t)
    def fin(n):
        n=n.rsplit('}',1)[-1]
        if estado['activa']==estado['prof']:
            cola.append((estado['numero'],''.join(estado['partes']).strip()));estado.update(activa=None,partes=[],tam=0)
        if n in {'script','style'} and estado['ignorar']:estado['ignorar']-=1
        estado['prof']-=1
    parser.StartElementHandler=inicio;parser.EndElementHandler=fin;parser.CharacterDataHandler=dato
    while True:
        if control:control()
        raw=f.read(65536)
        try:parser.Parse(raw,not raw)
        except expat.ExpatError as e:raise ValueError('XML del documento dañado o no seguro.') from e
        for n,t in cola:
            if t:
                restante=tope-total;yield n,t[:restante];total+=len(t)
                if total>=tope:return
        cola=[]
        if not raw:break

def _zip_xml(p,item,tope,control=None):
    from tandas_documentales import zip_seguro,limites
    with ZipFileAcotado(p) as z:
        zip_seguro(z,dict(limites(),archivos=1000))
        ext=item['tipo_real'];nombres=z.namelist()
        if ext=='.docx':unidades=[('word/document.xml','p','párrafo')]
        elif ext=='.pptx':unidades=[(n,'p','diapositiva '+str(i)) for i,n in enumerate(sorted((n for n in nombres if re.fullmatch('ppt/slides/slide[0-9]+.xml',n)),key=lambda n:int(re.search('[0-9]+',n).group())),1)]
        elif ext=='.epub':unidades=[(n,'html','capítulo '+str(i)) for i,n in enumerate(sorted(n for n in nombres if n.endswith(('.xhtml','.html','.htm'))),1)]
        else:unidades=[('content.xml','p','sección')]
        total=0
        for ruta,tag,tipo in unidades:
            if control:control()
            with z.open(ruta) as f:
                for n,t in xml_unidades(f,{tag},tope-total,control):
                    total+=len(t);yield item['nombre']+' · '+tipo+(' '+str(n) if tipo in {'párrafo','sección'} else ''),t
                    if total>=tope:item['cortado']=True;return

def _sqlite(p,item,tope,control=None):
    from lectura_sqlite import unidades
    yield from unidades(p,item,tope,control)

def _cancelado(control):
    try:control();return False
    except (TimeoutError,InterruptedError):return True

def combinar(*textos):return ' '.join(t for t in textos if t)

def metadatos(p,item,control=None):
    ext=item.get('tipo_real',item['tipo']);estado,razon=REGISTRO.get(ext,('NO SOPORTADO','Formato registrado sin lector seguro. No lo ejecuté.'))
    item['soporte']=estado;item['aviso']=combinar(item.get('aviso',''),razon)
    if ext in {'.png','.jpg','.jpeg','.webp','.bmp','.gif','.tiff','.tif'}:item['aviso']=combinar(item['aviso'],'Usa un modelo visual instalado.')
    if ext in {'.mp3','.wav','.ogg','.m4a','.flac','.mp4','.mkv','.webm','.avi','.mov'} and shutil.which('ffprobe'):
        r=subprocess.run([shutil.which('ffprobe'),'-v','error','-show_entries','format=duration:stream=codec_name,codec_type','-of','json',str(p)],capture_output=True,timeout=8)
        if r.returncode==0 and len(r.stdout)<200000:
            item['media']=json.loads(r.stdout)
        else:item['aviso']=combinar(item['aviso'],'ffprobe no pudo leer duración/códec; el archivo puede estar dañado o no soportado.')

def leer(p,item,l,control=None):
    tope=l['caracteres_archivo'];ext,aviso=detectar(p,item['tipo']);item['tipo_real']=ext;item['aviso']=combinar(item.get('aviso',''),aviso)
    item['soporte']=REGISTRO.get(ext,('NO SOPORTADO',''))[0]
    if item['soporte']=='PARCIAL':item['aviso']=combinar(item['aviso'],REGISTRO[ext][1])
    if ext in TEXTO|{'.env','.eml','.mbox','.vcf','.ics','.html','.htm','.rtf','.ipynb'}:
        with p.open('rb') as f:
            html=_HTML() if ext in {'.html','.htm'} else None
            for ref,t in bloques_texto(f,item,tope,control):
                if html:html.feed(t);t=html.vaciar()
                elif ext=='.rtf':t=re.sub(r'\\[a-z]+-?\d* ?|[{}]',' ',t)
                yield ref,t
        if ext=='.ipynb':item['aviso']=combinar(item['aviso'],'Notebook leído como JSON; salidas y código son datos, sin ejecutar.')
    elif ext=='.gz':
        item['cortado']=False
        with gzip.open(p,'rb') as f:
            for ref,t in bloques_texto(f,item,tope,control):yield ref+' · contenido gzip',t
        item['aviso']=combinar(item['aviso'],'Contenido expandido limitado por caracteres; no se escribió al disco.')
    elif ext=='.pdf':
        from documentos_jarvis import _pdf
        totalchars=0
        for pagina in range(1,501):
            if control:control()
            texto,paginas,cortado=_pdf(p,pagina);item['paginas']=paginas;item['paginas_leidas']=pagina
            if not texto.strip():item['aviso']=combinar(item['aviso'],'Páginas sin texto: posible escaneo. OCR '+('disponible (tesseract), no ejecutado.' if shutil.which('tesseract') else 'no instalado.'))
            yield item['nombre']+f' · página {pagina}',texto[:max(0,tope-totalchars)];totalchars+=len(texto)
            if cortado or totalchars>=tope or pagina>=500:item['cortado']=bool(cortado or totalchars>tope or pagina<paginas);return
            if pagina>=paginas:return
    elif ext in {'.xlsx','.xlsm'}:
        import libros_jarvis as X
        for ref,t in X.unidades(p,tope,item,control):yield item['nombre']+' · '+ref,t
        if ext=='.xlsm':item['aviso']=combinar(item['aviso'],'Macros presentes/posibles: no se leyeron ni ejecutaron.')
    elif ext in {'.docx','.pptx','.odt','.ods','.odp','.epub'}:yield from _zip_xml(p,item,tope,control)
    elif ext in {'.db','.sqlite','.sqlite3'}:yield from _sqlite(p,item,tope,control)
    elif ext in {'.doc','.xls','.ppt'}:
        from tandas_documentales import recursos
        if recursos()['mb_proceso']<512:
            item['soporte']='SOLO METADATOS';item['aviso']=combinar(item['aviso'],'Office antiguo requiere el perfil medido de 512 MiB de memoria virtual. Puedes elegir /adjuntos recursos mb_proceso=512 con autorización, o guardar como DOCX/XLSX/PPTX. No amplié el límite.')
            return
        from office_seguro import abrir_convertido
        formato,intermedio={'.doc':('docx:Office Open XML Text','.docx'),'.xls':('xlsx:Calc MS Excel 2007 XML','.xlsx'),'.ppt':('odp:impress8','.odp')}[ext]
        hubo_texto=False
        try:
            if control:control()
            with abrir_convertido(p,formato) as convertido:
                if control:control()
                if ext=='.xls':
                    import libros_jarvis as X
                    unidades=((item['nombre']+' · '+r,t) for r,t in X.unidades(convertido,tope,item,control))
                else:
                    meta=dict(item,tipo_real=intermedio)
                    unidades=_zip_xml(convertido,meta,tope,control)
                for ref,texto in unidades:hubo_texto=True;yield ref,texto
                if ext!='.xls' and meta.get('cortado'):item['cortado']=True
            item['soporte']='PARCIAL';item['aviso']=combinar(item['aviso'],'Texto convertido en un namespace privado sin red y con macros/contenido activo deshabilitados; no incluye todos los objetos o formato visual.')
        except (InterruptedError,TimeoutError):raise
        except (OSError,ValueError) as e:
            item['soporte']='PARCIAL' if hubo_texto else 'SOLO METADATOS'
            if hubo_texto:item['cortado']=True
            item['aviso']=combinar(item['aviso'],str(e))
    else:metadatos(p,item,control)

def analizar(p,recursos=None,desde=1,hasta=10,buscar=''):
    """Inspección de solo lectura separada del índice de 20 MB.

    Hasta 500 MiB y 60 segundos, línea física de 64 KiB, muestras de 20 KiB.
    Estos topes no elevan los límites de indexación. CSV multilínea se declara
    parcial; JSON grande se cuenta como texto, nunca se carga entero con loads.
    """
    from conversaciones_jarvis import _redactar
    from tandas_documentales import _hash,DEFAULT,zip_seguro,tar_seguro
    r=recursos or {};inicio=time.monotonic();plazo=min(60,r.get('segundos_archivo',60));max_bytes=500*1024**2
    if type(desde) is not int or type(hasta) is not int or not 1<=desde<=hasta or hasta-desde>1999:raise ValueError('Elige hasta 2000 líneas, empezando en 1.')
    if not isinstance(buscar,str) or len(buscar)>200:raise ValueError('Búsqueda literal de hasta 200 caracteres.')
    antes=p.stat();ext,aviso=detectar(p,extension(p.name))
    resultado={'archivo':p.name,'tipo_real':ext,'bytes':antes.st_size,'aviso':aviso,'indexado':False,'completo':False}
    def control():
        if time.monotonic()-inicio>plazo:raise TimeoutError('Plazo de análisis alcanzado; el resultado es parcial.')
    try:
        if antes.st_size>max_bytes:raise ValueError('El análisis por streaming admite hasta 500 MiB; divide el archivo. No elevé el índice de 20 MB.')
        if ext in {'.xlsx','.xlsm'}:
            import libros_jarvis as X
            resultado.update(X.estadisticas(p,control));resultado['soporte']='PARCIAL';resultado['aviso']=combinar(aviso,'Se analizan celdas guardadas; no imágenes ni macros.')
        elif ext in {'.zip','.tar','.tgz'}:
            if ext=='.zip':
                with ZipFileAcotado(p,DEFAULT['archivos']) as z:miembros=[(x.filename,x.file_size) for x in zip_seguro(z,DEFAULT) if not x.is_dir()]
            else:
                with tarfile.open(p,'r:*') as z:miembros=[(x.name,x.size) for x in tar_seguro(z,DEFAULT,antes.st_size if ext=='.tgz' else 0) if x.isfile()]
            resultado.update(miembros=[{'nombre':n,'bytes':b} for n,b in miembros],bytes_expandidos=sum(b for _,b in miembros),completo=True,soporte='SOLO METADATOS')
        elif ext in TEXTO|{'.env','.eml','.mbox','.vcf','.ics','.html','.htm','.rtf','.ipynb','.gz'}:
            abrir=gzip.open if ext=='.gz' else open
            with abrir(p,'rb') as binario:
                raw=binario.read(8192);enc=codificacion(raw)
            import io
            lineas=0;caracteres=0;largas=0;muestras=[];coincidencias=0;privada=False;num_validas=0;invalidas=0;sumas={};leidos=0;columnas_privadas=set();tabular_invalido=False
            with abrir(p,'rb') as binario,io.TextIOWrapper(binario,encoding=enc,errors='replace',newline='') as f:
                while True:
                    control();linea=f.readline(65537)
                    if not linea:break
                    caracteres+=len(linea);leidos+=len(linea.encode('utf-8',errors='replace'))
                    larga=len(linea)>65536 and not linea.endswith(('\n','\r'));s=linea
                    if larga:
                        largas+=1
                        while linea and not linea.endswith(('\n','\r')):
                            control();linea=f.readline(65537);caracteres+=len(linea);leidos+=len(linea.encode('utf-8',errors='replace'))
                    if leidos>max_bytes:raise ValueError('Contenido expandido superior a 500 MiB; análisis parcial.')
                    lineas+=1
                    if larga and ext in {'.csv','.tsv'}:tabular_invalido=True
                    if '-----BEGIN ' in s and 'PRIVATE KEY-----' in s:privada=True
                    es_privada=privada
                    if '-----END ' in s and 'PRIVATE KEY-----' in s:privada=False
                    seguro='[LÍNEA EXTENSA OMITIDA]' if larga else '[CLAVE PRIVADA REDACTADA]' if es_privada else _redactar(s)
                    if ext=='.env':seguro=re.sub(r'(?m)^(\s*(?:export\s+)?[A-Za-z_][\w]*\s*=).*$',r'\1[REDACTADO]',seguro)
                    if not larga and ext in {'.csv','.tsv','.jsonl'}:
                        try:
                            valores=json.loads(s) if ext=='.jsonl' else next(csv.reader([s],delimiter='\t' if ext=='.tsv' else ',',strict=True))
                            if ext=='.jsonl':seguro=_redactar(json.dumps(_json_sin_secretos(valores),ensure_ascii=False))
                            if isinstance(valores,list) and ext!='.jsonl':
                                if lineas==1:columnas_privadas={i for i,v in enumerate(valores,1) if re.search(r'(?i)(?:api.?key|token|secret|password|contrase[ñn]a|authorization|credential)',v)}
                                if columnas_privadas:
                                    valores=[('[REDACTADO]' if i in columnas_privadas and lineas>1 else v) for i,v in enumerate(valores,1)]
                                    buf=io.StringIO();csv.writer(buf,delimiter='\t' if ext=='.tsv' else ',').writerow(valores);seguro=_redactar(buf.getvalue())
                            if tabular_invalido and ext in {'.csv','.tsv'}:valores=[]
                            pares=valores.items() if isinstance(valores,dict) else enumerate(valores,1) if isinstance(valores,list) else []
                            num_validas+=1
                            for k,v in pares:
                                if re.search(r'(?i)(?:api.?key|token|secret|password|contrase[ñn]a|authorization|credential)',str(k)):continue
                                if isinstance(v,bool) or not isinstance(v,(str,int,float)):continue
                                try:
                                    numero=Decimal(str(v))
                                    if numero.is_finite():sumas[str(k)]=sumas.get(str(k),Decimal(0))+numero
                                except InvalidOperation:pass
                        except (ValueError,csv.Error,StopIteration,RecursionError):
                            invalidas+=1
                            if ext in {'.csv','.tsv'}:tabular_invalido=True
                            elif s.lstrip().startswith(('{','[')) or _SENSIBLE.search(s):seguro='[REGISTRO JSONL INVÁLIDO OMITIDO]'
                    if tabular_invalido:seguro='[MUESTRA CSV/TSV OMITIDA TRAS UN REGISTRO INVÁLIDO O MULTILÍNEA]'
                    coincide=bool(buscar and buscar.casefold() in seguro.casefold())
                    if coincide:coincidencias+=1
                    if (coincide if buscar else desde<=lineas<=hasta) and sum(len(x['texto']) for x in muestras)<20000:
                        muestras.append({'linea':lineas,'texto':seguro[:1000].rstrip()})
            resultado.update(completo=True,lineas=lineas,caracteres=caracteres,lineas_extensas_omitidas=largas,codificacion=enc,muestras=muestras,coincidencias=coincidencias,soporte='PARCIAL' if largas or invalidas or tabular_invalido else 'COMPLETO')
            if ext in {'.csv','.tsv','.jsonl'}:resultado.update(registros_fisicos_validos=num_validas,registros_fisicos_invalidos=invalidas,sumas_numericas_fisicas={k:str(v) for k,v in sumas.items()},aviso=combinar(aviso,'CSV/TSV se agrega por línea física; si contiene registros multilínea las estadísticas de registros son parciales. No se ejecutaron fórmulas.'))
            elif ext=='.json':resultado['aviso']=combinar(aviso,'Conteo de texto y muestras; no validé ni cargué el árbol JSON completo.')
        else:
            item={'tipo':extension(p.name),'tipo_real':ext,'aviso':aviso};metadatos(p,item,control);resultado.update(item)
        control()
    except (TimeoutError,ValueError,OSError,zipfile.BadZipFile,tarfile.TarError,subprocess.TimeoutExpired) as e:resultado['aviso']=combinar(resultado.get('aviso',''),str(e));resultado['completo']=False
    despues=p.stat()
    if (antes.st_size,antes.st_mtime_ns,antes.st_ino)!=(despues.st_size,despues.st_mtime_ns,despues.st_ino):resultado['completo']=False;resultado['aviso']=combinar(resultado.get('aviso',''),'El archivo cambió durante el análisis.')
    # Hash limitado por tamaño; no se imprime contenido ni se envía a servicios.
    if antes.st_size<=max_bytes:resultado['sha256']=_hash(p)
    resultado['segundos']=round(time.monotonic()-inicio,4)
    return resultado
