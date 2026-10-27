"""Barrera de auditoría para pruebas: ni datos reales ni MCP de producción.

Es una guarda contra errores de arnés, no un aislamiento del sistema operativo.
Se instala antes de cualquier escritura de los módulos de Jarvis en pruebas.
"""
import os
from pathlib import Path
import sys
import threading
import ipaddress

_INSTALADA=False
_LOCAL=threading.local()
REALES=(Path(__file__).resolve().parents[1]/'datos',Path.home()/'Jarvis/datos',
        Path.home()/'SegundoCerebro',Path.home()/'.config/jarvis',Path.home()/'.local/share/opencode')

def _ruta(valor,dir_fd=None):
    if isinstance(valor,int):
        try:return Path(os.readlink('/proc/self/fd/'+str(valor))).resolve()
        except OSError:return None
    if not isinstance(valor,(str,bytes,os.PathLike)):return None
    p=Path(os.fsdecode(valor))
    if not p.is_absolute() and isinstance(dir_fd,int) and dir_fd>=0:
        try:p=Path(os.readlink('/proc/self/fd/'+str(dir_fd)))/p
        except OSError:return None
    return p.resolve()

def _protegida(p):
    return p is not None and any(p==r or r in p.parents for r in REALES)

def comprobar_evento(evento,args):
    rutas=[]
    if evento=='open':
        modo=args[1] or '';flags=args[2] or 0
        if (isinstance(modo,str) and any(x in modo for x in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            rutas=[_ruta(args[0])]
    elif evento in {'os.rename','os.link'}:
        rutas=[_ruta(args[0],args[2] if len(args)>2 else None),_ruta(args[1],args[3] if len(args)>3 else None)]
    elif evento=='os.symlink':rutas=[_ruta(args[1],args[2] if len(args)>2 else None)]
    elif evento in {'os.remove','os.rmdir','os.mkdir','os.chmod','os.chown','os.truncate','os.utime'}:
        indice=2 if evento in {'os.mkdir','os.chmod'} else 1 if evento in {'os.remove','os.rmdir'} else None
        rutas=[_ruta(args[0],args[indice] if indice is not None and len(args)>indice else None)]
    elif evento=='socket.connect':
        direccion=args[1]
        if isinstance(direccion,tuple) and len(direccion)>=2 and direccion[1] in {8765,8767}:
            try:
                ip=ipaddress.ip_address(direccion[0]);local=ip.is_loopback or bool(getattr(ip,'ipv4_mapped',None) and ip.ipv4_mapped.is_loopback) or ip.is_unspecified
            except ValueError:local=direccion[0]=='localhost'
            if local:raise RuntimeError('Aislamiento: una prueba intentó conectarse al Segundo Cerebro real.')
    elif evento=='sqlite3.connect':rutas=[_ruta(args[0])]
    if any(_protegida(p) for p in rutas):
        raise RuntimeError('Aislamiento: una prueba intentó modificar datos reales; operación bloqueada antes de escribir.')

def _auditar(evento,args):
    if getattr(_LOCAL,'ocupado',False):return
    _LOCAL.ocupado=True
    try:comprobar_evento(evento,args)
    finally:_LOCAL.ocupado=False

def instalar():
    global _INSTALADA
    if not _INSTALADA:
        sys.addaudithook(_auditar);_INSTALADA=True

def verificar_previo(esperado,nativo=False,evidencias=None):
    esperado=Path(esperado).resolve()
    if esperado in {Path(__file__).resolve().parents[1],Path.home()/'Jarvis'} or _protegida(esperado/'datos'):
        raise RuntimeError('Aislamiento: la raíz de prueba coincide con datos reales.')
    for nombre in ('entorno_jarvis','configuracion_jarvis','jarvis_agente','conversaciones_jarvis','hilo_conversacion'):
        modulo=sys.modules.get(nombre)
        if modulo is None:continue
        for atributo in ('PROYECTO','TRABAJO','DATOS','REGISTROS'):
            ruta=getattr(modulo,atributo,None)
            if isinstance(ruta,Path) and not (ruta==esperado or esperado in ruta.parents):
                raise RuntimeError('Aislamiento: un módulo conservó rutas de otra instalación; no se inicia la medición.')
    c=sys.modules.get('configuracion_jarvis')
    if c is not None and c.ARCHIVO!=esperado/'datos/configuracion.json':raise RuntimeError('Aislamiento: configuración fuera del temporal.')
    instalar()
    resultado={'raiz_temporal_verificada':True,'guarda_instalada':True,'mcp_produccion_bloqueado':True}
    if nativo:resultado['landlock']=instalar_landlock([esperado]+([evidencias] if evidencias else []))
    return resultado

def instalar_landlock(escrituras):
    """Restringe escritura del proceso y descendientes, incluidos programas nativos.

    Solo habilita los temporales expresos, /tmp y las evidencias indicadas.
    No usa sudo ni altera políticas de otros procesos. No ofrece aislamiento
    total de lectura, red, metadatos ni descriptores heredados.
    """
    import ctypes,platform
    if platform.machine() not in {'x86_64','aarch64'}:raise RuntimeError('Aislamiento nativo: arquitectura sin comprobar.')
    lib=ctypes.CDLL(None,use_errno=True)
    abi=lib.syscall(444,0,0,1)
    if abi<3:raise RuntimeError('Landlock con protección de truncado no está disponible; no ejecutar sin aislamiento.')
    class Reglas(ctypes.Structure):_fields_=[('fs',ctypes.c_uint64)]
    class Ruta(ctypes.Structure):
        _pack_=1
        _fields_=[('acceso',ctypes.c_uint64),('fd',ctypes.c_int32)]
    mascara=(1<<1)|sum(1<<b for b in range(4,15))
    reglas=Reglas(mascara);fd=lib.syscall(444,ctypes.byref(reglas),ctypes.sizeof(reglas),0)
    if fd<0:raise OSError(ctypes.get_errno(),'No se pudo crear la restricción Landlock')
    try:
        rutas={Path('/tmp').resolve(),*(Path(x).resolve() for x in escrituras)}
        for ruta in rutas:
            if _protegida(ruta) or ruta==Path.home() or ruta==Path('/'):raise RuntimeError('Lista de escritura de prueba demasiado amplia.')
            pfd=os.open(ruta,os.O_PATH|os.O_CLOEXEC)
            try:
                regla=Ruta(mascara,pfd)
                if lib.syscall(445,fd,1,ctypes.byref(regla),0):raise OSError(ctypes.get_errno(),'No se pudo autorizar el temporal')
            finally:os.close(pfd)
        pfd=os.open('/dev/null',os.O_PATH|os.O_CLOEXEC)
        try:
            regla=Ruta((1<<1)|(1<<14),pfd)
            if lib.syscall(445,fd,1,ctypes.byref(regla),0):raise OSError(ctypes.get_errno(),'No se pudo autorizar /dev/null')
        finally:os.close(pfd)
        if lib.prctl(38,1,0,0,0):raise OSError(ctypes.get_errno(),'No se pudo restringir privilegios')
        if lib.syscall(446,fd,8 if abi>=8 else 0):raise OSError(ctypes.get_errno(),'No se pudo aplicar Landlock')
    finally:os.close(fd)
    return {'abi':abi,'escritura_restringida':True,'sin_cambios_en_otros_procesos':True}
