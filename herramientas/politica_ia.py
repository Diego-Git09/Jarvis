"""Política local sin interruptores controlados por chat, adjuntos o entorno."""
MENSAJE='Las consultas a IA externas están bloqueadas en esta instalación. Usa DeepSeek, Qwen u otro modelo local con /modelos y /preguntar_ia.'


def permite_externa():
    return False


def comprobar_externa():
    if not permite_externa():raise ValueError(MENSAJE)


def modelo_cloud(nombre):
    n=nombre.casefold() if isinstance(nombre,str) else ''
    return ':cloud' in n or n.endswith('-cloud')


def comprobar_destino_local(nombre,servidor):
    from urllib.parse import urlsplit
    if modelo_cloud(nombre) or urlsplit(servidor).hostname not in {'localhost','127.0.0.1','::1'}:
        raise ValueError('Solo se permiten modelos descargados en Ollama de este equipo; los modelos cloud y servidores de IA externos están bloqueados.')
