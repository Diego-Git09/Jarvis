"""Cliente oficial OpenCode en un espacio vacío, sin herramientas ni datos del usuario."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import tempfile
import time

from entorno_jarvis import DATOS
from seguridad_texto import privacidad_externa

INSTALACION = DATOS / 'opencode_cliente'
RECIBO = INSTALACION / 'instalacion_verificada.json'
MODELO = 'deepseek-v4.1-flash-free'
MAX_SALIDA = 2_000_000
TIEMPO_MAXIMO = 60


def binario():
    """Usa exclusivamente el ejecutable instalado y comprobado para Jarvis."""
    try:
        if RECIBO.is_symlink() or RECIBO.stat().st_size > 16000:return None
        d = json.loads(RECIBO.read_text())
        relativo = Path(d['binario'])
        if relativo.is_absolute() or '..' in relativo.parts:return None
        p = INSTALACION / relativo
        if any(x.is_symlink() for x in (p, *p.parents)):return None
        if not p.is_file() or not os.access(p, os.X_OK):return None
        with p.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != d['sha256']:return None
        return p
    except (OSError, ValueError, KeyError, TypeError):return None


def disponible():
    return bool(shutil.which('bwrap') and binario())


def configuracion():
    modelo = 'opencode/' + MODELO
    return {
        'model':modelo, 'small_model':modelo, 'enabled_providers':['opencode'],
        'default_agent':'jarvis_texto', 'permission':{'*':'deny'},
        'agent':{'jarvis_texto':{
            'mode':'primary', 'description':'Respuesta de texto sin herramientas',
            'model':modelo, 'steps':1, 'permission':{'*':'deny'},
            'prompt':'Responde en español sencillo a la pregunta genérica. Solo texto. No tienes acceso a archivos, recuerdos, terminal ni herramientas. No afirmes haber ejecutado acciones.',
        }},
        'provider':{'opencode':{'options':{'apiKey':'{env:OPENCODE_API_KEY}'}}},
        'snapshot':False, 'share':'disabled', 'autoupdate':False,
        'plugin':[], 'mcp':{}, 'instructions':[], 'lsp':False, 'formatter':False,
    }


def preparar_aislamiento(carpeta, token):
    """La aplicación solo ve sistema, su instalación y carpetas temporales vacías."""
    carpeta = Path(carpeta)
    ejecutable = binario()
    if not ejecutable or not shutil.which('bwrap'):
        raise ConnectionError('El cliente oficial OpenCode o su aislamiento no están disponibles. Se mantiene local.')
    for nombre in ('tarea','home','config','cache','datos','estado','temporal'):
        (carpeta/nombre).mkdir(mode=0o700)
    (carpeta/'passwd').write_text(
        'root:x:0:0:Sandbox:/work/home:/bin/false\n'
        f'assistant:x:{os.getuid()}:{os.getgid()}:Sandbox:/work/home:/bin/false\n')
    (carpeta/'hosts').write_text('127.0.0.1 localhost\n::1 localhost\n')
    entorno = {
        'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8', 'TMPDIR':'/work/temporal',
        'XDG_CONFIG_HOME':'/work/config', 'XDG_CACHE_HOME':'/work/cache',
        'XDG_DATA_HOME':'/work/datos', 'XDG_STATE_HOME':'/work/estado',
        'OPENCODE_API_KEY':token,
        'OPENCODE_CONFIG_CONTENT':json.dumps(configuracion()),
        'OPENCODE_PERMISSION':json.dumps({'*':'deny'}),
        'OPENCODE_DISABLE_AUTOUPDATE':'1', 'OPENCODE_DISABLE_PRUNE':'1',
        'OPENCODE_DISABLE_DEFAULT_PLUGINS':'1', 'OPENCODE_DISABLE_LSP_DOWNLOAD':'1',
        'OPENCODE_DISABLE_AUTOCOMPACT':'1', 'OPENCODE_DISABLE_CLAUDE_CODE':'1',
        'OPENCODE_DISABLE_MODELS_FETCH':'1',
        'OPENCODE_EXPERIMENTAL_DISABLE_FILEWATCHER':'1',
        'DO_NOT_TRACK':'1', 'OTEL_SDK_DISABLED':'true',
    }
    args = [shutil.which('bwrap'), '--unshare-all', '--share-net', '--die-with-parent',
            '--hostname','jarvis-texto', '--ro-bind','/usr','/usr',
            '--symlink','usr/bin','/bin', '--symlink','usr/lib','/lib',
            '--symlink','usr/lib64','/lib64', '--proc','/proc', '--dev','/dev',
            '--tmpfs','/tmp', '--dir','/etc',
            '--ro-bind','/etc/ssl','/etc/ssl',
            '--ro-bind','/etc/resolv.conf','/etc/resolv.conf',
            '--ro-bind',str(carpeta/'passwd'),'/etc/passwd',
            '--ro-bind',str(carpeta/'hosts'),'/etc/hosts',
            '--ro-bind',str(INSTALACION),'/opt/opencode',
            '--bind',str(carpeta),'/work', '--chdir','/work/tarea',
            '/opt/opencode/'+str(ejecutable.relative_to(INSTALACION))]
    return args, entorno


class Proceso:
    def __init__(self, proceso):self.proceso = proceso
    def close(self):
        if self.proceso.poll() is None:
            try:os.killpg(self.proceso.pid, signal.SIGKILL)
            except ProcessLookupError:pass


def interpretar_eventos(salida):
    textos = []; final = False
    for linea in salida.splitlines():
        if not linea.strip():continue
        try:e = json.loads(linea)
        except ValueError:raise ConnectionError('El cliente OpenCode devolvió eventos no válidos.') from None
        if not isinstance(e, dict):raise ConnectionError('Evento OpenCode inválido.')
        tipo = e.get('type'); parte = e.get('part', {})
        if tipo in {'tool_use','tool_call','permission'} or isinstance(parte, dict) and parte.get('type') == 'tool':
            raise ConnectionError('OpenCode intentó usar herramientas; su respuesta se descartó.')
        if tipo == 'error':
            error=e.get('error',{})
            datos=error.get('data',{}) if isinstance(error,dict) else {}
            try:
                remoto=json.loads(datos.get('responseBody','{}')) if isinstance(datos,dict) else {}
                detalle=remoto.get('error',{}) if isinstance(remoto,dict) else {}
            except (ValueError,TypeError):detalle={}
            if isinstance(detalle,dict) and detalle.get('type')=='FreeTierError':
                raise ConnectionError('OpenCode rechazó el nivel gratuito incluso con su cliente oficial (HTTP 403, FreeTierError). La causa concreta no está confirmada; se mantiene local.')
            status=datos.get('statusCode') if isinstance(datos,dict) else None
            if type(status) is int and 400<=status<=599:
                raise ConnectionError('El cliente oficial OpenCode recibió HTTP '+str(status)+'. Sin causa adicional confirmada.')
            raise ConnectionError('El cliente oficial OpenCode rechazó o no completó la consulta.')
        if tipo == 'text' and isinstance(parte, dict) and isinstance(parte.get('text'), str):
            textos.append(parte['text'])
        if tipo == 'step_finish' and isinstance(parte, dict) and parte.get('reason') == 'stop':final = True
    if not textos or not final:raise ConnectionError('OpenCode no confirmó una respuesta de texto completa.')
    return '\n'.join(textos)


def consultar(cuerpo, token, cancelado=None, registrar=None, retirar=None):
    if not isinstance(cuerpo, dict) or cuerpo.get('model') != MODELO or cuerpo.get('tools'):
        raise ValueError('El cliente oficial solo admite el modelo gratuito autorizado y texto sin herramientas.')
    mensajes = cuerpo.get('messages', [])
    usuarios = [m for m in mensajes if isinstance(m,dict) and m.get('role') == 'user']
    if len(usuarios)!=1 or any(not isinstance(m,dict) or m.get('role') not in {'system','user'} or set(m)-{'role','content'} for m in mensajes):
        raise ValueError('OpenCode solo recibe la pregunta actual, sin historial ni adjuntos.')
    pregunta = usuarios[0].get('content')
    if not privacidad_externa(pregunta)[0]:raise ValueError('La pregunta no admite envío externo; se mantiene local.')
    if not token:raise ValueError('Falta la clave OpenCode.')
    with tempfile.TemporaryDirectory(prefix='jarvis-opencode-') as tmp:
        args, entorno = preparar_aislamiento(tmp, token)
        args += ['run','--format','json','--model','opencode/'+MODELO,
                 '--agent','jarvis_texto','--title','Consulta genérica','--port','0']
        try:
            proceso = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=entorno, start_new_session=True)
        except OSError:
            raise ConnectionError('No se pudo iniciar el cliente OpenCode aislado; se mantiene local.') from None
        handle = Proceso(proceso)
        stdout = bytearray(); stderr = bytearray(); selector = selectors.DefaultSelector()
        try:
            if registrar:registrar(handle)
            entrada=pregunta.encode(); posicion=0
            os.set_blocking(proceso.stdin.fileno(),False)
            selector.register(proceso.stdin, selectors.EVENT_WRITE, None)
            selector.register(proceso.stdout, selectors.EVENT_READ, stdout)
            selector.register(proceso.stderr, selectors.EVENT_READ, stderr)
            plazo = time.monotonic()+TIEMPO_MAXIMO
            while selector.get_map():
                if cancelado and cancelado.is_set():raise ConnectionError('Consulta OpenCode cancelada.')
                if time.monotonic()>plazo:raise ConnectionError('El cliente OpenCode agotó el tiempo; se conserva la respuesta local.')
                for llave, _ in selector.select(.1):
                    if llave.data is None:
                        try:posicion+=os.write(llave.fileobj.fileno(),entrada[posicion:posicion+16384])
                        except BrokenPipeError:posicion=len(entrada)
                        if posicion==len(entrada):selector.unregister(llave.fileobj);proceso.stdin.close()
                        continue
                    datos = os.read(llave.fileobj.fileno(), 16384)
                    if not datos:selector.unregister(llave.fileobj);continue
                    llave.data.extend(datos)
                    if len(llave.data)>MAX_SALIDA:raise ConnectionError('OpenCode excedió el límite de salida; se descartó la respuesta.')
            proceso.wait(timeout=max(.01,plazo-time.monotonic()))
            texto = interpretar_eventos(stdout.decode('utf-8'))
            if proceso.returncode:raise ConnectionError('El cliente oficial OpenCode no pudo completar la consulta.')
            return {'choices':[{'message':{'content':texto,'role':'assistant'}}]}
        except ConnectionError:raise
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            raise ConnectionError('No se completó el cliente OpenCode ('+type(error).__name__+').') from None
        finally:
            handle.close()
            proceso.wait()
            selector.close()
            if not proceso.stdin.closed:proceso.stdin.close()
            proceso.stdout.close(); proceso.stderr.close()
            if retirar:retirar(handle)
