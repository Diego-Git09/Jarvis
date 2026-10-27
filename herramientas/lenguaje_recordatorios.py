"""Peticiones de escritorio con datos explícitos y fechas separadas del evento."""
import re
import unicodedata
from lenguaje_jarvis import limpiar,normalizar,alternativas,VOCABULARIO,no_es_peticion,sin_literales
from fechas_naturales import NUMERO,numero
import recordatorios_jarvis as R

OBJETO=alternativas(VOCABULARIO.get('sustantivos',{}).get('recordatorios',['recordatorio','recordatorios','aviso','avisos','nota de escritorio']))
DIAS=r'(?:hoy|ma[nñ]ana|m[nñ]n|pasadoma[nñ]ana|(?:pasado|pasao) ma[nñ]ana|(?:este |pr[oó]ximo )?(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo))'
FECHA=r'(?:(?:para|desde|el|d[ií]a|a partir de)\s+)*(?:'+DIAS+r'|\d{1,2}[/-]\d{1,2}(?:[/-]\d{4})?|\d{4}-\d{2}-\d{2}|'+NUMERO+r' de (?:'+'|'.join(R.MESES)+r')(?: (?:de |del )?\d{4})?|(?:en|dentro de)\s+'+NUMERO+r'\s+(?:minutos?|horas?|d[ií]as?|semanas?))(?:\s+(?:a las?\s+)?'+NUMERO+r'(?::\d{2})?(?:\s+(?:y media|y cuarto|menos cuarto))?(?:\s*(?:am|pm|de la ma[nñ]ana|de la tarde|de la noche))?|\s+(?:a mediod[ií]a|a medianoche|todo el d[ií]a|(?:en|por) la ma[nñ]ana|(?:en|por) la tarde|(?:en|por) la noche))?'
CREAR=alternativas(VOCABULARIO.get('acciones',{}).get('recordatorio_crear',['crea','haz','anota','pon','deja','genera','arma']))
LISTAR=alternativas(VOCABULARIO.get('acciones',{}).get('recordatorio_listar',['muestra','muéstrame','lista','enséñame','dime','ver']))


def sin_citas(texto):
    return sin_literales(texto)


def forma(texto):
    # Una posición por carácter para recortar el texto original sin tocar títulos.
    return ''.join(unicodedata.normalize('NFD',c.lower())[0] for c in texto)


def compuesta(p):
    n=normalizar(sin_citas(p))
    n=re.sub(r'\by(?: tambien)?\s+(?:avisame|recuerdame)\s+'+NUMERO+r'\s+(?:dias?|semanas?|horas?|minutos?)\s+antes\b','',n)
    return bool(re.search(r'\b(?:y(?: tambien)?|luego|despues)\s+(?:busca|consulta|lee|edita|modifica|crea|elimina|borra|clasifica|recuerdame|avisame|mueve|copia)\b',n))


def no_es_orden(p):
    n=normalizar(sin_citas(limpiar(p)))
    return no_es_peticion(p) or bool(re.search(r'\b(?:solo (?:un )?ejemplo|es (?:solo )?un ejemplo|no (?:crees|guardes|modifiques|elimines|borres) nada)\b',n))


def dominio(p):
    n=normalizar(sin_citas(limpiar(p)))
    return bool(re.search(r'\b(?:recordatorios?|recoratorios?|recodatorios?|recuerdame|recordarme|avisame|avisarme|post[- ]?it)\b',n) or
                re.search(r'\b(?:escritorio|desktop|nota flotante)\b',n) and re.search(r'\b(?:antes|avis[ae]|examen|prueba|evento|cita|visible|aparezca)\b',n))


def separar_fecha(texto):
    mascara=sin_citas(texto)
    separador=mascara.rfind('|')
    if separador>=0:
        return texto[:separador].strip(),texto[separador+1:].strip()
    m=re.search(r'\s+('+FECHA+r'|siempre|permanente|todo el tiempo)$',mascara,re.I)
    if m:return texto[:m.start(1)].strip(' ,;'),texto[m.start(1):m.end(1)].strip()
    return texto.strip(),'siempre'


def quitar_citas(texto):
    texto=texto.strip()
    pares={'"':'"',"'":"'",'«':'»','“':'”','‘':'’','`':'`'}
    return texto[1:-1] if len(texto)>=2 and texto[0] in pares and texto[-1]==pares[texto[0]] else texto


def fecha_al_comienzo(texto):
    """Fecha seguida de separador/título explícito; posiciones del original."""
    # Solo se reconoce el prefijo. Ocultar la cita del título la volvía espacios
    # y el antiguo grupo (.+) terminaba capturando únicamente la comilla final.
    mascara=forma(texto)
    marcador=r'(?:(?:y\s+)?(?:dejalo|dejala|ponlo|ponla|dejame|ponle)\s+(?:con\s+)?(?:el\s+)?(?:titulo|nombre|texto)|(?:con\s+)?(?:el\s+)?(?:titulo|nombre)|(?:que\s+)?diga|llamado|llamada)\s*[:=]?\s+'
    m=re.match(r'^('+FECHA+r'|siempre|permanente|todo el tiempo)\s*(?:[,;]\s*|\s+'+marcador+r')',mascara,re.I)
    if m:return texto[m.end():].strip(' ,;'),texto[m.start(1):m.end(1)].strip()
    return None


def limpiar_cola_aviso(texto):
    mascara=forma(sin_citas(texto))
    m=re.search(r'(?<!\w)\s*(?:[,;]\s*|\s+(?:y(?: que)?|que|para que)\s+)?(?:(?:y|me|lo|la|se|que|empiece|empieza|empieces|comience|comienza|quiero|pueda|a)\s+)*(?:aparecer|aparezca|apareciendo|muestre|mostrar|mostrarse|verse|vea|verlo|avisame|avisa|avise|avisar|avises|recuerdame|recordar)\b.*$',mascara)
    return texto[:m.start()].strip(' ,;') if m else texto.strip(' ,;')


def plan_creacion(cuerpo):
    mascara=forma(sin_citas(cuerpo));args={};resto=cuerpo
    antic=re.search(r'\b(?:con\s+)?('+NUMERO+r')\s+(?:de\s+)?(dias?|semanas?|horas?|minutos?)\s+(?:antes|de anticipacion)(?:\s+.*)?$',mascara)
    if antic:
        cantidad=numero(antic[1]);unidad=antic[2]
        campo='anticipacion_minutos' if unidad.startswith(('hora','minuto')) else 'anticipacion_dias'
        args[campo]=cantidad*(60 if unidad.startswith('hora') else 7 if unidad.startswith('semana') else 1)
        resto=limpiar_cola_aviso(cuerpo[:antic.start()])
    hasta=re.search(r'\s+(?:y\s+)?(?:que\s+)?(?:se\s+)?(?:muestre\s+)?hasta\s+('+FECHA+r')$',sin_citas(resto),re.I)
    if hasta:args['mostrar_hasta']=resto[hasta.start(1):hasta.end(1)];resto=resto[:hasta.start()].strip(' ,;')
    if re.fullmatch(FECHA+r'|siempre|permanente|todo el tiempo',resto.strip(),re.I):
        return {'nombre':'aclarar','respuesta':'¿Qué texto quieres poner en el recordatorio? La fecha sola no indica qué debo recordar.'}
    inicial=fecha_al_comienzo(resto)
    texto,fecha=inicial if inicial else separar_fecha(resto)
    if re.search(r'\b(?:en|por) la (?:manana|tarde|noche)\b',normalizar(fecha)):
        return {'nombre':'aclarar','respuesta':'¿A qué hora concreta quieres que aparezca? No elegí una hora para ese periodo.','borrador':dict(args,texto=quitar_citas(texto))}
    if re.search(r'\bsin decidir (?:la hora|el titulo)\b',normalizar(sin_citas(texto))):
        return {'nombre':'aclarar','respuesta':'¿Qué título y hora concretos quieres para el recordatorio? No lo creé.'}
    if args.get('anticipacion_dias') is not None or args.get('anticipacion_minutos') is not None:
        if fecha=='siempre':
            titulo=re.split(r'\s+(?:para el d[ií]a|el d[ií]a|para alguna fecha)\b',texto,maxsplit=1,flags=re.I)[0]
            return {'nombre':'aclarar','respuesta':'¿Qué día y hora es el evento? Necesito esa fecha para empezar a mostrarlo antes. Sin hora explícita usaré 09:00 de Chile.','borrador':dict(args,texto=titulo)}
        args['evento']=fecha
    else:args['fecha']=fecha
    if not texto or normalizar(texto) in {'de','para','sobre','un','una'}:
        return {'nombre':'aclarar','respuesta':'¿Qué texto quieres poner en el recordatorio? No lo creé todavía.'}
    # Un marcador de fecha sin fecha reconocible no se convierte en nota permanente.
    if fecha=='siempre' and re.search(r'\b(?:para el dia|el dia|fecha de|algun dia|dia tanto|mas adelante|en un rato|hoy|manana+|mananna|pasadomanana|lunes|martes|miercoles|jueves|viernes|sabado|domingo|a las?\s+\d|(?:en|dentro de)\s+\d+\s+(?:horas?|dias?|minutos?))\b',normalizar(sin_citas(texto))):
        titulo=re.split(r'\s+(?:para el d[ií]a|el d[ií]a|para alguna fecha|en un rato)\b',texto,maxsplit=1,flags=re.I)[0]
        return {'nombre':'aclarar','respuesta':'Necesito una fecha concreta para ese recordatorio. Por ejemplo: «20 de octubre a las 09:00». No elegí una fecha por suposición.','borrador':dict(args,texto=titulo)}
    args['texto']=quitar_citas(texto)
    return {'nombre':'crear_recordatorio','argumentos':args}


def interpretar(pregunta):
    p=limpiar(pregunta);n=normalizar(p)
    p=re.sub(r'^(?:socio|compa|compadre|mi rey),\s*','',p,flags=re.I)
    p=re.sub(r'^\w+',lambda m:normalizar(m[0]),p,count=1)
    if compuesta(p) or no_es_orden(p):return None
    if re.search(r'\b(?:pero|y)\s+no\s+(?:me\s+)?(?:avises|muestres|muestr[ea]|recuerdes|avisar)\b',n):return None
    corta=interpretar_referencia(p)
    if corta:return corta
    lista=re.sub(r'\s+(?:ahora|otra vez|de nuevo|altiro|por favor)$','',p,flags=re.I)
    if re.fullmatch(LISTAR+r'\s+(?:todos\s+|todas\s+)?(?:los\s+|las\s+|mis\s+)?'+OBJETO+r'(?: de escritorio)?',lista,re.I) or re.fullmatch(r'(?:dime\s+)?(?:qu[eé]|cu[aá]les son mis)\s+recordatorios\s+tengo',lista,re.I) or re.fullmatch(LISTAR+r'\s+(?:qu[eé]|cu[aá]les son mis)\s+recordatorios(?: tengo)?',lista,re.I):
        return {'nombre':'listar_recordatorios','argumentos':{}}
    # Esta forma expresa una descripción junto con una petición explícita.
    aviso=re.fullmatch(r'(?:tengo|tendre)\s+(.+?)\s*[,;]\s*(?:avisame|recu[eé]rdame)\s+(.+)',p,re.I)
    if aviso:return plan_creacion(aviso[1]+' avísame '+aviso[2])
    relato=re.fullmatch(r'(?:tengo|tendr[eé])\s+(.+?)[.;,]\s*[¿]?\s*(?:me (?:dejai|dejas|podi dejar)|puedes dejarme|podr[ií]as dejarme)\s+(?:algo|una (?:nota|notita))\s+en\s+(?:el |mi )?(?:escritorio|desktop|pantalla)\s+(?:que\s+)?(.+)',p,re.I)
    if relato:return plan_creacion(relato[1]+' '+relato[2])
    # «Recordatorio para mañana... título...» es una petición con los datos,
    # aunque no incluya verbo. La forma singular sola no crea una nota vacía.
    desnudo=re.fullmatch(r'(?:recordatorio|aviso)\s+(.+)',p,re.I|re.S)
    if desnudo and re.match(r'^(?:para|desde|el|hoy|ma[nñ]ana|siempre|con el titulo)\b',desnudo[1],re.I):return plan_creacion(desnudo[1])
    crear=re.fullmatch(r'(?:/recordar|recu[eé]rdame|recordarme|recordame|recordar|av[ií]same|avisarme|ag[eé]ndame|acu[eé]rdame|'+CREAR+r'\s+(?:un\s+|una\s+)?'+OBJETO+r'(?:\s+(?:de|sobre))?)\s+(.+)',p,re.I|re.S)
    if crear:
        # «Agéndame un recordatorio de X» y «agéndame X» comparten verbo.
        # El descriptor solo se quita al inicio fuera de las citas del título.
        cuerpo=re.sub(r'^(?:un\s+|una\s+)'+OBJETO+r'\s+(?:(?:de|sobre)\s+)?','',crear[1],flags=re.I)
        return plan_creacion(cuerpo)
    cambio_anticipacion=re.fullmatch(r'(?:avisa|avisame|muestra|muestrame|deja|pon|haz que aparezca)\s+(?:el\s+)?'+OBJETO+r'\s+('+NUMERO+r')\s+('+NUMERO+r')\s+(dias?|semanas?|horas?|minutos?)\s+antes',n)
    if cambio_anticipacion:return {'nombre':'modificar_recordatorio','argumentos':{'numero':numero(cambio_anticipacion[1]),('anticipacion_minutos' if cambio_anticipacion[3].startswith(('hora','minuto')) else 'anticipacion_dias'):numero(cambio_anticipacion[2])*(60 if cambio_anticipacion[3].startswith('hora') else 7 if cambio_anticipacion[3].startswith('semana') else 1)}}
    nuevo_evento=re.fullmatch(r'(?:cambia|modifica|reprograma|mueve)\s+(?:la\s+)?(?:fecha del evento|fecha de la prueba|evento|prueba)\s+(?:del?\s+)?'+OBJETO+r'\s+('+NUMERO+r')\s+(?:a|para|al)\s+(.+)',p,re.I)
    if nuevo_evento:return {'nombre':'modificar_recordatorio','argumentos':{'numero':numero(nuevo_evento[1]),'evento':nuevo_evento[2]}}
    modificar=re.fullmatch(r'(?:edita|editar|editame|modifica|modificar|modificame|cambia|cambiar|cambiame|corrige)\s+(?:el\s+)?'+OBJETO+r'\s+('+NUMERO+r')\s+(?:(?:para que diga|que diga|a|por|para)\s+)?(.+)',p,re.I|re.S)
    if modificar:
        texto,fecha=separar_fecha(modificar[2]);args={'numero':numero(modificar[1]),'texto':quitar_citas(texto)}
        if fecha!='siempre' or re.search(r'(?:siempre|permanente|todo el tiempo)$',modificar[2],re.I):args['fecha']=fecha
        return {'nombre':'modificar_recordatorio','argumentos':args}
    quitar=re.fullmatch(r'(?:elimina|eliminar|eliminame|borra|borrar|borrame|quita|quitar|quitame|saca|sacame)\s+(?:el\s+)?'+OBJETO+r'\s+('+NUMERO+r')',p,re.I)
    if quitar:return {'nombre':'eliminar_recordatorio','argumentos':{'numero':numero(quitar[1])}}
    posponer=re.fullmatch(r'(?:pospon|pospone|posponer|postergame|posterga|postergar|reprograma|mueve|muestra|muestrame|pon|deja)\s+(?:el\s+)?'+OBJETO+r'\s+('+NUMERO+r')\s+(?:(?:para|al|desde)\s+)?(.+)',p,re.I)
    if posponer:return {'nombre':'modificar_recordatorio','argumentos':{'numero':numero(posponer[1]),'fecha':posponer[2]}}
    hecho=re.fullmatch(r'(?:completa|completar|termina|terminar|marca como hecho|da por terminado)\s+(?:el\s+)?'+OBJETO+r'\s+('+NUMERO+r')',p,re.I)
    if hecho:return {'nombre':'modificar_recordatorio','argumentos':{'numero':numero(hecho[1]),'estado':'hecho'}}
    referencia=re.fullmatch(r'(?:elimina|borra|quita|saca)\s+(?:el\s+)?'+OBJETO+r'\s+(?:de\s+|que dice\s+|llamado\s+)(.+)',p,re.I)
    if referencia:return {'nombre':'eliminar_recordatorio','argumentos':{'referencia':referencia[1].strip('«»"')}}
    return interpretar_referencia(p)


def interpretar_referencia(p):
    n=normalizar(p)
    if n in {'ponlo siempre','dejalo siempre','muestralo siempre','que aparezca siempre','que se vea siempre','siempre visible','ponlo permanente'}:
        return {'nombre':'modificar_recordatorio','argumentos':{'fecha':'siempre'},'referencia_corta':True}
    if n in {'borralo','quitalo','eliminalo','sacalo'}:
        return {'nombre':'eliminar_recordatorio','argumentos':{},'referencia_corta':True}
    if n in {'ya lo hice','ya esta hecho','marcalo como hecho','dalo por terminado','completalo'}:
        return {'nombre':'modificar_recordatorio','argumentos':{'estado':'hecho'},'referencia_corta':True}
    antic=re.fullmatch(r'(?:avisame|avisa|recuerdame|muestralo|haz que aparezca|que aparezca)\s+('+NUMERO+r')\s+(dias?|semanas?|horas?|minutos?)\s+antes(?: de (?:la prueba|el evento|la fecha))?',n)
    if antic:return {'nombre':'modificar_recordatorio','argumentos':{('anticipacion_minutos' if antic[2].startswith(('hora','minuto')) else 'anticipacion_dias'):numero(antic[1])*(60 if antic[2].startswith('hora') else 7 if antic[2].startswith('semana') else 1)},'referencia_corta':True}
    fecha=re.fullmatch(r'(?:cambialo|ponlo|pasalo|postergalo|posponlo|dejalo|muestralo)\s+(?:para|al|desde)\s+(.+)',p,re.I)
    if fecha:return {'nombre':'modificar_recordatorio','argumentos':{'fecha':fecha[1]},'referencia_corta':True,'fecha_ambigua':n.startswith(('cambialo','pasalo'))}
    texto=re.fullmatch(r'(?:que diga|cambia el texto a|ponle de texto)\s+(.+)',p,re.I)
    if texto:return {'nombre':'modificar_recordatorio','argumentos':{'texto':texto[1].strip('«»"')},'referencia_corta':True}
    return None
