"""El usuario confirma su uso; el léxico base nunca se reescribe en silencio."""
import json
import unicodedata
import fcntl
import os
from datetime import datetime,timezone
from entorno_jarvis import DATOS
from conversaciones_jarvis import _atomic

ARCHIVO=DATOS/'confirmaciones_vocabulario.json'

def plegar(t):return ''.join(x for x in unicodedata.normalize('NFD',t.casefold()) if unicodedata.category(x)!='Mn').strip()

def leer():
    if ARCHIVO.is_symlink() or any(p.is_symlink() for p in ARCHIVO.parents):raise ValueError('Ruta de confirmaciones no segura')
    try:
        if ARCHIVO.stat().st_size>200000:raise ValueError('Confirmaciones demasiado grandes')
        d=json.loads(ARCHIVO.read_text())
        if not isinstance(d,dict) or any(not isinstance(k,str) or not isinstance(v,dict) or v.get('estado') not in {'observado','pasivo'} for k,v in d.items()):raise ValueError('Confirmaciones inválidas; no sobrescribir')
        return d
    except FileNotFoundError:return {}

def ampliados():
    from normalizacion_entrada import BASE
    return [x for x in json.loads(BASE.read_text()) if x.get('origen')=='ampliado']

def presentar(forma):
    entrada=next(x for x in ampliados() if x['forma']==forma)
    s=entrada['significado'];s=' / '.join(s) if isinstance(s,list) else s
    return f"¿Usas «{forma}» para «{s}»? Responde sí, no o a veces. Luego se pide s/n antes de guardar. «no» lo deja solo como comprensión pasiva; Jarvis no lo adopta al hablar. /confirmar_vocabulario salir pausa."

def siguiente(estado):
    d=leer();pendientes=[x for x in ampliados() if x['forma'] not in d]
    if not pendientes:estado.pop('_confirmacion_vocabulario',None);return 'Revisaste todos los términos ampliados. /confirmar_vocabulario estado muestra tus decisiones.'
    forma=pendientes[0]['forma'];estado['_confirmacion_vocabulario']={'forma':forma};return presentar(forma)

def comando(p,estado,confirmar):
    n=plegar(p);activa=estado.get('_confirmacion_vocabulario')
    if n.startswith('/confirmar_vocabulario'):
        opcion=n.partition(' ')[2]
        if opcion=='salir':estado.pop('_confirmacion_vocabulario',None);return True,'Confirmación pausada; preferencias guardadas intactas.'
        if opcion=='estado':
            d=leer();return True,'Términos confirmados por ti:\n'+('\n'.join(k+' · '+v['estado']+' · '+v.get('uso','') for k,v in d.items()) or 'Ninguno todavía.')
        if opcion:return True,'Usa /confirmar_vocabulario, /confirmar_vocabulario estado o /confirmar_vocabulario salir.'
        estado.pop('_revision_respuestas',None);return True,siguiente(estado)
    if not activa or n not in {'s','si','no','n','a veces'}:return False,''
    forma=activa['forma'];d=leer();marca='pasivo' if n in {'no','n'} else 'observado'
    if not confirmar(f"Guardar «{forma}» como {marca}, uso «{n}», en tus datos privados? Solo confirma uso; no cambia su significado ni publica recuerdos."):
        return True,'Decisión sin guardar. Puedes responder otra vez o salir.'
    ARCHIVO.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=ARCHIVO.with_suffix('.lock')
    if lock.is_symlink():raise ValueError('Bloqueo no seguro')
    fd=os.open(lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        if leer()!=d:raise ValueError('Las confirmaciones cambiaron; vuelve a revisar')
        d[forma]={'estado':marca,'uso':n,'evidencia':'confirmación explícita del usuario','fecha':datetime.now(timezone.utc).isoformat()}
        _atomic(ARCHIVO,d)
    if leer()!=d:raise ValueError('No se pudo comprobar la confirmación')
    return True,'Uso guardado localmente.\n'+siguiente(estado)
