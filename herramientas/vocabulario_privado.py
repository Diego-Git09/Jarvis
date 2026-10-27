"""Términos explícitos del usuario; archivo privado, acotado y con bloqueo."""
import fcntl
import json
import re
import shlex
from entorno_jarvis import DATOS

ARCHIVO=DATOS/'vocabulario_privado.json'

def leer(estricto=False):
    if ARCHIVO.is_symlink() or any(p.is_symlink() for p in ARCHIVO.parents):
        if estricto:raise ValueError('La ruta de vocabulario contiene un enlace')
        return {}
    try:
        if ARCHIVO.stat().st_size>100000:raise ValueError('Vocabulario demasiado grande')
        d=json.loads(ARCHIVO.read_text())
        if not isinstance(d,dict) or len(d)>500:raise ValueError('Formato inválido')
        for k,v in d.items():validar(k,v)
        return d
    except FileNotFoundError:return {}
    except (OSError,ValueError,TypeError):
        if estricto:raise ValueError('El vocabulario existente no es válido; se conserva para revisarlo.')
        return {}

def validar(a,b):
    if not all(isinstance(s,str) and re.fullmatch(r'[a-záéíóúüñ][a-záéíóúüñ -]{0,59}',s) for s in (a,b)):
        raise ValueError('Usa palabras o frases cortas, sin comandos, rutas, números ni símbolos.')
    from conversaciones_jarvis import _redactar
    if any(_redactar(s)!=s for s in (a,b)):raise ValueError('No se aprenden credenciales')

def cambiar(a,b,confirmar):
    from normalizacion_entrada import plegar
    from conversaciones_jarvis import _atomic
    a=plegar(a);b=plegar(b) if b is not None else None
    validar(a,b or a)
    antes=leer(estricto=True)
    if b is None and a not in antes:return 'Ese término no está aprendido.'
    if b is not None and len(antes)>=500 and a not in antes:return 'El vocabulario alcanzó 500 términos.'
    if not confirmar(('Quitar '+a if b is None else f'Aprender «{a}» como «{b}»')+' en tu vocabulario privado?'):return 'Vocabulario sin cambios.'
    DATOS.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=DATOS/'vocabulario_privado.lock'
    if lock.is_symlink() or ARCHIVO.is_symlink():raise ValueError('Ruta de vocabulario no segura')
    with lock.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        if leer()!=antes:raise ValueError('El vocabulario cambió; vuelve a revisar la propuesta.')
        if b is None:antes.pop(a)
        else:antes[a]=b
        _atomic(ARCHIVO,antes)
    return 'Vocabulario actualizado y comprobado.' if leer()==antes else 'No pude comprobar el vocabulario.'

def comando(p,confirmar):
    try:
        if p.startswith('/aprender_palabra'):
            m=re.fullmatch(r'/aprender_palabra\s+"([^"]+)"\s*=\s*"([^"]+)"',p)
            if not m:return True,'Uso: /aprender_palabra "palabra" = "significado". Se pide permiso antes de guardar.'
            return True,cambiar(m[1],m[2],confirmar)
        if p=='/vocabulario':
            d=leer();return True,('Vocabulario privado aprendido:\n'+'\n'.join(f'• {a} = {b}' for a,b in sorted(d.items())) if d else 'Todavía no hay palabras aprendidas.')+'\nQuitar: /vocabulario quitar "palabra".'
        if p.startswith('/vocabulario quitar '):
            a=shlex.split(p)
            return True,cambiar(a[2],None,confirmar) if len(a)==3 else (True,'Indica una palabra entre comillas.')
    except (OSError,ValueError) as e:return True,'Vocabulario sin cambios: '+str(e)
    return False,''
