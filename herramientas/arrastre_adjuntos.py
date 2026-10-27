"""Arrastre local de archivos: rutas Tcl fieles, sin ejecución ni autorizaciones."""
from pathlib import Path, PurePosixPath
import hashlib
import importlib
import json
import platform
import re
from urllib.parse import unquote_to_bytes, urlsplit

MAX_RUTAS=200
MAX_DATOS=1_000_000
TERCEROS=Path(__file__).resolve().parent/'terceros'


def rutas_del_evento(root,datos):
    """Tupla de rutas absolutas locales. Autorizar/abrir corresponde a TANDAS.

    `splitlist` interpreta una lista de Tcl, nunca un script: los espacios,
    llaves, tildes y caracteres de shell de un nombre no se ejecutan.
    """
    if not isinstance(datos,str) or not datos or len(datos)>MAX_DATOS:
        raise ValueError('La lista de archivos está vacía o supera el límite del arrastre.')
    if '\x00' in datos:raise ValueError('La lista contiene un carácter nulo.')
    try:elementos=root.tk.splitlist(datos)
    except Exception as e:raise ValueError('La lista de archivos del escritorio no es válida.') from e
    if not 1<=len(elementos)<=MAX_RUTAS:
        raise ValueError('Arrastra entre 1 y 200 archivos por tanda.')
    rutas=[]
    for entrada in elementos:
        if not isinstance(entrada,str) or not entrada or len(entrada)>4096:
            raise ValueError('Hay una ruta vacía o demasiado larga.')
        if any(ord(c)<32 or ord(c)==127 for c in entrada):
            raise ValueError('Una ruta contiene caracteres de control.')
        ruta=entrada
        if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',entrada):
            u=urlsplit(entrada)
            if u.scheme.casefold()!='file' or u.netloc.casefold() not in {'','localhost'} or u.query or u.fragment:
                raise ValueError('Solo se aceptan archivos locales; no enlaces ni ubicaciones remotas.')
            if re.search(r'%(?![0-9A-Fa-f]{2})',u.path):raise ValueError('La ruta file:// contiene escapes inválidos.')
            try:ruta=unquote_to_bytes(u.path).decode('utf-8','strict')
            except UnicodeError as e:raise ValueError('La ruta file:// no tiene una codificación UTF-8 válida.') from e
        if any(ord(c)<32 or ord(c)==127 for c in ruta):
            raise ValueError('Una ruta contiene caracteres de control.')
        if not ruta.startswith('/') or ruta.startswith('//') or '..' in PurePosixPath(ruta).parts:
            raise ValueError('Arrastra rutas locales absolutas, sin retrocesos a otra carpeta.')
        if ruta not in rutas:rutas.append(ruta)
    return tuple(rutas)


def verificar_copia():
    """Comprueba los archivos oficiales antes de importar/cargar código nativo."""
    manifiesto=TERCEROS/'TKINTERDND2_SHA256.json'
    if manifiesto.is_symlink():raise ValueError('El manifiesto del arrastre no es válido.')
    datos=json.loads(manifiesto.read_text(encoding='utf-8'))
    if datos.get('version')!='0.6.4' or datos.get('wheel_sha256')!='4b11e0ac6febd8609faf154851d782eca4068bfa68a88ca3d3dded8294367f80':
        raise ValueError('La copia local del arrastre no corresponde a la versión verificada.')
    archivos=datos.get('archivos')
    if not isinstance(archivos,dict) or not archivos:raise ValueError('Falta el manifiesto de archivos del arrastre.')
    raiz=TERCEROS/'tkinterdnd2'
    if raiz.is_symlink():raise ValueError('La copia del arrastre no puede ser un enlace.')
    for nombre,esperado in archivos.items():
        relativo=PurePosixPath(nombre)
        if relativo.is_absolute() or '..' in relativo.parts:raise ValueError('Ruta no válida en el manifiesto de arrastre.')
        p=raiz/nombre
        if any(parte.is_symlink() for parte in [p,*p.parents] if parte==raiz or raiz in parte.parents):
            raise ValueError('Hay un enlace en la copia local del arrastre.')
        if hashlib.sha256(p.read_bytes()).hexdigest()!=esperado:
            raise ValueError('La copia local del arrastre cambió; conserva el selector Adjuntar y revisa su integridad.')
    return datos['version']


def _cargar_backend():
    if platform.system()!='Linux' or platform.machine()!='x86_64':
        raise RuntimeError('El arrastre empaquetado está disponible en Linux x86_64. Usa Adjuntar en este equipo.')
    verificar_copia()
    return importlib.import_module('terceros.tkinterdnd2')


def instalar(root,widgets,callback):
    """Registra destinos de archivos y devuelve {ok, version, error}.

    El callback recibe una tupla. Debe usar el flujo normal de adjuntos de la
    interfaz, incluidas rutas autorizadas, límites y permisos. No se realizan
    lecturas ni se autorizan carpetas en este módulo. Devuelve False para
    rechazar el arrastre; None permite callbacks que encolan trabajo de la GUI.
    """
    estado={'ok':False,'version':'','error':''}
    registrados=[]
    try:
        if not callable(callback):raise ValueError('Falta el manejador de archivos adjuntos.')
        backend=_cargar_backend()
        estado['version']=str(backend.TkinterDnD.require(root))
        destinos=[]
        for w in widgets:
            if w not in destinos:destinos.append(w)
        if not destinos:raise ValueError('No se indicó una zona para soltar archivos.')

        def error_arrastre(mensaje):
            estado['error']=mensaje
            try:root.event_generate('<<JarvisArrastreError>>',when='tail')
            except Exception:pass

        def recibir(evento):
            try:
                rutas=rutas_del_evento(root,evento.data)
            except (ValueError,OSError) as e:
                error_arrastre(str(e));return backend.REFUSE_DROP
            except Exception:
                error_arrastre('No pude interpretar la lista de archivos soltados. Usa Adjuntar.')
                return backend.REFUSE_DROP
            try:
                if callback(rutas) is False:return backend.REFUSE_DROP
                estado['error']=''
                return backend.COPY
            except Exception:
                error_arrastre('No pude adjuntar los archivos soltados. Usa el botón Adjuntar para revisarlos.')
                return backend.REFUSE_DROP

        for w in destinos:
            if not all(callable(getattr(w,n,None)) for n in ('drop_target_register','dnd_bind')):
                raise ValueError('La zona de arrastre debe ser un widget de Tk, como el chat o el cuadro de escritura.')
            w.drop_target_register(backend.DND_FILES)
            registrados.append(w)
            w.dnd_bind('<<DropEnter>>',lambda _e:backend.COPY)
            w.dnd_bind('<<DropPosition>>',lambda _e:backend.COPY)
            w.dnd_bind('<<Drop>>',recibir)
        estado['ok']=True
    except Exception as e:
        for w in registrados:
            try:w.drop_target_unregister()
            except Exception:pass
        estado['error']='Arrastre no disponible: '+str(e)[:300]+'. Puedes usar Adjuntar.'
    return estado
