"""Citas contiguas con contexto; nunca inventa ni reescribe un recuerdo."""
import re

def autosuficiente(texto):
    t=texto.strip()
    if not t or len(t)<12 or len(t)>1800:return False
    if '\n' not in t and re.match(r'^\s*(?:#{1,6}\s|(?:objetivo|contenido|reglas de trabajo|modelos permitidos|pol[ií]tica de privacidad)\s*:?\s*$)',t,re.I):return False
    if re.fullmatch(r's[oó]lo\s+(?:dise[nñ]o|texto|c[oó]digo)\s*,?\s*(?:sin implementar|sin ejecutar)?[.!]?',t,re.I):return False
    if len(t)<160 and re.search(r'\b(?:secci[oó]n|apartado|cap[ií]tulo|punto|filtro|pol[ií]tica)\b.*?\b\d+\.\d+\b',t,re.I):return False
    if len(t)<100 and re.search(r'\b(?:lo anterior|lo de arriba|esa misma|la primera|la segunda)\b',t,re.I):return False
    return True

def candidatos(texto):
    if not isinstance(texto,str):return []
    bloques=list(re.finditer(r'\S.*?(?=\n[ \t]*\n|\Z)',texto,re.S))
    codigo=[m.span() for m in re.finditer(r'```[\s\S]*?(?:```|\Z)',texto)]
    salida=[];consumidos=set()
    for i,m in enumerate(bloques):
        if i in consumidos:continue
        if any(a<m.end() and b>m.start() for a,b in codigo):continue
        fragmento=m[0].strip()
        if '\n' not in fragmento and re.match(r'^#{1,6}\s',fragmento) and i+1<len(bloques):
            siguiente=bloques[i+1]
            fragmento=texto[m.start():siguiente.end()].strip()
            if any(a<siguiente.end() and b>m.start() for a,b in codigo):continue
            if autosuficiente(fragmento):consumidos.add(i+1)
        if autosuficiente(fragmento):salida.append(fragmento)
        # No convertir cada línea de un párrafo/lista en una decisión suelta.
        elif len(fragmento)>1800:
            for frase in re.split(r'(?<=[.!?])\s+',fragmento):
                if autosuficiente(frase):salida.append(frase)
    return list(dict.fromkeys(salida))[:64]
