"""Presentación de prosa generada; no altera archivos ni resultados de herramientas."""
import re

EMOJI=re.compile('[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0E\uFE0F\u200D]')


def permite_emojis(pedido):
    from lenguaje_jarvis import normalizar
    visible=pedido.split('[Adjunto:',1)[0]
    sin_citas=re.sub(r'"[^"\n]*"|“[^”\n]*”|«[^»\n]*»|`[^`\n]*`|\'[^\'\n]*\'',' ',visible)
    n=normalizar(sin_citas)
    if re.search(r'\b(?:sin|no (?:uses|incluyas|pongas|agregues))\s+(?:los\s+)?(?:emojis?|emoticonos?|caritas?)\b',n):return False
    literal=EMOJI.search(pedido) and re.search(r'\b(?:literal|exactamente|unicamente|solo)\b',n) and re.search(r'\b(?:conserva|manten|copia|repite|escribe|responde|devuelve)\b',n)
    return bool(literal or re.search(r'\b(?:con|usa|incluye|agrega|anade|pon|ponle|quiero)\s+(?:un |una |unos |unas |algunos )?(?:emojis?|emoticonos?|caritas?)\b',n) or (EMOJI.search(pedido) and re.search(r'\b(?:significa|emoji|emoticono|simbolo|carita)\b',n)))


def presentar(pedido,respuesta):
    from lenguaje_jarvis import normalizar
    n=normalizar(pedido)
    literal=bool(re.search(r'\b(?:literal|exactamente|unicamente)\b',n) and re.search(r'\b(?:repite|copia|escribe|responde|devuelve)\b',n))
    if not literal:
        respuesta=re.sub(r'^\s*Explico con estilo (?:simple|tecnico|técnico):\s*','',respuesta,flags=re.I)
    if permite_emojis(pedido) or literal:return respuesta
    partes=re.split(r'(```[\s\S]*?(?:```|$)|`[^`\n]*`|“[^”\n]*”|«[^»\n]*»|"[^"\n]*"|\'[^\'\n]*\')',respuesta)
    for i in range(0,len(partes),2):
        partes[i]=EMOJI.sub('',partes[i])
        partes[i]=partes[i].replace('El usuario no autorizó','No autorizaste')
        partes[i]=re.sub(r'(?<!\.)\.\.(?![./\w])','.',partes[i])
    return '\n'.join(l.rstrip() for l in ''.join(partes).split('\n')).strip()
