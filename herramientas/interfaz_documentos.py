"""Rutas pegadas, carpeta consultada y lectura documental sin depender de Qwen."""
import re
from pathlib import Path
from lenguaje_jarvis import limpiar_prefijos,normalizar
import herramientas_lectura as L
from documentos_jarvis import firma


def quitar_comillas(texto):
    t=texto.strip()
    if len(t)>1 and (t[0],t[-1]) in {('`','`'),('"','"'),("'","'"),('«','»')}:
        return t[1:-1]
    return t


def ruta_sola(texto):
    t=quitar_comillas(texto)
    return t if '\n' not in t and (t.startswith('~/') or re.match(r'^/[^/\s]+/',t) or t=='/' or t.startswith('/') and ' ' not in t and Path(t).exists()) else None


def resolver_referencia(ruta,estado):
    import adjuntos_jarvis
    adjunto=adjuntos_jarvis.resolver_adjunto(ruta,estado)
    if adjunto:return adjunto
    t=quitar_comillas(ruta);p=Path(t).expanduser()
    if not p.is_absolute() and len(p.parts)==1:
        listado=estado.get('_archivos_listado',{})
        if any(x.get('nombre')==t and x.get('tipo') in {'archivo','carpeta'} for x in listado.get('items',[])):
            carpeta=L._resolver(listado['ruta']);t=str(carpeta/t)
    return t


def recordar_resultado(nombre,r,estado):
    if not r.get('ok') or nombre not in {'listar_archivos','leer_documento','leer_archivo','leer_lineas','informacion_archivo','comparar_archivos','encontrar_archivos','buscar_texto'}:return
    if nombre=='listar_archivos':
        estado['_archivos_listado']={'ruta':r['ruta'],'items':r.get('items',[])}
    if nombre in {'leer_documento','leer_archivo','leer_lineas'}:
        estado['_archivo_foco']=r['ruta']
        estado.pop('_documento_tramo',None)
        if 'siguiente_documento' in r:
            estado['_documento_tramo']={'ruta':r['ruta'],'siguiente':r['siguiente_documento'],'firma':r['firma']}
    estado['_tipo_ultimo_listado']='archivos'


def presentar(r):
    if not r.get('ok'):return r.get('error','No pude leer el documento.')
    if 'siguiente_documento' not in r:
        from interfaz_archivos import renderizar_archivos
        return renderizar_archivos('leer_lineas',r)
    encabezado=f"{r['ruta']} · "+(f"página {r['inicio']} de {r['total_paginas']}" if r.get('total_paginas') else 'texto extraído')
    if r.get('offset'):encabezado+=f" · continuación desde el carácter {r['offset']}"
    texto=r.get('contenido','')
    fin='Escribe /mas_documento o «continúa leyendo» para el siguiente tramo.' if r['siguiente_documento'] else 'Fin del documento.'
    return encabezado+'\n\n'+texto+'\n\n'+(r['aviso']+'\n' if r.get('aviso') else '')+fin


def _carpeta_personal(nombre):
    n=normalizar(quitar_comillas(nombre))
    aliases={'downloads':['Downloads'],'descargas':['Downloads','Descargas'],'documentos':['Documents','Documentos'],'escritorio':['Desktop','Escritorio']}
    candidatas=aliases.get(n,[quitar_comillas(nombre)])
    for nombre in candidatas:
        p=Path.home()/nombre
        if p.is_dir():return str(p)
    return None


def comando(pregunta,historial,estado,ejecutar):
    t=limpiar_prefijos(pregunta.strip());n=normalizar(t).strip(' ¿?¡!')
    siguiente=n in {'/mas_documento','continua leyendo','sigue leyendo','lee la siguiente pagina','muestra la siguiente pagina','siguiente parte del documento'}
    if n in {'esa es la ruta','te estoy pasando la ruta','esa es la ruta del archivo'} and estado.get('_archivo_foco'):
        texto='La ruta consultada es '+estado['_archivo_foco']+'. El contenido leído aparece arriba; /mas_documento continúa si quedan tramos.'
        historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}]);return True,texto
    if siguiente:
        actual=estado.get('_documento_tramo')
        if not actual:return True,'Primero abre un documento con /leer RUTA.'
        if not actual['siguiente']:return True,'Ya llegaste al final del documento.'
        try:
            if firma(L._resolver(actual['ruta']))!=actual['firma']:
                estado.pop('_documento_tramo',None);return True,'El documento cambió desde el último tramo. Vuelve a leerlo desde el inicio.'
        except (OSError,L.FueraDeAlcance) as e:return True,str(e)
        nombre,args='leer_documento',{'ruta':actual['ruta'],**actual['siguiente']}
    else:
        ruta=ruta_sola(t)
        leer=re.fullmatch(r'(?:lee|leer|leeme|léeme|abre|abrir|muestra|muéstrame)\s+(?:(?:el|ese|este)\s+)?(?:(?:archivo|documento|pdf)\s+)?(?:por (?:partes|tramos)\s+)?(.+)',t,re.I)
        inverso=re.fullmatch(r'(.+?)\s+(?:lee ese|lee ese archivo|leelo|léelo)',t,re.I)
        carpeta=re.fullmatch(r'(?:ir|ve|accede|entra|abre|abrir|lista|listar|listarme|muestra|muestrame)\s+(?:a\s+)?(?:(?:la|el)\s+)?(?:ruta|carpeta|directorio)\s+(.+?)(?:\s+del pc)?',n)
        listar_referencia=bool(re.fullmatch(r'(?:lista|listar|listarme|muestra|muestrame) (?:los )?archivos (?:que contiene|de|en) (?:esa|esta|la) carpeta',n))
        if listar_referencia:
            listado=estado.get('_archivos_listado')
            if not listado:return True,'¿Qué carpeta quieres listar? Puedes pegar su ruta completa.'
            nombre,args='listar_archivos',{'ruta':listado['ruta']}
        elif carpeta:
            destino=_carpeta_personal(carpeta[1]) or ruta_sola(carpeta[1])
            if not destino:return False,''
            nombre,args='listar_archivos',{'ruta':destino}
        elif ruta or leer or inverso:
            candidata=ruta or quitar_comillas((leer or inverso)[1])
            import adjuntos_jarvis
            try:referencia=adjuntos_jarvis.resolver_adjunto(candidata,estado)
            except ValueError as e:return True,str(e)
            if referencia:candidata=referencia
            if not ruta and re.match(r'^(?:y |luego |después |resume |resumir |explica |explicar )',candidata,re.I):return False,''
            if not ruta and candidata in {'ese','eso','ese archivo','el archivo','ese documento'}:
                candidata=estado.get('_archivo_foco','')
                if not candidata:return True,'¿Qué archivo quieres leer? Pega la ruta completa.'
            # Solo se consumen lecturas con una ruta/nombre de archivo. Una frase
            # como «muestra mis recuerdos» sigue hacia su intérprete habitual.
            if not ruta and not (Path(candidata).suffix or candidata.startswith(('~/','/'))):return False,''
            candidata=resolver_referencia(candidata,estado)
            if ruta:
                try:es_carpeta=L._resolver(candidata).is_dir()
                except L.FueraDeAlcance as e:return True,'Fuera de alcance: '+str(e)
                if es_carpeta:nombre,args='listar_archivos',{'ruta':candidata}
                else:nombre,args='leer_lineas',{'ruta':candidata}
            else:nombre,args='leer_lineas',{'ruta':candidata}
        else:return False,''
    r=ejecutar(nombre,args);recordar_resultado(nombre,r,estado)
    if nombre=='listar_archivos':
        from interfaz_archivos import renderizar_archivos
        texto=renderizar_archivos(nombre,r)
    else:texto=presentar(r)
    historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}])
    return True,texto
