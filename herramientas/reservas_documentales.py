"""Fragmentos de condiciones en fuentes: detección literal, nunca permisos.

El diccionario es dato editable, no expresiones regulares ejecutables. Retener
estas frases no demuestra equivalencia semántica universal de un resumen.
"""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

RUTA=Path(__file__).with_suffix('.json')
MAX_REGLAS=16384
MAX_FRAGMENTOS=6
MAX_CARACTERES=1200


def _normalizar(t):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD',t.casefold()) if not unicodedata.combining(c)).split())


def cargar():
    if RUTA.is_symlink():raise ValueError('El diccionario de condiciones no puede ser un enlace.')
    with RUTA.open('rb') as f:raw=f.read(MAX_REGLAS+1)
    if len(raw)>MAX_REGLAS:raise ValueError('Diccionario de condiciones demasiado grande.')
    try:d=json.loads(raw)
    except (ValueError,UnicodeError) as e:raise ValueError('El diccionario de condiciones no tiene JSON válido.') from e
    if not isinstance(d,dict) or set(d)!={'version','categorias'} or type(d['version']) is not int or d['version']!=1:
        raise ValueError('Versión de diccionario de condiciones inválida.')
    categorias=d['categorias']
    if not isinstance(categorias,dict) or not 1<=len(categorias)<=12:raise ValueError('Categorías de condiciones inválidas.')
    patrones={}
    for nombre,reglas in categorias.items():
        if not isinstance(nombre,str) or not re.fullmatch(r'[a-z_]{1,40}',nombre):raise ValueError('Categoría de condiciones inválida.')
        if not isinstance(reglas,dict) or set(reglas)!={'palabras','frases','prefijos'}:raise ValueError('Reglas de condiciones inválidas.')
        grupos=[]
        for tipo,lista in reglas.items():
            if not isinstance(lista,list) or len(lista)>100:raise ValueError('Lista de condiciones fuera de límite.')
            for frase in lista:
                if not isinstance(frase,str) or not 1<=len(frase)<=80 or any(ord(c)<32 for c in frase):raise ValueError('Marcador de condición inválido.')
                valor=_normalizar(frase)
                if not valor:raise ValueError('Marcador de condición vacío.')
                patron=re.escape(valor).replace(r'\ ',r'\s+')
                grupos.append(r'(?<!\w)'+patron+(r'\w*' if tipo=='prefijos' else r'(?!\w)'))
        if grupos:patrones[nombre]=re.compile('|'.join(grupos))
    if not patrones:raise ValueError('El diccionario de condiciones no tiene marcadores.')
    return {'sha256':hashlib.sha256(raw).hexdigest(),'patrones':patrones}


def _frases(texto):
    # Conserva las líneas envueltas del PDF. Un salto doble separa párrafos;
    # una puntuación dentro de una cita o un nombre no separa la frase.
    inicio=0;i=0;cierre=None
    pares={'"':'"',"'":"'",'«':'»','“':'”','‘':'’','`':'`'}
    while i<len(texto):
        c=texto[i]
        if cierre:
            if c==cierre:
                if i+1<len(texto) and texto[i+1]==c:i+=2;continue
                cierre=None
        elif c in pares and not (c=="'" and i and i+1<len(texto) and texto[i-1].isalnum() and texto[i+1].isalnum()):cierre=pares[c]
        fin=None
        if cierre is None:
            if c in '.!?' and (i+1==len(texto) or texto[i+1].isspace()):fin=i+1
            elif c=='\n' and re.match(r'\n[ \t]*\n',texto[i:]):fin=i
        if fin is not None:
            frase=texto[inicio:fin].strip()
            if frase:yield frase
            inicio=i+1
        i+=1
    frase=texto[inicio:].strip()
    if frase:yield frase


def extraer(texto,reglas):
    if not isinstance(texto,str) or len(texto)>4000:raise ValueError('Trozo fuera del límite de condiciones.')
    vistos=set();salida=[]
    for frase in _frases(texto):
        normal=_normalizar(frase)
        categorias=[nombre for nombre,p in reglas['patrones'].items() if p.search(normal)]
        if categorias and normal not in vistos:
            vistos.add(normal);salida.append({'texto':frase,'categorias':categorias})
    return salida


def textos(fragmentos):return list(dict.fromkeys(f['texto'] for f in fragmentos))


def validar_capacidad(fragmentos):
    if len(fragmentos)>MAX_FRAGMENTOS or sum(len(f['texto']) for f in fragmentos)>MAX_CARACTERES:
        raise ValueError('Las condiciones de este trozo exceden el perfil de generación; se conservan sus extractos literales.')


def faltantes(texto,fragmentos):
    # Admite espacios, mayúsculas y puntuación terminal distintos, sin cambiar
    # palabras, cifras, tildes ni el orden de la condición de la fuente.
    normal=' '.join(texto.casefold().split())
    return [f['texto'] for f in fragmentos if re.search(r'(?<!\w)'+re.escape(' '.join(f['texto'].casefold().split()).rstrip('.!?'))+r'(?!\w)',normal) is None]


def comprobar(texto,fragmentos):
    if faltantes(texto,fragmentos):raise ValueError('El resumen omitió una condición o reserva literal de la fuente; no se presenta como generación completa.')
