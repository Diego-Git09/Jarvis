"""Respaldo de inferencia local; una acción iniciada nunca se repite aquí."""
from urllib.parse import urlsplit
from configuracion_jarvis import MODELO_COTIDIANO, MODELO_PREDETERMINADO, MODELO_BASE_DEEPSEEK


def hubo_herramientas(historial, desde):
    return any(m.get('tool_calls') or m.get('role')=='tool' for m in historial[desde:])


def elegir(actual, instalados, servidor):
    if urlsplit(servidor).hostname not in {'127.0.0.1','localhost','::1'}:
        raise ConnectionError('El respaldo solo utiliza Ollama en este equipo. Revisa /ollama_url y /diagnostico.')
    otro=MODELO_COTIDIANO if actual in {MODELO_PREDETERMINADO,MODELO_BASE_DEEPSEEK} else MODELO_PREDETERMINADO
    if otro==actual or otro not in instalados:
        raise ConnectionError('El otro modelo local no está instalado. /modelos muestra los disponibles; no descargué nada.')
    return otro


def admite_otro(pregunta):
    import re
    from lenguaje_jarvis import normalizar
    n=normalizar(pregunta)
    return not (re.search(r'\b(?:no (?:uses|utilices|consultes)|sin (?:usar|consultar)) (?:a )?(?:otra ia|otro modelo|qwen|deepseek)\b',n) or
                re.search(r'\bsolo (?:con |usa |utiliza )?(?:deepseek|qwen|este modelo)\b',n))
