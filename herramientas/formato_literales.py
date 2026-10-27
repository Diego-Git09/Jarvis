"""Conserva identificadores pedidos por el usuario como campo de presentación."""
import re

_SOLO=re.compile(r'(?i)\b(?:responde|resp[oó]ndeme|contesta|cont[eé]stame|devuelve|dime)\s+(?:ahora\s+)?(?:solo|solamente|unicamente|únicamente|exactamente)\s+(?:con\s+)?["“`\']?([A-Za-z][A-Za-z0-9_-]{1,80})')
_CONDICION=re.compile(r'(?i)\b(?:cuando (?:yo )?(?:diga|escriba|te diga)|si digo)\s+["“`\']?([A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]{1,50})["”`\']?\s*[,;:]\s*(?:responde|resp[oó]ndeme|contesta|cont[eé]stame|devuelve|dime)\s+(?:solo|solamente|unicamente|únicamente|exactamente)\s+(?:con\s+)?["“`\']?([A-Za-z][A-Za-z0-9_-]{1,80})')


def _es_identificador(texto):
    return '_' in texto or '-' in texto or any(c.isdigit() for c in texto) or texto.isupper()


def _peticion_directa(texto,posicion):
    antes=texto[:posicion]
    clausula=re.split(r'[.!?\n;]',antes)[-1]
    if re.search(r'(?i)\b(?:no|nunca)\b',clausula):return False
    if any(antes.count(c)%2 for c in ['"',"'",'`']):return False
    return not re.search(r'(?i)\b(?:por ejemplo|un ejemplo|el documento dice|la frase|cita textual|hipotesis)\b',antes)


def solo_identificador(pedido):
    pedido=pedido.split('[Adjunto:',1)[0]
    if re.search(r'(?i)\b(?:crea|crear|mueve|mover|copia|borra|elimina|guarda|edita|modifica|aplica|revierte|ejecuta|instala)\b',pedido):return ''
    condiciones=list(_CONDICION.finditer(pedido))
    for m in _SOLO.finditer(pedido):
        if any(c.start()<=m.start()<c.end() for c in condiciones):continue
        contexto=pedido[:m.start()]+' '+pedido[m.end():]
        if re.search(r'(?i)\b(?:si|cuando|siempre que|a menos que|en caso)\b',contexto):continue
        # Solo reemplaza la prosa si toda la petición es de presentación.
        # Una lista de verbos nunca cubre todas las acciones (renombrar,
        # restaurar, adjuntar…); tampoco debe ocultar una segunda pregunta.
        prefijo=pedido[:m.start()].strip()
        sufijo=pedido[m.end():]
        solo_formato=(re.fullmatch(r'(?i)(?:(?:jarvis|por favor)[\s,:]*)*',prefijo) is not None and
                      re.fullmatch(r'''[\s.!?¡¿"”`']*''',sufijo) is not None)
        if solo_formato and _es_identificador(m[1]) and _peticion_directa(pedido,m.start()):return m[1]
    return ''


def respuesta_condicional(pedido,estado):
    """Contrato explícito de presentación; no entrena pesos ni ejecuta acciones."""
    import hilo_conversacion as H
    from lenguaje_jarvis import limpiar,normalizar
    visible=pedido.split('[Adjunto:',1)[0]
    if H.cambio_tema(visible):estado.pop('_contrato_literal',None)
    for m in _CONDICION.finditer(visible):
        if _es_identificador(m[2]) and _peticion_directa(visible,m.start()):
            estado['_contrato_literal']={'disparador':normalizar(limpiar(m[1])).strip(' ¿?¡!.,;:'),'literal':m[2]}
    regla=estado.get('_contrato_literal')
    actual=normalizar(limpiar(visible)).strip(' ¿?¡!.,;:')
    return regla['literal'] if regla and actual==regla['disparador'] else None

def etiqueta(pedido):
    pedido=pedido.split('[Adjunto:',1)[0]
    m=re.search(r'(?i)\b(?:conserva|mant[eé]n|incluye|usa)\s+(?:exactamente|literalmente)\s+[`"\']?([A-Za-z][A-Za-z0-9_-]{1,80})',pedido)
    if not m or re.search(r'(?i)\b(?:no|nunca|qu[eé] significa|ejemplo|el documento dice)\b',pedido[:m.start()]):return ''
    antes=pedido[:m.start()]
    if any(antes.count(c)%2 for c in ['"',"'",'`']):return ''
    return m[1]

def presentar(pedido,respuesta):
    identificador=solo_identificador(pedido)
    if identificador:return identificador
    e=etiqueta(pedido)
    if not e or e in respuesta:return respuesta
    patron=r'(?i)\b'+r'[\s_-]*'.join(re.escape(p) for p in re.split('[_-]',e))+r'\b'
    if re.search(patron,respuesta):return re.sub(patron,lambda _:e,respuesta)
    # La cabecera es el dato literal del usuario; no afirma que el modelo lo recordara.
    return e+': '+respuesta
