"""Aclaraciones revisables sin guardar datos privados ni inventar intenciones."""
import json
import re
from entorno_jarvis import DATOS
from conversaciones_jarvis import _redactar,_privada,_atomic

ARCHIVO=DATOS/'vocabulario_pendientes.json'

def sanear(frase):
    t=_redactar(frase[:10000])
    t=re.sub(r'```[\s\S]*?(?:```|$)','[BLOQUE OMITIDO]',t)
    t=re.sub(r'\b[^\s@]+@[^\s:]+:[^\n$#]{0,180}[$#]','[TERMINAL]',t)
    t=re.sub(r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b','[CORREO]',t)
    t=re.sub(r'(?:~/|(?<!\w)/(?:[\w.-]+/)+|[A-Za-z]:\\)\S*','[RUTA]',t)
    t=re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b','[DIRECCION]',t)
    t=re.sub(r'\+?56\s*9(?:[ -]?\d){8}\b','[TELEFONO]',t)
    t=re.sub(r'(?i)\b(?:me llamo|mi nombre es)\s+[\wáéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñ]+)?','[NOMBRE OMITIDO]',t)
    return t[:600]

def listar():
    if not ARCHIVO.exists():return []
    if ARCHIVO.is_symlink() or ARCHIVO.stat().st_size>200000:raise ValueError('Lista de vocabulario inválida; se conservó sin sobrescribirla.')
    d=json.loads(ARCHIVO.read_text())
    if not isinstance(d,list):raise ValueError('Lista de vocabulario dañada.')
    return d

def aclarar(frase,respuesta,explicita=False):
    if not isinstance(frase,str) or _privada(frase):return respuesta
    if not explicita and not re.search(r'(?i)(no (?:entend|comprend)|¿(?:de qu[eé] tema|qu[eé] (?:tema|archivo|proyecto) quieres)|no pude interpretar)',respuesta):return respuesta
    f=sanear(frase);d=listar()
    if not any(x.get('frase')==f for x in d):d.append({'frase':f,'motivo':'El controlador/modelo pidió aclarar; interpretación sin confirmar.'});_atomic(ARCHIVO,d[-200:])
    # La aclaración del controlador ya especifica el dato que falta. No añadir
    # tres menús distintos ni convertir la duda en una propuesta ejecutable.
    preguntas=re.findall(r'¿[^?]+\?',respuesta)
    return preguntas[0] if len(preguntas)>1 else respuesta

def presentar():
    d=listar()
    return 'Frases pendientes de interpretación (no son reglas aprendidas):\n'+'\n'.join(f'{i}. {sanear(x["frase"])}' for i,x in enumerate(d,1)) if d else 'No hay frases pendientes de interpretación.'
