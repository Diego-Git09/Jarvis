"""Peticiones explícitas de tareas; interpretación pura, sin escrituras.

Las variantes viven en vocabulario.json. Una pega se interpreta como tarea solo
en una petición inequívoca de lista/creación/estado; no convierte relatos en
acciones ni usa números de listados de otro dominio.
"""
import re

import lenguaje_jarvis as N

OBJETO=N.alternativas(N.VOCABULARIO.get('sustantivos',{}).get('tareas',['tarea','tareas','pega','pegas','pendiente','pendientes']))
ACCIONES={k:N.alternativas(v) for k,v in N.VOCABULARIO.get('acciones',{}).items() if k.startswith('tarea_')}
ART=r'(?:(?:el|la|los|las|mis?|una?|todas las|todos los)\s+)?'
VALOR=r'(alta|normal|baja|urgente|importante)'
ESTADO_HECHO=r'(?:hech[ao]s?|list[ao]s?|completad[ao]s?|terminad[ao]s?)'
ESTADO_PENDIENTE=r'(?:pendientes?|sin completar|no hech[ao]s?)'


def _aclarar(dato):
    preguntas={'texto':'¿Qué texto quieres poner en la tarea?',
               'numero':'¿Qué número de tarea del listado /tareas quieres cambiar?',
               'prioridad':'¿Qué prioridad quieres para esa tarea: alta, normal o baja?',
               'literal':'¿Puedes cerrar las comillas del texto de la tarea?',
               'cadena':'¿Quieres añadir una sola tarea o realizar varias acciones?'}
    return N.Intencion('aclarar',respuesta=preguntas[dato])


def _texto(original):
    t=original.strip();cierres={'«':'»','“':'”','‘':'’','"':'"',"'":"'",'`':'`'}
    if not t:return None
    if t[0] in cierres:
        fin=t.rfind(cierres[t[0]])
        if fin<=0:return None
        cola=t[fin+1:]
        if not re.fullmatch(r'\s*(?:[,;]\s*)?(?:po|poh|porfa|porfis|por favor)?[.!?]*\s*',cola,re.I):return None
        return t[1:fin] if t[1:fin].strip() else None
    # Un título sin comillas se conserva literal, incluidas sus palabras finales.
    return t


def _elegir(texto,estado,unica=False):
    if not isinstance(estado,dict) or estado.get('_tipo_ultimo_listado')!='tareas':return None
    mapa=estado.get('_tareas_visibles')
    if not isinstance(mapa,dict) or not mapa:return None
    numeros=N.seleccion(texto.strip(' ,;'),{'_lista_memorias':mapa})
    if not numeros or any(i not in mapa for i in numeros) or unica and len(numeros)!=1:return None
    return numeros


def _cambio(acceso,seleccion,estado,**argumentos):
    numeros=_elegir(seleccion,estado,unica=acceso in {'/editar_tarea','/prioridad'})
    if numeros is None:return _aclarar('numero')
    if acceso in {'/editar_tarea','/prioridad'}:argumentos['numero']=numeros[0]
    else:argumentos['numeros']=numeros
    return N.Intencion(acceso,argumentos)


def interpretar(frase,estado=None):
    if not isinstance(frase,str) or frase.lstrip().startswith('/') or N.no_es_peticion(frase):return None
    t=N.limpiar_prefijos(frase.strip(' ¿?¡!'));n=N.normalizar(t)
    # Las citas quedan intactas: solo se consulta la máscara para distinguir
    # otras órdenes reales de palabras dentro del texto de una tarea.
    mascara=N.sin_literales(t)
    if not re.search(r'\b'+OBJETO+r'\b',mascara,re.I):return None
    if re.search(r'\b(?:y luego|y despues|y después|luego|despues|después)\s+(?:borra|mueve|crea|anota|copia|elimina)\b',mascara,re.I):return _aclarar('cadena')
    lista=ACCIONES.get('tarea_listar',r'(?:muestra|lista)')
    if re.fullmatch(lista+r'\s+'+ART+r'(?:lista de\s+)?'+OBJETO+r'(?:\s+(?:pendientes|ahora))?(?:\s+(?:po|porfa|por favor))?',t,re.I) or re.fullmatch(r'que\s+'+OBJETO+r'\s+(?:tengo|me faltan)(?:\s+pendientes)?',n):
        return N.Intencion('/tareas',{'todas':bool(re.search(r'\btod[ao]s\b',n))})
    buscar=ACCIONES.get('tarea_buscar',r'(?:busca|encuentra)')
    m=re.fullmatch(buscar+r'\s+'+ART+OBJETO+r'\s+(?:sobre|que digan|con(?: el texto)?)\s+(.+)',t,re.I)
    if m:
        texto=_texto(m[1]);return N.Intencion('/buscar_tareas',{'texto':texto}) if texto else _aclarar('texto')
    crear=ACCIONES.get('tarea_crear',r'(?:anota|agrega)')
    # «Pon la tarea dos ...» se refiere a una existente; no es «pon una tarea».
    # Los artículos definidos de una referencia nunca abren la creación.
    destino_lista=r'(?:mis\s+(?:tareas|pendientes|pegas)|(?:mi|la)\s+lista de\s+'+OBJETO+r')'
    inicio=crear+r'\s+(?:(?:a|en)\s+'+destino_lista+r'|como\s+(?:una?\s+)?'+OBJETO+r'|(?:una?\s+)?'+OBJETO+r')'
    m=re.fullmatch(inicio+r'(?:\s+(?:llamad[ao]|titulad[ao]|con el titulo|con el título))?\s*:?\s*(.*)',t,re.I|re.S)
    if m:
        texto=_texto(m[1]);return N.Intencion('/anotar',{'texto':texto}) if texto else _aclarar('texto')
    # Prefijos antes/después del ordinal, siempre unidos a una tarea explícita.
    completar=ACCIONES.get('tarea_completar',r'(?:completa|termina)')
    reabrir=ACCIONES.get('tarea_reabrir',r'(?:reabre|vuelve a abrir)')
    for verbo,acceso in [(completar,'/hecho'),(reabrir,'/reabrir')]:
        m=re.fullmatch(verbo+r'\s+'+ART+OBJETO+r'(?:\s+(.+))?',t,re.I)
        if m:return _cambio(acceso,m[1] or '',estado)
    for fin,acceso in [(ESTADO_HECHO,'/hecho'),(ESTADO_PENDIENTE,'/reabrir')]:
        m=re.fullmatch(r'(?:marca|pon|deja)\s+'+ART+r'(.+?)\s+'+OBJETO+r'\s+(?:como\s+|en\s+)?'+fin,t,re.I)
        if m:return _cambio(acceso,m[1],estado)
        m=re.fullmatch(r'(?:marca|pon|deja)\s+(?:como\s+)?'+fin+r'\s+'+ART+OBJETO+r'\s+(.+)',t,re.I)
        if m:return _cambio(acceso,m[1],estado)
        m=re.fullmatch(r'(?:marca|pon|deja)\s+'+ART+OBJETO+r'\s+(.+?)\s+(?:como\s+|en\s+)?'+fin,t,re.I)
        if m:return _cambio(acceso,m[1],estado)
    editar=ACCIONES.get('tarea_editar',r'(?:edita|modifica|cambia)')
    cabecera=editar+r'\s+(?:(?:el\s+)?texto\s+de\s+|(?:a|al)\s+)?'+ART
    separador=r'(?:para que diga|que diga|a|por|el texto)'
    for patron in [cabecera+OBJETO+r'\s+(.+?)\s+'+separador+r'\s+(.+)',cabecera+r'(.+?)\s+'+OBJETO+r'\s+'+separador+r'\s+(.+)']:
        m=re.fullmatch(patron,t,re.I|re.S)
        if m:
            texto=_texto(m[2]);return _cambio('/editar_tarea',m[1],estado,texto=texto) if texto else _aclarar('texto')
    prioridad=ACCIONES.get('tarea_prioridad',r'(?:pon|marca|asigna|deja|dale)')
    patrones=[prioridad+r'\s+'+ART+OBJETO+r'\s+(.+?)\s+(?:como|con prioridad|en prioridad|prioridad)\s+'+VALOR,
              prioridad+r'\s+'+ART+r'(.+?)\s+'+OBJETO+r'\s+(?:como|con prioridad|en prioridad|prioridad)\s+'+VALOR,
              prioridad+r'\s+(?:como\s+)?'+VALOR+r'\s+'+ART+OBJETO+r'\s+(.+)',
              prioridad+r'\s+(?:la\s+)?prioridad\s+'+VALOR+r'\s+(?:a|al)\s+'+ART+OBJETO+r'\s+(.+)',
              prioridad+r'\s+en prioridad\s+'+VALOR+r'\s+'+ART+OBJETO+r'\s+(.+)']
    for i,patron in enumerate(patrones):
        m=re.fullmatch(patron,t,re.I)
        if m:
            s,v=(m[1],m[2]) if i<2 else (m[2],m[1]);v=N.normalizar(v)
            return _cambio('/prioridad',s,estado,prioridad={'urgente':'alta','importante':'alta'}.get(v,v))
    if re.fullmatch(prioridad+r'\s+(?:la\s+)?prioridad\s+(?:a|al)\s+'+ART+OBJETO+r'\s+.+',t,re.I):return _aclarar('prioridad')
    if re.fullmatch(cabecera+OBJETO+r'\s+.+',t,re.I):return _aclarar('texto')
    if re.fullmatch(r'(?:marca|pon|deja)\s+(?:esa|esta)\s+'+OBJETO+r'\s+como\s+'+ESTADO_HECHO,t,re.I):return _aclarar('numero')
    return None


def acceso(intencion):
    """Traducción al controlador existente; no pasa por un shell ni ejecuta."""
    if intencion is None or intencion.nombre=='aclarar':return None
    a=intencion.argumentos;n=intencion.nombre
    if n=='/tareas':return n+(' todas' if a.get('todas') else '')
    if n in {'/anotar','/buscar_tareas'}:return n+' '+a['texto']
    if n in {'/hecho','/reabrir'}:return n+' '+','.join(str(i) for i in a['numeros'])
    if n in {'/editar_tarea','/prioridad'}:return n+' '+str(a['numero'])+' '+a['texto' if n=='/editar_tarea' else 'prioridad']
    return None
