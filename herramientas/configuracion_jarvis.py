"""Configuración validada y escritura atómica, sin ejecutar valores como código."""
import json
import os
import tempfile
from entorno_jarvis import DATOS

ARCHIVO = DATOS / 'configuracion.json'
MODELO_BASE_DEEPSEEK = 'deepseek-r1:8b'
MODELO_PREDETERMINADO = 'jarvis-deepseek:8b'
MODELO_COTIDIANO = 'qwen3:8b'
ETIQUETA_AUTOMATICA = 'Automático'
DEFAULT = {'modelo':MODELO_PREDETERMINADO, 'modo':'normal', 'tamano_pagina':5,
           'timeout_modelo':120, 'timeout_auto':True, 'modo_gpu':'auto', 'capas_gpu':12, 'num_ctx':8192, 'num_predict':2048,
           'perfil':'equilibrado','hilos':0,'keep_alive':'5m','ollama_url':'http://127.0.0.1:11434',
           'seleccion_modelo':'manual','autoinicio_ollama':True}
PERFILES={'rapido':{'modelo':'qwen2.5-coder:1.5b','num_ctx':8192,'num_predict':1024,'hilos':8,'keep_alive':'5m'},
          'equilibrado':{'modelo':MODELO_PREDETERMINADO,'num_ctx':8192,'num_predict':2048,'hilos':0,'keep_alive':'5m'},
          'maximo':{'modelo':MODELO_PREDETERMINADO,'num_ctx':16384,'num_predict':4096,'hilos':8,'keep_alive':'10m'}}
MODOS = {'breve':'Responde de forma breve, sin omitir resultados relevantes.',
         'simple':'Explica con frases cortas. Usa pasos numerados y un ejemplo si ayuda. Explica las siglas y cada término técnico nuevo.',
         'tecnico':'Responde con precisión técnica, supuestos, restricciones y criterios de verificación; puedes usar terminología especializada.',
         'normal':'Usa explicaciones sencillas y concisas.',
         'detallado':'Explica los pasos y los resultados con más detalle cuando sea útil.'}


def validar(dato):
    if not isinstance(dato, dict) or set(dato)-set(DEFAULT):
        raise ValueError('Configuración desconocida o formato inválido')
    completo = dict(DEFAULT, **dato)
    if type(completo['timeout_auto']) is not bool:raise ValueError('Espera automática inválida.')
    if type(completo['autoinicio_ollama']) is not bool:raise ValueError('Inicio automático de Ollama inválido.')
    if completo['modo_gpu'] not in ('auto','cpu','mixto'):raise ValueError('Modo de GPU inválido: auto, cpu o mixto.')
    if type(completo['capas_gpu']) is not int or not 1<=completo['capas_gpu']<=128:raise ValueError('Capas GPU: elige entre 1 y 128; se comprueba también el límite del modelo.')
    if completo['seleccion_modelo'] not in ('manual','automatico'):
        raise ValueError('Selección de modelo inválida: manual o automatico.')
    if not isinstance(completo['perfil'],str) or completo['perfil'] not in PERFILES:raise ValueError('Perfil inválido: rapido, equilibrado o maximo.')
    if type(completo['hilos']) is not int or not 0<=completo['hilos']<=32:raise ValueError('Hilos: elige entre 0 (automático) y 32.')
    if not isinstance(completo['keep_alive'],str) or completo['keep_alive'] not in {'0','1m','5m','10m','30m','60m'}:raise ValueError('Tiempo de carga no válido.')
    validar_url(completo['ollama_url'])
    if not isinstance(completo['modelo'], str) or not completo['modelo'].strip() or len(completo['modelo'])>120 or any(ord(c)<32 for c in completo['modelo']):
        raise ValueError('Nombre de modelo inválido')
    if not isinstance(completo['modo'],str) or completo['modo'] not in MODOS:
        raise ValueError('Modo no válido: breve, normal o detallado')
    for k,a,b in [('tamano_pagina',1,20),('timeout_modelo',15,600),('num_ctx',4096,32768),('num_predict',128,8192)]:
        if type(completo[k]) is not int or not a<=completo[k]<=b:
            raise ValueError(f'{k} debe estar entre {a} y {b}')
    return completo


def etiqueta_modelo(ajustes):
    return ETIQUETA_AUTOMATICA if ajustes.get('seleccion_modelo') == 'automatico' else ajustes['modelo']

def validar_url(url):
    from urllib.parse import urlsplit
    if not isinstance(url,str):raise ValueError('URL de Ollama inválida.')
    u=urlsplit(url)
    if u.scheme not in {'http','https'} or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in {'','/'}:
        raise ValueError('Usa http(s)://equipo:11434 sin claves, rutas ni parámetros.')
    try:puerto=u.port
    except ValueError:raise ValueError('Puerto de Ollama inválido.')
    if puerto is not None and not 1<=puerto<=65535:raise ValueError('Puerto de Ollama inválido.')
    if any(ord(c)<33 for c in url):raise ValueError('URL con espacios o caracteres de control.')
    return url.rstrip('/')


def leer(ruta=ARCHIVO):
    if not ruta.exists():
        return dict(DEFAULT), ''
    try:
        if ruta.stat().st_size>16000:
            raise ValueError('Archivo demasiado grande')
        return validar(json.loads(ruta.read_text(encoding='utf-8'))), ''
    except (OSError, ValueError, TypeError):
        return dict(DEFAULT), 'La configuración guardada no se pudo leer. Uso los valores iniciales; /config muestra los ajustes.'


def guardar(datos, ruta=ARCHIVO):
    datos=validar(datos)
    ruta.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,tmp=tempfile.mkstemp(prefix='.config-',dir=ruta.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(datos,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,ruta)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return datos
