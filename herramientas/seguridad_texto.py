"""Redacción de secretos previa a captura y rechazo conservador para nube."""
import re
import json
from pathlib import Path

TERMINOS_PUBLICOS=Path(__file__).with_name('terminos_publicos_ia.json')

def terminos_publicos():
    try:
        if TERMINOS_PUBLICOS.is_symlink() or TERMINOS_PUBLICOS.stat().st_size>32000:return set()
        d=json.loads(TERMINOS_PUBLICOS.read_text())
        if not isinstance(d,list) or len(d)>1000 or any(not isinstance(t,str) or not re.fullmatch(r'[A-Za-zÁÉÍÓÚÑáéíóúñ][A-Za-zÁÉÍÓÚÑáéíóúñ0-9+.-]{0,59}',t) for t in d):return set()
        return {t.casefold() for t in d}
    except (OSError,ValueError):return set()

def redactar_credenciales(texto):
    # La clave configurada se redacta también si su proveedor cambia el prefijo.
    import os
    from pathlib import Path
    secretos=[os.environ.get(k,'') for k in ('OPENCODE_API_KEY','OPENCODE_ZEN_API_KEY','ZEN_API_KEY')]
    p=Path.home()/'.config/jarvis/zen.key'
    try:
        if not p.is_symlink() and not any(q.is_symlink() for q in p.parents) and p.stat().st_mode&0o077==0 and p.stat().st_size<=2048:secretos.append(p.read_text().strip())
    except OSError:pass
    for secreto in secretos:
        if len(secreto)>=12:texto=texto.replace(secreto,'[TOKEN ZEN REDACTADO]')
    # También cubre sqlplus usuario/clave@host y Easy Connect sin imprimirlos.
    texto=re.sub(r'(?i)(?<![\w/$@.-])(?:[\w.$#-]+|"[^"\n]+")/(?:"[^"\n]+"|[^\s/@]+)@[^\s;]+','[CONEXION REDACTADA]',texto)
    texto=re.sub(r'(?i)((?:--password|--passwd|--token|--api-key)(?:\s*=\s*|\s+))(?:"[^"\n]*"|\'[^\'\n]*\'|[^\s;]+)',r'\1[REDACTADO]',texto)
    texto=re.sub(r'(?im)(\b(?:authorization|proxy-authorization|x-api-key|opencode_api_key|opencode_zen_api_key|zen_api_key)["\']?\s*[:=]\s*)[^\r\n]+',r'\1[REDACTADO]',texto)
    texto=re.sub(r'\b(?:sk[-_][A-Za-z0-9_-]{8,}|oc[-_][A-Za-z0-9_-]{16,}|opencode[-_][A-Za-z0-9_-]{8,})\b','[TOKEN REDACTADO]',texto)
    texto=re.sub(r'(?i)(\b(?:contrase[ñn]a|password|passwd|clave api|api key|token)\s+(?:es\s+)?)(?:"[^"\n]+"|\'[^\'\n]+\'|[^\s,;]+)',r'\1[REDACTADO]',texto)
    return texto

def privacidad_externa(texto,*,adjuntos=False,memoria=False,herramientas=False):
    """Solo texto genérico explícito. Las dudas se mantienen en el equipo."""
    from conversaciones_jarvis import _redactar
    if not isinstance(texto,str) or not texto.strip():return False,'pregunta vacía'
    if adjuntos or memoria or herramientas:return False,'el turno usa fuentes locales, memoria o herramientas'
    if len(texto)>100000:return False,'tamaño superior al límite externo local'
    if _redactar(texto)!=texto:return False,'contiene posibles credenciales; quitarlas podría cambiar la petición'
    if re.search(r'\b[A-Za-z0-9_+/=-]{48,}\b',texto):return False,'contiene un identificador opaco que podría ser privado'
    if re.search(r'\b\d{8,}\b|\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b',texto,re.I):return False,'posibles identificadores personales'
    if re.search(r'(?:^|\s)\.{1,2}/',texto):return False,'contiene una ruta relativa'
    permitidos=terminos_publicos()
    if not permitidos:return False,'no se pudo validar el léxico público; se mantiene local'
    inicios={'Escribe','Explica','Explícame','Genera','Crea','Compara','Analiza','Demuestra','Razona','Calcula','Define','Traduce','Resume','Dime','Corrige','Depura','Diseña','Diagnostica','Evalúa','Necesito','Quiero','Puedes','Podrías','Usa','Sin','Solo','No','Con','Devuelve','Ejemplo','Qué','Que','Cómo','Como','Por','Cuánto','Cuanto'}
    for m in re.finditer(r'\b[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]{2,}\b',texto):
        inicio=not texto[:m.start()].strip(' ¿¡\n') or bool(re.search(r'[.!?]\s*$',texto[:m.start()]))
        if m[0].casefold() not in permitidos and not (inicio and m[0].casefold() in {i.casefold() for i in inicios}):return False,'un nombre propio no se puede acreditar como genérico'
    patrones=[(r'(?i)(?:https?://|~/|/home/|/tmp/|/etc/|/var/|/usr/|[A-Z]:\\|\b[\w.-]+\.(?:py|sql|pdf|docx|xlsx|csv|txt|json|md)\b)','rutas o referencias de archivos'),
        (r'(?i)(?:[\w.+-]+@[\w.-]+|\b(?:\d{1,3}\.){3}\d{1,3}\b|\b(?:usuario|username|contraseña|password|token|api.?key|authorization)\b)','identificadores o secretos'),
        (r'(?im)(?:^\S+@\S+[:~].*[$#]|Traceback|nvidia-smi|NVIDIA-SMI|\+[-+]{8}|\b(?:HOSTNAME|USER|HOME)\s*=)','salida de terminal o datos del equipo'),
        (r'(?i)\b(?:adjunto|adjuntos|mi archivo|mis archivos|segundo cerebro|mis recuerdos|conversacion guardada|mi universidad|universitario|universidad|duoc|evaluacion|crm|correo|contactos|mi trabajo|mi empresa|mi cliente|mi nombre|me llamo|mi direccion|mi telefono|lo anterior|ese documento|este documento|ese archivo|lo que te pase|mi caso|como te dije)\b','datos personales, académicos, laborales o guardados')]
    from normalizacion_entrada import plegar
    n=plegar(texto)
    for patron,motivo in patrones:
        if re.search(patron,n):return False,motivo
    if re.search(r'(?im)^\s*(?:Usuario:|Respuesta(?: final)?:|Jarvis:|Tú:)',texto):return False,'conversación pegada'
    if not re.search(r'(?i)\b(?:explica|explicame|que es|como|por que|compara|analiza|demuestra|escribe|genera|codigo|funcion|python|java|kotlin|sql|algoritmo|calcula|razona|define|traduce|resume|dime)\b',n):return False,'no se acredita una pregunta genérica'
    return True,'pregunta genérica sin fuentes locales detectadas'
