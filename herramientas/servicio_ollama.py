"""Sesiones de Ollama: solo el supervisor puede detener el hijo que creó.

No ejecuta systemctl, sudo, pkill ni señales contra PIDs leídos del disco.
Las sesiones comparten un supervisor y dejan intacto un servidor preexistente.
"""
import atexit
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from urllib.parse import urlsplit

from salud_ollama import comprobar,validar_destino

MAX_JSON=16384
MOTIVOS_INICIO={
    'proceso_terminado':'El proceso local de Ollama terminó antes de completar la sesión.',
    'api_sin_respuesta':'El proceso inició pero no acreditó una API Ollama disponible en 12 segundos.',
    'control':'No se pudo iniciar el proceso local de Ollama. /diagnostico permite revisar la conexión.',
    'propiedad_sin_acreditar':'La API respondió, pero no pude acreditar que el puerto perteneciera al proceso iniciado por Jarvis.',
}

def escucha_propia(pid,url):
    """Relaciona un puerto LISTEN con sockets del hijo; no inspecciona sus datos."""
    puerto=urlsplit(url).port or 80
    try:
        inodos=set()
        for f in Path('/proc',str(pid),'fd').iterdir():
            try:destino=os.readlink(f)
            except FileNotFoundError:continue
            if destino.startswith('socket:[') and destino.endswith(']'):
                inodos.add(destino[8:-1])
        for tabla in ('tcp','tcp6'):
            for linea in Path('/proc',str(pid),'net',tabla).read_text().splitlines()[1:]:
                campos=linea.split()
                if len(campos)>9 and campos[3]=='0A' and int(campos[1].rsplit(':',1)[1],16)==puerto and campos[9] in inodos:
                    return True
        return False
    except (OSError,ValueError,IndexError):return None

def identidad(pid):
    """Tiempo de nacimiento del proceso Linux; evita aceptar un PID reutilizado."""
    try:
        raw=Path('/proc',str(pid),'stat').read_text()
        campos=raw[raw.rfind(')')+2:].split()
        if campos[0]=='Z':return None
        return campos[19]
    except (OSError,ValueError,IndexError):return None

def vivo(dato):
    return (isinstance(dato,dict) and type(dato.get('pid')) is int and dato['pid']>0
            and isinstance(dato.get('nacimiento'),str)
            and identidad(dato['pid'])==dato['nacimiento'])

def _directorio(raiz):
    if any(p.is_symlink() for p in (raiz,*raiz.parents)):
        raise ValueError('El control de Ollama no admite enlaces simbólicos.')
    raiz.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not raiz.is_dir() or raiz.stat().st_uid!=os.getuid():
        raise ValueError('El directorio de control no pertenece a esta sesión.')
    os.chmod(raiz,0o700)

def leer_json(ruta):
    try:
        fd=os.open(ruta,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except FileNotFoundError:return None
    try:
        meta=os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.getuid() or meta.st_mode&0o077 or meta.st_size>MAX_JSON:
            raise ValueError('Metadatos de control no seguros.')
        # Conservamos la propiedad del descriptor incluso si falla la creación
        # del adaptador de texto (por ejemplo, un directorio en lugar del JSON).
        with os.fdopen(fd,closefd=False) as f:d=json.load(f)
    finally:os.close(fd)
    if not isinstance(d,dict):raise ValueError('Metadatos de control no válidos.')
    return d

def guardar_json(ruta,dato):
    fd,tmp=tempfile.mkstemp(prefix='.control-',dir=ruta.parent)
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(dato,f);f.write('\n');f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600);os.replace(tmp,ruta)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

@contextmanager
def bloqueo(raiz,timeout=2):
    _directorio(raiz)
    fd=os.open(raiz/'candado',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        meta=os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.getuid():raise ValueError('Candado no seguro.')
        os.fchmod(fd,0o600)
        fin=time.monotonic()+timeout
        while True:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>=fin:raise TimeoutError('El control de Ollama está ocupado.')
                time.sleep(.02)
        yield
    finally:os.close(fd)

def clientes_vivos(raiz):
    activos=[]
    for p in raiz.glob('cliente-*.json'):
        try:dato=leer_json(p)
        except (OSError,ValueError,RecursionError):continue
        if vivo(dato):activos.append(p)
        else:p.unlink()
    return activos

def entorno_hijo(url,raiz):
    # Lista explícita: no heredar claves API, proxies ni configuración de nube.
    nombres=('PATH','LANG','LC_ALL','LD_LIBRARY_PATH','CUDA_VISIBLE_DEVICES',
             'ROCR_VISIBLE_DEVICES','GGML_VK_VISIBLE_DEVICES','TMPDIR')
    env={k:os.environ[k] for k in nombres if k in os.environ}
    u=urlsplit(url)
    host='['+u.hostname+']' if ':' in u.hostname else u.hostname
    destino='http://'+host+':'+str(u.port or 80)
    env.update(HOME=str(raiz/'hogar'),OLLAMA_HOST=destino,OLLAMA_NO_CLOUD='1',
               OLLAMA_NUM_PARALLEL='1',OLLAMA_NOPRUNE='1')
    modelos=os.environ.get('OLLAMA_MODELS')
    if not modelos:
        for ruta in (Path.home()/'.ollama/models',Path('/usr/share/ollama/.ollama/models')):
            if (ruta/'manifests').is_dir() and os.access(ruta,os.R_OK|os.X_OK):
                modelos=str(ruta);break
    if modelos:env['OLLAMA_MODELS']=modelos
    else:env['OLLAMA_MODELS']=str(raiz/'modelos')
    return env

class SesionOllama:
    def __init__(self,url,*,raiz=None,ejecutable=None,avisar=None,permitir_pruebas=False):
        self.url=validar_destino(url)
        if raiz is None:
            from entorno_jarvis import DATOS
            raiz=DATOS/'ollama_sesion'/hashlib.sha256(self.url.encode()).hexdigest()[:16]
        self.raiz=Path(raiz)
        self.ejecutable=ejecutable
        self.avisar=avisar or (lambda _:None)
        self._id=uuid.uuid4().hex
        self._cliente=self.raiz/('cliente-'+self._id+'.json')
        self._cerrada=threading.Event();self._lock=threading.RLock()
        self._comprobada=0.;self._ultima=None
        self._registrada=False
        self.generacion=0
        self._token_actual=None
        self._sin_supervisor=None
        from entorno_jarvis import en_pruebas
        self.habilitada=permitir_pruebas or not en_pruebas()
        atexit.register(self.cerrar)

    def _registrar(self):
        guardar_json(self._cliente,{'pid':os.getpid(),'nacimiento':identidad(os.getpid())})
        self._registrada=True

    def _resultado(self,r,gestion):
        self._ultima=dict(r,gestion=gestion);self._comprobada=time.monotonic()
        return dict(self._ultima)

    def asegurar(self,timeout=10,forzar=False):
        presupuesto=max(.1,min(15,float(timeout)));fin=time.monotonic()+presupuesto
        if not self._lock.acquire(timeout=presupuesto):
            return {'ok':False,'tipo':'ocupada','error':'Otra solicitud está preparando Ollama; conserva la pregunta y reintenta en unos segundos.'}
        try:
            if self._cerrada.is_set():return {'ok':False,'tipo':'cerrada','error':'La sesión de Jarvis se está cerrando.'}
            if not self.habilitada:return {'ok':False,'tipo':'prueba','error':'El autoinicio está deshabilitado en pruebas.'}
            if not forzar and self._ultima and self._ultima['ok'] and time.monotonic()-self._comprobada<1:
                return dict(self._ultima)
            try:
                restante=fin-time.monotonic()
                if restante<=0:raise TimeoutError('Plazo de preparación agotado.')
                resultado=self._asegurar(restante)
                if not resultado['ok']:self._retirar()
                return resultado
            except (OSError,ValueError,RecursionError) as e:
                try:self._retirar()
                except (OSError,ValueError):pass
                tipo='no_instalado' if isinstance(e,FileNotFoundError) else 'control'
                error=('No encontré el ejecutable local de Ollama; no instalé ni descargué nada.'
                       if tipo=='no_instalado' else 'No pude preparar el inicio seguro de Ollama ('+type(e).__name__+').')
                return self._resultado({'ok':False,'tipo':tipo,'error':error},'sin_iniciar')
        finally:self._lock.release()

    def _asegurar(self,timeout):
        fin=time.monotonic()+timeout
        while not self._cerrada.is_set() and time.monotonic()<fin:
            preparado=self._preparar(min(timeout,max(.01,fin-time.monotonic())))
            if preparado.get('esperar'):
                self._cerrada.wait(.1)
                continue
            if 'resultado' in preparado:
                return self._resultado(preparado['resultado'],preparado['gestion'])
            gestion=preparado['gestion']
            break
        else:return self._resultado({'ok':False,'tipo':'inicio','error':'La sesión anterior de Ollama todavía se está cerrando. Reintenta en unos segundos.'},'sin_iniciar')
        while time.monotonic()<fin and not self._cerrada.is_set():
            control=leer_json(self.raiz/'control.json') or {}
            if control.get('estado')=='error':
                codigo=control.get('error_codigo')
                mensaje=MOTIVOS_INICIO.get(codigo if isinstance(codigo,str) else '',
                    'Ollama no terminó de iniciar; no hay una causa adicional confirmada.')
                return self._resultado({'ok':False,'tipo':'inicio','error':mensaje},gestion)
            salud=comprobar(self.url,timeout=min(.4,max(.01,fin-time.monotonic())))
            if salud['ok']:
                if control.get('estado')=='preexistente':
                    self._retirar()
                    return self._resultado(salud,'preexistente')
                if control.get('estado')=='iniciando':
                    self._cerrada.wait(.05)
                    continue
                if not self._ultima or not self._ultima.get('ok'):
                    self.avisar('Ollama disponible. Se cerrará cuando termine la última sesión de Jarvis que lo está usando.')
                return self._resultado(salud,gestion)
            if not vivo(control):break
            self._cerrada.wait(.1)
        self._retirar()
        return self._resultado({'ok':False,'tipo':'inicio','error':'Ollama no quedó disponible dentro del plazo de inicio. Conservé la pregunta; /ollama muestra el estado.'},gestion)

    def _preparar(self,timeout):
        with bloqueo(self.raiz):
            control=leer_json(self.raiz/'control.json')
            if control and vivo(control):
                if control.get('estado') not in {'iniciando','disponible'}:return {'esperar':True}
                self._registrar()
                if self._token_actual!=control.get('token'):
                    self._token_actual=control.get('token');self.generacion+=1
                return {'gestion':'iniciado_por_jarvis'}
            else:
                if control and control.get('estado') in {'iniciando','disponible'}:
                    # Al morir el supervisor, Linux termina su hijo. Dale un
                    # margen breve antes de confundirlo con otro servidor.
                    token=control.get('token')
                    if self._sin_supervisor is None or self._sin_supervisor[0]!=token:
                        self._sin_supervisor=(token,time.monotonic())
                    if time.monotonic()-self._sin_supervisor[1]<.4:return {'esperar':True}
                salud=comprobar(self.url,timeout=min(1,timeout))
                if salud['ok']:return {'resultado':salud,'gestion':'preexistente'}
                if salud['tipo']!='detenido':return {'resultado':salud,'gestion':'sin_iniciar'}
                validar_destino(self.url,iniciar=True)
                ejecutable=self.ejecutable or shutil.which('ollama')
                if not ejecutable or not os.path.isfile(ejecutable) or not os.access(ejecutable,os.X_OK):
                    raise FileNotFoundError('ollama')
                self._registrar();token=uuid.uuid4().hex
                args=[sys.executable,'-B',str(Path(__file__).with_name('supervisor_ollama.py')),
                      '--url',self.url,'--raiz',str(self.raiz),'--token',token,
                      '--ejecutable',str(Path(ejecutable).resolve())]
                # El supervisor hereda solo lo necesario. Nunca recibe claves ni prompts.
                entorno={k:v for k,v in os.environ.items() if k in
                         {'PATH','HOME','LANG','LC_ALL','LD_LIBRARY_PATH','CUDA_VISIBLE_DEVICES',
                          'OLLAMA_MODELS','ROCR_VISIBLE_DEVICES','GGML_VK_VISIBLE_DEVICES','TMPDIR'}}
                proceso=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL,env=entorno,start_new_session=True,close_fds=True)
                nacimiento=identidad(proceso.pid)
                if nacimiento is None:
                    proceso.wait(timeout=1);raise OSError('El supervisor no inició')
                guardar_json(self.raiz/'control.json',{'pid':proceso.pid,'nacimiento':nacimiento,
                             'token':token,'estado':'iniciando'})
                # Retener el handle permite recoger al supervisor cuando ya terminó.
                self._supervisor=proceso
                self._token_actual=token;self.generacion+=1
                self.avisar('Ollama estaba apagado. Jarvis está iniciando un servidor local propio…')
                return {'gestion':'iniciado_por_jarvis'}

    def _retirar(self):
        if self._registrada:
            with bloqueo(self.raiz):
                self._cliente.unlink(missing_ok=True)
            self._registrada=False

    def invalidar(self):
        # Solo invalida una marca; una carrera puede provocar otra lectura,
        # nunca acreditar un servicio que no respondió.
        self._comprobada=0.

    def estado(self):
        r=dict(self._ultima or {'ok':False,'tipo':'sin_comprobar','gestion':'sin_comprobar'})
        r['sesion_cerrada']=self._cerrada.is_set()
        return r

    def cerrar(self):
        self._cerrada.set()
        with self._lock:
            try:self._retirar()
            except (OSError,ValueError):pass
            proceso=getattr(self,'_supervisor',None)
            if proceso is not None and proceso.poll() is not None:
                proceso.wait()
            atexit.unregister(self.cerrar)
