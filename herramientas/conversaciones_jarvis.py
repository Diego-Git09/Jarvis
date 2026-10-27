"""Cola local resistente a interrupciones para guardar cada turno de Jarvis."""
from datetime import datetime, timezone, timedelta
import json
import os
import re
import tempfile
import uuid
import time
from zoneinfo import ZoneInfo

from entorno_jarvis import DATOS, en_pruebas

COLA = DATOS / 'conversaciones_pendientes'
SESION = uuid.uuid4().hex
MAX_INTENTOS_POR_VUELTA = 20
TIEMPO_MAXIMO_ENVIO = 8
ESPERA_RESPUESTA = timedelta(minutes=10)


def _ahora():
    return datetime.now(timezone.utc)


def _iso():
    return _ahora().isoformat()


def _privada(pregunta):
    p = pregunta.casefold().strip()
    return bool(re.search(
        r'(?is)(?:^|[\s,;:])(?:/privado\b|modo privado\b|esto es privado\b|'
        r'(?:jarvis[, :]*)?(?:no (?:me )?(?:guardes(?: nada)?(?: de esto| este (?:turno|mensaje|chat|registro))?|registres|almacenes|archives)|'
        r'no (?:me )?lo guardes|no quiero guardar|'
        r'no quiero que (?:.{0,60} )?(?:se guarde|guarde|guardes|guarden|se registre|registre|registres|registren|se almacene|almacene|almacenes|almacenen|se archive|archive|archives|archiven)|'
        r'que no quede guardado)\b)', p[:400]))


def _redactar(texto):
    from seguridad_texto import redactar_credenciales
    texto=redactar_credenciales(texto)
    # Credenciales en URL y cabeceras, incluso si son cortas o entre comillas.
    texto=re.sub(r'(?i)(https?://)[^\s/@]+:[^\s/@]+@',r'\1[CREDENCIALES REDACTADAS]@',texto)
    texto=re.sub(r'(?im)(\b(?:authorization|proxy-authorization|x-api-key|api-key|cookie|set-cookie)["\']?\s*[:=]\s*)([^\r\n]+)',r'\1[REDACTADO]',texto)
    texto=re.sub(r'\bAIza[0-9A-Za-z_-]{20,}\b','[TOKEN REDACTADO]',texto)
    texto=re.sub(r'\b(?:xox[baprs]-[0-9A-Za-z-]{12,}|hf_[0-9A-Za-z]{20,})\b','[TOKEN REDACTADO]',texto)
    texto=re.sub(r'(?i)([?&](?:key|api_key|token|access_token|password|secret)=)[^&#\s]+',r'\1[REDACTADO]',texto)
    texto = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', '[CLAVE PRIVADA REDACTADA]', texto, flags=re.S)
    auth = r'(?i)(\b[A-Za-z0-9_.-]{0,80}authorization[A-Za-z0-9_.-]{0,80}[\"\']?\s*[:=]\s*[\"\']?)(?:(?:Bearer|Basic)\s+)?[A-Za-z0-9._~+/=-]{12,}'
    texto = re.sub(auth, r'\1[REDACTADO]', texto)
    campo_secreto = r'(?i)(\b[A-Za-z0-9_.-]{0,80}(?:password|passwd|contrase(?:ñ|n)a|api[_ -]?key|access[_ -]?token|auth[_ -]?token|secret(?:[_ -]?key)?|private[_ -]?key|token)[A-Za-z0-9_.-]{0,80}[\"\']?\s*[:=]\s*[\"\']?)([^\s,;\"\'}&#]+)'
    texto = re.sub(campo_secreto, r'\1[REDACTADO]', texto)
    texto = re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}', 'Bearer [TOKEN REDACTADO]', texto)
    texto = re.sub(r'\bAKIA[0-9A-Z]{16}\b', '[TOKEN REDACTADO]', texto)
    texto = re.sub(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b', '[TOKEN REDACTADO]', texto)
    texto = re.sub(r'(?i)\bsk-[a-z0-9_-]{12,}\b', '[TOKEN REDACTADO]', texto)
    texto = re.sub(r'(?i)\b(?:gh[pousr]_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,})\b', '[TOKEN REDACTADO]', texto)
    return texto


def _atomic(path, data):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('La captura no puede escribir sobre enlaces simbólicos')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(prefix='.turno-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        dirfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def iniciar(pregunta):
    """Persiste la pregunta antes de llamar al modelo. Devuelve None si pidió privacidad."""
    if en_pruebas() or not isinstance(pregunta, str) or not pregunta.strip() or _privada(pregunta):
        return None
    ident = uuid.uuid4().hex
    fila = {'version': 1, 'clave': ident, 'fuente': 'Jarvis', 'creado': _iso(),
            'sesion': SESION, 'pid': os.getpid(), 'pregunta': _redactar(pregunta.strip()),
            'respuesta': '', 'estado': 'esperando'}
    _atomic(COLA / (ident + '.json'), fila)
    return ident


def finalizar(ident, respuesta, estado='completa'):
    if not ident:
        return False
    ruta = COLA / (ident + '.json')
    try:
        fila = json.loads(ruta.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    fila['respuesta'] = _redactar(str(respuesta or '').strip())
    fila['estado'] = estado if estado in {'completa', 'interrumpida', 'fallida'} else 'interrumpida'
    if fila['estado']=='completa' and (len(re.findall(r'\w+',fila.get('pregunta','')+' '+fila['respuesta']))<5 or '[Aviso: la respuesta se cortó' in fila['respuesta']):
        fila['categoria']='dudosa'
        fila['motivo_duda']='Intercambio demasiado corto o respuesta recortada; conservado localmente para revisar.'
    fila['finalizado'] = _iso()
    _atomic(ruta, fila)
    return True


def _proceso_activo(pid):
    try:
        pid = int(pid)
        if pid < 2:
            return False
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (TypeError, ValueError, ProcessLookupError, OSError):
        return False


def recuperar_interrumpidas():
    """Marca turnos en espera cuyo proceso ya terminó, por ejemplo tras un apagado."""
    if not COLA.exists():
        return 0
    recuperadas = 0
    for ruta in COLA.glob('*.json'):
        try:
            fila = json.loads(ruta.read_text(encoding='utf-8'))
            if fila.get('estado') != 'esperando':
                continue
            pid = fila.get('pid')
            if pid is None:
                edad = _ahora() - datetime.fromisoformat(fila['creado'])
                if edad < ESPERA_RESPUESTA:
                    continue
            elif _proceso_activo(pid):
                continue
            fila['estado'] = 'interrumpida'
            fila['respuesta'] = ''
            fila['finalizado'] = _iso()
            _atomic(ruta, fila)
            recuperadas += 1
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return recuperadas


def _proyecto(pregunta):
    # Los chats con Jarvis se separan del contexto del desarrollo del programa.
    return 'CHAT JARVIS'


def _registro(fila):
    fila=dict(fila,pregunta=_redactar(fila['pregunta']),respuesta=_redactar(fila.get('respuesta','')))
    fecha = datetime.fromisoformat(fila['creado']).astimezone(ZoneInfo('America/Santiago'))
    titulo = f"Conversación Jarvis · {fecha:%d-%m-%Y %H:%M:%S}"
    contenido = ['Intercambio local de Jarvis.', '', 'Usuario:', fila['pregunta']]
    if fila['estado'] == 'completa' and fila.get('respuesta'):
        contenido.extend(['', 'Respuesta final de Jarvis:', fila['respuesta'], '', 'Estado: respuesta completa.'])
    elif fila.get('respuesta'):
        contenido.extend(['', 'Respuesta parcial de Jarvis (no confirmada como completa):', fila['respuesta'],
                          '', 'Estado: conversación inconclusa; se conserva la solicitud original y el texto parcial.'])
    else:
        contenido.extend(['', 'Respuesta de Jarvis: no quedó una respuesta completa en esta sesión.',
                          '', 'Estado: conversación inconclusa; se conserva la solicitud original.'])
    contenido.extend(['', 'Origen automático: jarvis; intercambio local guardado al cerrar la respuesta.'])
    return titulo, '\n'.join(contenido)


def guardar_pendientes(cliente, limite=MAX_INTENTOS_POR_VUELTA):
    """Entrega la cola por MCP sin repetir escrituras ni perderla si el servidor falla."""
    if en_pruebas():
        return {'guardadas': 0, 'pendientes': 0, 'revisadas': 0}
    recuperar_interrumpidas()
    fin_envio=time.monotonic()+TIEMPO_MAXIMO_ENVIO
    if not COLA.exists():
        return {'guardadas': 0, 'pendientes': 0}
    timeout_original = getattr(cliente, 'timeout', None)
    if isinstance(timeout_original, (int, float)):
        cliente.timeout = min(timeout_original, TIEMPO_MAXIMO_ENVIO)
    filas = sorted(COLA.glob('*.json'), key=lambda p: p.stat().st_mtime)
    candidatas=[];dudosas=0
    for ruta in filas:
        try:
            if ruta.is_symlink():continue
            fila=json.loads(ruta.read_text())
            if fila.get('categoria')=='dudosa':dudosas+=1;continue
        except (OSError,ValueError):pass
        candidatas.append(ruta)
    filas=candidatas
    guardadas = 0
    procesadas = 0
    for ruta in filas[:max(1, limite)]:
        restante=fin_envio-time.monotonic()
        if restante<=0:break
        if isinstance(timeout_original,(int,float)):cliente.timeout=min(timeout_original,max(.1,restante))
        try:
            fila = json.loads(ruta.read_text(encoding='utf-8'))
            if fila.get('version') != 1 or not re.fullmatch(r'[0-9a-f]{32}', str(fila.get('clave', ''))):
                continue
            if fila.get('estado') == 'esperando':
                edad = _ahora() - datetime.fromisoformat(fila['creado'])
                if edad < ESPERA_RESPUESTA:
                    continue
                fila['estado'] = 'interrumpida'
                fila['respuesta'] = ''
                _atomic(ruta, fila)
            titulo, contenido = _registro(fila)
            proyecto = _proyecto(fila['pregunta'])
            clave = fila['clave']
            # El MCP aplica una clave única en SQLite: un reintento no duplica el turno.
            cliente.guardar_conversacion(proyecto,titulo,contenido,clave,sesion=fila.get('sesion',''),creado=fila.get('creado',''))
            ruta.unlink(missing_ok=True)
            guardadas += 1
            procesadas += 1
        except ConnectionError:
            # Se conserva el archivo para el siguiente turno; no se reintenta una escritura a ciegas.
            break
        except Exception:
            continue
    if isinstance(timeout_original, (int, float)):
        cliente.timeout = timeout_original
    restantes = len(filas)-guardadas
    return {'guardadas': guardadas, 'pendientes': restantes, 'revisadas': procesadas,'dudosas':dudosas}


def sigue_pendiente(ident):
    return bool(ident and (COLA / (ident + '.json')).exists())
