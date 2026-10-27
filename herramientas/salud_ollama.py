"""Servidor local: distinguir una caída del servicio de un fallo del modelo."""
import errno
import json
import re
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

MAX_BYTES = 4096

def queja_conexion(vista):
    """Quejas exactas, en texto ya normalizado y sin literales; solo diagnóstico."""
    if len(vista)>220:return False
    return bool(re.fullmatch(
        r'(?:(?:oye|jarvis)[, ]+)?(?:no|nunca) (?:(?:me )?(?:funciona|responde|arranca) (?:el )?(?:servidor de )?ollama|'
        r'puedo conectarme (?:a|con) ollama)(?:[, ]+(?:que hago|puedes revisarlo|revisalo))?',
        vista.strip(' ¿?¡!.')))

class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError('No se siguen redirecciones del servicio local.')

def validar_destino(url, iniciar=False):
    from configuracion_jarvis import validar_url
    from politica_ia import comprobar_destino_local
    url=validar_url(url)
    comprobar_destino_local('',url)
    if iniciar and urlsplit(url).scheme!='http':
        raise ValueError('El inicio automático requiere HTTP local; no cambia la configuración HTTPS.')
    return url

def comprobar(url, timeout=1):
    """Solo GET /api/version, sin cargar modelos, proxies ni credenciales."""
    try:
        url=validar_destino(url)
        espera=max(.01,float(timeout));plazo=time.monotonic()+espera
        op=urllib.request.build_opener(urllib.request.ProxyHandler({}),SinRedireccion())
        with op.open(url+'/api/version',timeout=espera) as respuesta:
            from lectura_http import leer_acotado
            raw=leer_acotado(respuesta,MAX_BYTES+1,plazo)
        if len(raw)>MAX_BYTES:raise ValueError('Respuesta demasiado grande')
        datos=json.loads(raw)
        version=datos.get('version') if isinstance(datos,dict) else None
        if not isinstance(version,str) or not version.strip() or len(version)>100 or any(ord(c)<32 for c in version):
            raise ValueError('No se recibió una versión válida')
        return {'ok':True,'tipo':'disponible','version':version}
    except urllib.error.HTTPError as e:
        codigo=e.code;e.close()
        return {'ok':False,'tipo':'http','codigo':codigo,'error':'El servidor local respondió HTTP '+str(codigo)+'. No se iniciará otro servidor sobre ese puerto.'}
    except (OSError,ValueError,urllib.error.URLError) as e:
        causa=getattr(e,'reason',e)
        if isinstance(causa,ConnectionRefusedError) or getattr(causa,'errno',None)==errno.ECONNREFUSED:
            tipo='detenido';error='Ollama no acepta conexiones en el destino local configurado.'
        elif isinstance(causa,(TimeoutError,socket.timeout)):
            tipo='timeout';error='Ollama no respondió a tiempo. Puede estar ocupado; no se iniciará otro proceso encima.'
        elif isinstance(e,ValueError):
            tipo='respuesta';error='El destino no devolvió una versión de Ollama válida o no cumple la política local.'
        else:
            tipo='conexion';error='No pude comprobar la conexión local; no asumí que Ollama estuviera apagado.'
        return {'ok':False,'tipo':tipo,'error':error}
