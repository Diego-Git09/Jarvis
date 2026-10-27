"""Conversión Office local y aislada; nunca recurre a un conversor sin barreras.

Las rutas deben pasar también por los permisos del controlador. Este lector
vuelve a comprobar la autorización, usa una copia privada y monta únicamente
esa copia de entrada como lectura. No interpreta instrucciones del documento.
"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import shutil
import signal
import stat
import struct
import subprocess
import tempfile
import time
import zipfile
from xml.etree import ElementTree as E
from xml.parsers import expat

import herramientas_lectura as L

MAX_ENTRADA=20*1024**2
MAX_SALIDA=16*1024**2
MAX_CARACTERES=2_000_000
MAX_AS=1024**3
MAX_CPU=30
MAX_STACK=2*1024**2
TIMEOUT=35
OOR='http://openoffice.org/2001/registry'
ESQUEMA=Path('/usr/lib/libreoffice/share/registry/main.xcd')
BINARIO=Path('/usr/lib/libreoffice/program/soffice.bin')
FORMATOS={
    'txt:Text':('txt:Text (encoded):UTF8','.txt'),
    'csv:Text - txt - csv (StarCalc)':('csv:Text - txt - csv (StarCalc):44,34,76,1','.csv'),
    'docx:Office Open XML Text':('docx:Office Open XML Text','.docx'),
    'xlsx:Calc MS Excel 2007 XML':('xlsx:Calc MS Excel 2007 XML','.xlsx'),
    'odp:impress8':('odp:impress8','.odp'),
}
AVISO_PARCIAL='\n[Texto convertido parcial: se alcanzó el límite de caracteres.]'


class OfficeNoDisponible(ValueError):
    """No se puede garantizar el aislamiento; conserva solo los metadatos."""


def _firma(p):
    s=p.stat()
    return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns


def _herramientas():
    bwrap=shutil.which('bwrap');prlimit=shutil.which('prlimit')
    if not BINARIO.is_file() or not os.access(BINARIO,os.X_OK):
        raise OfficeNoDisponible('LibreOffice no está instalado en la ruta verificada. Guarda el documento como DOCX/XLSX/PPTX; no instalé nada.')
    if not bwrap or not prlimit:
        raise OfficeNoDisponible('Falta bwrap o prlimit para aislar Office. Solo se conservan metadatos; no usé una conversión sin aislamiento.')
    # No se supone que todas las versiones tengan el interruptor global.
    requeridas={'DisableMacrosExecution','MacroSecurityLevel','DisableActiveContent',
                'DisablePythonRuntime','DisableOLEAutomation','BlockUntrustedRefererLinks','SecureURL'}
    halladas=set();pila=[]
    try:
        with ESQUEMA.open('rb') as fuente:
            for evento,nodo in E.iterparse(fuente,events=['start','end']):
                nombre=nodo.attrib.get('{'+OOR+'}name','')
                if evento=='start':pila.append(nombre)
                else:
                    camino=[n for n in pila if n]
                    if nodo.tag.rsplit('}',1)[-1]=='prop' and camino[-4:-1]==['Common','Security','Scripting']:
                        halladas.add(nombre)
                    if nodo.tag.rsplit('}',1)[-1] in {'prop','group','component-schema','component-data','node'}:nodo.clear()
                    pila.pop()
                    if requeridas<=halladas:break
    except (OSError,E.ParseError) as e:
        raise OfficeNoDisponible('No pude verificar la configuración de seguridad de LibreOffice; no abrí el documento.') from e
    if not requeridas<=halladas:
        raise OfficeNoDisponible('Esta instalación no acredita el bloqueo global de macros requerido. Solo metadatos; no abrí el documento.')
    return str(Path(bwrap).resolve()),str(Path(prlimit).resolve())


def _perfil(ruta):
    """Escrito ANTES de abrir: no hereda el perfil ni fuentes de confianza."""
    user=ruta/'user'
    if user.is_symlink():raise ValueError('El perfil Office temporal no puede ser un enlace.')
    user.mkdir(mode=0o700,exist_ok=True);os.chmod(user,0o700)
    E.register_namespace('oor',OOR)
    raiz=E.Element('{'+OOR+'}items')
    def item(camino,propiedades):
        n=E.SubElement(raiz,'item',{'{'+OOR+'}path':camino})
        for nombre,valor in propiedades.items():
            p=E.SubElement(n,'prop',{'{'+OOR+'}name':nombre,'{'+OOR+'}op':'fuse','{'+OOR+'}finalized':'true'})
            E.SubElement(p,'value').text=valor
        return n
    scripting=item('/org.openoffice.Office.Common/Security/Scripting',{
        'DisableMacrosExecution':'true','MacroSecurityLevel':'3',
        'DisableActiveContent':'true','DisablePythonRuntime':'true',
        'DisableOLEAutomation':'true','BlockUntrustedRefererLinks':'true',
        'SecureURL':'','AllowedDocumentEventURLs':''})
    E.SubElement(scripting,'node',{'{'+OOR+'}name':'TrustedAuthors','{'+OOR+'}op':'replace'})
    # Writer y Calc tienen enumeraciones distintas para «Nunca».
    item('/org.openoffice.Office.Writer/Content/Update',{'Link':'2','Field':'false','Chart':'false'})
    item('/org.openoffice.Office.Calc/Content/Update',{'Link':'1'})
    destino=user/'registrymodifications.xcu'
    fd=os.open(destino,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    os.fchmod(fd,0o600)
    with os.fdopen(fd,'wb') as f:E.ElementTree(raiz).write(f,encoding='UTF-8',xml_declaration=True)
    return destino


def _copiar(ruta,destino):
    fd=os.open(ruta,os.O_RDONLY|os.O_NOFOLLOW)
    h=hashlib.sha256();total=0
    with os.fdopen(fd,'rb') as entrada:
        if not stat.S_ISREG(os.fstat(entrada.fileno()).st_mode):raise ValueError('Office requiere un archivo normal.')
        salida_fd=os.open(destino,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(salida_fd,'wb') as salida:
            while True:
                bloque=entrada.read(65536)
                if not bloque:break
                total+=len(bloque)
                if total>MAX_ENTRADA:raise ValueError('Office supera el límite de 20 MiB; no lo abrí.')
                h.update(bloque);salida.write(bloque)
    return h.hexdigest()


def _sectores_ole(ole,entrada):
    """Recorre el Workbook por sectores; no llama a openstream (carga todo)."""
    from olefile import ENDOFCHAIN
    mini=entrada.size<ole.minisectorcutoff
    if mini:
        ole.loadminifat();fat=ole.minifat;tam=ole.minisectorsize
        raiz=[];sector=ole.root.isectStart;vistos=set()
        while sector!=ENDOFCHAIN:
            if sector in vistos or sector>=len(ole.fat) or len(raiz)>MAX_ENTRADA//ole.sectorsize:
                raise ValueError('La cadena OLE del libro no es válida.')
            vistos.add(sector);raiz.append(sector);sector=ole.fat[sector]
    else:fat=ole.fat;tam=ole.sectorsize
    sector=entrada.isectStart;restante=entrada.size;vistos=set()
    while restante:
        if sector in vistos or sector==ENDOFCHAIN or sector>=len(fat):raise ValueError('El libro OLE está truncado o tiene ciclos.')
        vistos.add(sector)
        if mini:
            pos=sector*tam;indice=pos//ole.sectorsize
            if indice>=len(raiz):raise ValueError('El libro OLE está truncado.')
            offset=(raiz[indice]+1)*ole.sectorsize+pos%ole.sectorsize
        else:offset=(sector+1)*ole.sectorsize
        ole.fp.seek(offset);bloque=ole.fp.read(min(tam,restante))
        if len(bloque)!=min(tam,restante):raise ValueError('El libro OLE está truncado.')
        yield bloque;restante-=len(bloque);sector=fat[sector]


def _validar_biff(bloques):
    """Admite BIFF8 de valores; no expone fórmulas a un motor de cálculo."""
    datos=bytearray();primero=True;registros=0
    prohibidos={0x0006,0x0206,0x0406,0x0021,0x0221,0x04BC,0x0036,0x0236,
                0x0018,0x0023,0x0017,0x01AE,0x002F}
    for bloque in bloques:
        datos.extend(bloque)
        while len(datos)>=4:
            ident,tam=struct.unpack_from('<HH',datos)
            if tam>8224:raise ValueError('Registro XLS fuera del subconjunto BIFF8 seguro; solo metadatos.')
            if len(datos)<tam+4:break
            cuerpo=bytes(datos[4:tam+4]);del datos[:tam+4];registros+=1
            if primero:
                if ident!=0x0809 or tam<4 or struct.unpack_from('<H',cuerpo)[0]!=0x0600:
                    raise ValueError('XLS no es BIFF8 verificable; guarda como XLSX sin fórmulas. Solo metadatos.')
                primero=False
            if ident in prohibidos:
                raise ValueError('XLS contiene fórmulas, nombres definidos, vínculos o cifrado. No lo convertí para evitar cálculo o contenido activo; guarda una copia de valores en XLSX.')
            if ident==0x0809 and tam>=4 and struct.unpack_from('<H',cuerpo,2)[0] in {0x0040,0x0006}:
                raise ValueError('XLS contiene una hoja macro; no lo convertí.')
    if primero or datos and any(datos):raise ValueError('XLS truncado o no reconocido; solo metadatos.')
    return registros


def _xls_sin_formulas(ruta):
    try:
        import olefile
    except ImportError as e:raise OfficeNoDisponible('Falta el lector OLE para excluir fórmulas en XLS; solo metadatos, sin instalar nada.') from e
    try:
        with olefile.OleFileIO(str(ruta),raise_defects=olefile.DEFECT_INCORRECT) as ole:
            if ole.exists('EncryptedPackage') or ole.exists('EncryptionInfo'):raise ValueError('XLS protegido por contraseña; solo metadatos.')
            if not ole.exists('Workbook'):raise ValueError('No encontré un libro BIFF8 verificable; solo metadatos.')
            entrada=ole.direntries[ole._find('Workbook')]
            if entrada.size>MAX_ENTRADA:raise ValueError('El libro XLS supera el límite local.')
            _validar_biff(_sectores_ole(ole,entrada))
    except (OSError,IndexError,struct.error) as e:raise ValueError('XLS corrupto o no verificable; no se abrió con el conversor.') from e


def _comando(entrada,salida,perfil,formato,bwrap,prlimit):
    dentro='/tmp/jarvis-office'
    import resource
    heredado=resource.getrlimit(resource.RLIMIT_AS)[1]
    memoria=MAX_AS if heredado==resource.RLIM_INFINITY else min(MAX_AS,heredado)
    argumentos=[prlimit,f'--as={memoria}',f'--cpu={MAX_CPU}',f'--fsize={MAX_SALIDA}',f'--stack={MAX_STACK}',
                '--core=0','--nofile=256','--',bwrap,
                '--unshare-all','--new-session','--die-with-parent','--cap-drop','ALL',
                '--tmpfs','/','--ro-bind','/usr','/usr',
                '--symlink','usr/bin','/bin','--symlink','usr/lib','/lib',
                '--symlink','usr/lib64','/lib64','--dir','/etc',
                '--dir','/tmp','--dir','/var/tmp','--proc','/proc','--dev','/dev']
    # Solo runtimes y configuración de la suite. /home, /root, /media, /mnt,
    # /opt y el resto de /etc no se montan en el namespace del conversor.
    for ruta in ('/etc/ld.so.cache','/etc/fonts','/etc/libreoffice','/etc/locale.alias','/etc/localtime'):
        if Path(ruta).exists():argumentos+=['--ro-bind',ruta,ruta]
    argumentos += [
                '--dir',dentro+'/entrada','--ro-bind',str(entrada),dentro+'/entrada/'+entrada.name,
                '--dir',dentro+'/salida','--bind',str(salida),dentro+'/salida',
                '--dir',dentro+'/perfil','--bind',str(perfil),dentro+'/perfil',
                '--chdir',dentro+'/salida','--clearenv']
    for k,v in {'HOME':dentro+'/perfil','TMPDIR':'/tmp','PATH':'/usr/bin:/bin','LANG':'C.UTF-8',
                'LC_ALL':'C.UTF-8','SAL_USE_VCLPLUGIN':'svp','OMP_NUM_THREADS':'1',
                'OPENBLAS_NUM_THREADS':'1','SAL_DISABLE_OPENCL':'1',
                'MALLOC_ARENA_MAX':'1','MAX_CONCURRENCY':'1'}.items():argumentos+=['--setenv',k,v]
    return argumentos+['--',str(BINARIO),'-env:UserInstallation=file://'+dentro+'/perfil',
                       '--headless','--nologo','--nodefault','--nofirststartwizard',
                       '--norestore','--nolockcheck','--convert-to',formato,
                       '--outdir',dentro+'/salida',dentro+'/entrada/'+entrada.name]


def _ejecutar(argumentos,registro,perfil=None):
    fin=time.monotonic()+TIMEOUT
    with registro.open('wb') as salida:
        os.chmod(registro,0o600)
        for intento in range(2):
            try:
                proceso=subprocess.Popen(argumentos,stdin=subprocess.DEVNULL,stdout=salida,
                                         stderr=subprocess.STDOUT,start_new_session=True,close_fds=True,
                                         env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8'})
            except OSError as e:raise OfficeNoDisponible('No pude iniciar el aislamiento de Office; no usé otro conversor.') from e
            try:codigo=proceso.wait(timeout=max(.01,fin-time.monotonic()))
            except subprocess.TimeoutExpired as e:
                try:os.killpg(proceso.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proceso.wait(timeout=3)
                raise ValueError('Office alcanzó el plazo de 35 segundos. Se detuvo el grupo aislado; el original no se modificó.') from e
            # soffice.bin puede terminar con 81 al inicializar un perfil nuevo.
            # Se permite una única repetición, dentro del mismo plazo global,
            # restaurando la política antes de cualquier apertura siguiente.
            if codigo==81 and intento==0 and perfil is not None and time.monotonic()<fin:
                _perfil(perfil);continue
            break
    if codigo:
        with registro.open('rb') as fuente:detalle=fuente.read(4096).lower()
        if b'bwrap:' in detalle:
            raise OfficeNoDisponible('No pudo iniciarse el aislamiento de Office (namespaces o recursos). Solo metadatos; no intenté convertir sin aislamiento.')
        raise ValueError('Office no pudo convertir el documento dentro de los límites. Puede estar protegido, dañado o no ser compatible; solo metadatos.')


@contextmanager
def abrir_convertido(ruta,formato='txt:Text'):
    """Entrega un Path temporal; el llamador lo lee por bloques antes de salir.

    La conversión XLS a CSV representa una hoja; para todas las hojas, solicitar
    ``xlsx:Calc MS Excel 2007 XML`` y usar el lector incremental de libros.
    """
    if formato not in FORMATOS:raise ValueError('Formato de conversión no permitido; solo texto, CSV o intermediarios Office registrados.')
    original=L._resolver(str(ruta))
    if original.suffix.lower() not in {'.doc','.xls','.ppt','.odt'}:raise ValueError('Esta conversión solo admite DOC, XLS, PPT y ODT de prueba/lectura.')
    if not original.is_file() or original.stat().st_size>MAX_ENTRADA:raise ValueError('Office requiere un archivo normal de hasta 20 MiB.')
    bwrap,prlimit=_herramientas();firma=_firma(original)
    with tempfile.TemporaryDirectory(prefix='jarvis-office-seguro-') as temporal:
        base=Path(temporal);os.chmod(base,0o700)
        entrada=base/('fuente'+original.suffix.lower());_copiar(original,entrada)
        if _firma(original)!=firma:raise ValueError('El documento cambió mientras se preparaba la lectura; vuelve a adjuntarlo.')
        if original.suffix.lower()=='.xls':_xls_sin_formulas(entrada)
        salida=base/'salida';perfil=base/'perfil'
        salida.mkdir(mode=0o700);perfil.mkdir(mode=0o700);_perfil(perfil)
        filtro,extension=FORMATOS[formato]
        _ejecutar(_comando(entrada,salida,perfil,filtro,bwrap,prlimit),base/'conversion.log',perfil=perfil)
        if _firma(original)!=firma:raise ValueError('El documento cambió durante la conversión; no presenté un resultado antiguo.')
        convertido=salida/('fuente'+extension)
        if convertido.is_symlink() or not convertido.is_file():
            raise ValueError('Office no produjo texto legible. El documento puede estar protegido, dañado o no ser compatible; solo metadatos.')
        s=convertido.stat()
        if s.st_nlink!=1 or not 0<s.st_size<=MAX_SALIDA:raise ValueError('La salida de Office no es un archivo normal dentro del límite de 16 MiB.')
        os.chmod(convertido,0o600)
        yield convertido


def _texto_odp(ruta,max_caracteres):
    partes=[];usados=0;ignorar=0
    parser=expat.ParserCreate(namespace_separator='}')
    parser.ExternalEntityRefHandler=lambda *_:0
    def inicio(n,a):
        nonlocal ignorar
        if n.rsplit('}',1)[-1] in {'script','scripts'}:ignorar+=1
    def dato(t):
        nonlocal usados
        if not ignorar:
            disponible=max_caracteres+1-usados
            if disponible>0:partes.append(t[:disponible]);usados+=len(t[:disponible])
    def fin(n):
        nonlocal ignorar
        nombre=n.rsplit('}',1)[-1]
        if nombre in {'script','scripts'} and ignorar:ignorar-=1
        if nombre in {'p','h'}:dato('\n')
    parser.StartElementHandler=inicio;parser.CharacterDataHandler=dato;parser.EndElementHandler=fin
    with zipfile.ZipFile(ruta) as z:
        info=z.getinfo('content.xml')
        if info.file_size>MAX_SALIDA*4:raise ValueError('El texto convertido se expande demasiado; no lo cargué.')
        with z.open(info) as f:
            while usados<=max_caracteres:
                b=f.read(65536)
                try:parser.Parse(b,not b)
                except expat.ExpatError as e:raise ValueError('El texto convertido contiene XML inválido.') from e
                if not b:break
    return ''.join(partes)


def convertir(ruta,formato='txt:Text',max_caracteres=MAX_CARACTERES):
    """Compatibilidad textual acotada; PPT usa ODP, porque no exporta Writer TXT."""
    if type(max_caracteres) is not int or not 1<=max_caracteres<=MAX_CARACTERES:raise ValueError('Límite de texto Office no válido.')
    ppt=Path(ruta).suffix.lower()=='.ppt' and formato=='txt:Text'
    with abrir_convertido(ruta,'odp:impress8' if ppt else formato) as convertido:
        if ppt:texto=_texto_odp(convertido,max_caracteres)
        else:
            if formato not in {'txt:Text','csv:Text - txt - csv (StarCalc)'}:raise ValueError('Usa abrir_convertido para un formato intermedio binario.')
            partes=[];total=0
            with convertido.open('r',encoding='utf-8-sig',errors='replace') as f:
                while total<=max_caracteres:
                    bloque=f.read(min(8192,max_caracteres+1-total))
                    if not bloque:break
                    partes.append(bloque);total+=len(bloque)
            texto=''.join(partes)
    if len(texto)>max_caracteres:
        return texto[:max(0,max_caracteres-len(AVISO_PARCIAL))]+AVISO_PARCIAL[:max_caracteres]
    return texto
