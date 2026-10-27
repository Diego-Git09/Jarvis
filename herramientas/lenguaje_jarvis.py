"""Interpreta solicitudes explícitas. El vocabulario no ejecuta ni autoriza acciones."""
import re
import shlex
import unicodedata
from dataclasses import dataclass, field

from cargar_vocabulario import cargar
VOCABULARIO = cargar('vocabulario.json')
ESTILO_USUARIO = cargar('estilo_usuario.json')
LITERAL_PATRON=r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|«[^»]*»|“[^”]*”|‘[^’]*’|`[^`]*`'''


def normalizar(texto):
    texto=''.join(c for c in unicodedata.normalize('NFD', texto.casefold()) if unicodedata.category(c) != 'Mn')
    # Abreviaturas de chat inequívocas; no corrige nombres ni palabras arbitrarias.
    for patron, reemplazo in ((r'\bq\b','que'),(r'\bxq\b','porque'),
                             (r'\btmb\b|\btb\b','tambien'),
                             (r'\bdnd\b','donde'),(r'\bpa\b','para')):
        texto=re.sub(patron,reemplazo,texto)
    return texto


def alternativas(lista):
    # Coincide con tildes o sin ellas, preservando los nombres capturados del usuario.
    patrones=[]
    for palabra in sorted(set(lista), key=len, reverse=True):
        patron=''
        for c in normalizar(palabra):
            patron += {'a':'[aá]', 'e':'[eé]', 'i':'[ií]', 'o':'[oó]', 'u':'[uúü]', 'n':'[nñ]', ' ':r'\s+'}.get(c,re.escape(c))
        patrones.append(patron)
    return '(?:'+'|'.join(patrones)+')'


@dataclass
class Intencion:
    nombre: str
    argumentos: dict = field(default_factory=dict)
    respuesta: str = ''


def limpiar_prefijos(texto):
    texto=texto.strip()
    vocativos='|'.join(re.escape(x).replace(r'\ ',r'\s+') for x in sorted(ESTILO_USUARIO['vocativos'],key=len,reverse=True))
    prefijos='|'.join(re.escape(x).replace(r'\ ',r'\s+') for x in sorted(ESTILO_USUARIO['prefijos'],key=len,reverse=True))
    cortesia=False
    for _ in range(8):
        texto=re.sub(r'^(?:(?:hola|wena|buenas)\s+)?(?:'+vocativos+r')[, ]+','',texto,flags=re.I)
        nuevo=re.sub(r'^(?:'+prefijos+r'|oye[, ]*)\s+','',texto,flags=re.I)
        if nuevo==texto:break
        cortesia=True
        texto=nuevo
    if cortesia:
        m=re.match(r'^(?:me\s+)?(\w+)\b',texto,re.I)
        if m and normalizar(m[1]) in ESTILO_USUARIO['verbos_peticion']:
            texto=ESTILO_USUARIO['verbos_peticion'][normalizar(m[1])]+texto[m.end():]
    m=re.match(r'^(\w+)\b',texto)
    if m and normalizar(m[1]) in ESTILO_USUARIO['acciones_con_tipeo']:
        texto=ESTILO_USUARIO['acciones_con_tipeo'][normalizar(m[1])]+texto[m.end():]
    return texto


def limpiar(texto):
    # La separación fuera de comillas no altera nombres ni rutas literales.
    partes=re.split('('+LITERAL_PATRON+')',texto.strip())
    texto=''.join(p if i%2 else re.sub(r'\s+',' ',p) for i,p in enumerate(partes)).strip(' ¿?¡!')
    texto=limpiar_prefijos(texto)
    marcador=re.search(r'\b(?:t[ií]tulo|nombre|texto|que diga|llamad[ao])(?=\s|[:=])',sin_literales(texto),re.I)
    if marcador:
        # El título explícito sin comillas conserva hasta su última palabra,
        # aunque sea «po» o «porfa». La cortesía dentro de un título no se borra.
        resto=texto[marcador.end():].lstrip(' :=')
        if resto and resto[0] not in {'"',"'",'«','“','‘','`'}:return texto.strip(' ¿?¡!')
    return re.sub(r'\s*,?\s+(?:por favor|porfa|porfis|po|poh)$','',texto,flags=re.I).strip(' ¿?¡!.')


def sin_literales(texto):
    """Oculta citas manteniendo posiciones; no altera la petición original."""
    return re.sub(LITERAL_PATRON,lambda m:' '*len(m[0]),texto)


def no_es_peticion(texto):
    """Ejemplos, hipótesis y negaciones no son accesos automáticos."""
    n=normalizar(sin_literales(limpiar(texto))).strip()
    if re.match(r'^el (?:comando|programa|ejemplo|documento|tutorial)\b',n):return True
    return bool(re.match(r'^(?:no\b|nunca\b|si\b|por ejemplo\b|ejemplo\b|como (?:ejemplo|si)\b|que significa\b|podria decirle\b|puedo decirte\b|me tinca\b|el (?:ejemplo|documento|tutorial) (?:dice|indica)\b|una hipotesis\b)',n)
                or re.search(r'\b(?:solo (?:un )?ejemplo|es (?:solo )?un ejemplo|no (?:crees|guardes|modifiques|elimines|borres|copies|muevas|compiles)\b)',n))


def confirmacion_conversacional(frase):
    """'aceptar'/'rechazar'/''; nunca es permiso de escritura o ejecución.

    El consumidor lo asocia a una propuesta del hilo. El diálogo técnico de
    autorización continúa usando su callback separado.
    """
    n=normalizar(limpiar(frase)).strip(' ,;')
    if re.search(r'["«“‘`]|\b(?:archivo|carpeta|ruta|contraseña|token|sudo|borra|elimina)\b',n):return ''
    datos=ESTILO_USUARIO.get('confirmaciones',{})
    for clase in ('rechazar','aceptar'):
        if n in {normalizar(x) for x in datos.get(clase,[])}:return clase
    for _ in range(4):
        nuevo=re.sub(r'(?:[, ]+)(?:porfa|por favor|altiro|po|compa)$','',n).strip(' ,;')
        if nuevo==n:break
        n=nuevo
    for clase in ('rechazar','aceptar'):
        if n in {normalizar(x) for x in datos.get(clase,[])}:return clase
    return ''


def _clave_acceso(frase):
    n=normalizar(limpiar(frase)).strip(' ,;')
    for _ in range(4):
        nuevo=re.sub(r'\s+(?:ahora|otra vez|de nuevo|altiro|al tiro|por favor|porfa)$','',n).strip(' ,;')
        if nuevo==n:break
        n=nuevo
    return n


def acceso_vocabulario(frase, estado=None):
    """str o None; traduce a comandos existentes sin ejecutar ni autorizarlos.

    El controlador conserva el original y vuelve a aplicar contratos, rutas y
    permisos propios del comando traducido.
    """
    if not isinstance(frase,str) or frase.lstrip().startswith('/') or no_es_peticion(frase):return None
    if isinstance(estado,dict) and estado.get('_entrenamiento_pendiente'):return None
    import lenguaje_tareas
    tarea=lenguaje_tareas.acceso(lenguaje_tareas.interpretar(frase,estado))
    if tarea:return tarea
    t=limpiar(frase);n=_clave_acceso(t)
    for acceso,variantes in VOCABULARIO.get('accesos_locales',{}).items():
        # Las variantes editables pasan por la misma limpieza de cortesía y
        # vocativos que la entrada; esa limpieza nunca toca sus argumentos.
        if n in {_clave_acceso(x) for x in variantes}:return acceso
    # Captura la ruta original. Nunca usa el texto normalizado como nombre.
    ruta='('+LITERAL_PATRON+r'|[^\s]+)'
    leer=re.fullmatch(ACCIONES['leer_archivo']+r'\s+(?:(?:el|la|un|una)\s+)?(?:archivo|fichero|documento|pdf|word|planilla|excel|ppt)\s+'+ruta,t,re.I)
    if leer:
        literal=leer[1];literal=literal[1:-1] if literal[:1] in {'"',"'",'`','«','“','‘'} else literal
        return '/leer '+shlex.quote(literal)
    adjuntar=re.fullmatch(ACCIONES.get('adjuntar',r'(?:adjunta|adjuntar)')+r'\s+(?:(?:el|la|un|una)\s+)?(?:(?:archivo|documento|pdf|word|planilla|excel|ppt|carpeta)\s+)?'+ruta,t,re.I)
    if adjuntar:
        literal=adjuntar[1];literal=literal[1:-1] if literal[:1] in {'"',"'",'`','«','“','‘'} else literal
        return '/adjuntar '+shlex.quote(literal)
    return None


ACCIONES={k:alternativas(v) for k,v in VOCABULARIO['acciones'].items()}
RECUERDOS=alternativas(VOCABULARIO['sustantivos']['recuerdos'])
PENDIENTES=alternativas(VOCABULARIO['sustantivos']['sin_clasificar'])
NUMEROS={normalizar(k):v for k,v in VOCABULARIO['numeros'].items()}
ORDINALES={normalizar(k):v for k,v in VOCABULARIO['ordinales'].items()}


def seleccion(texto, estado):
    texto=normalizar(texto).strip()
    texto=re.sub(r'^(?:los|las|mis|el|la)\s+','',texto)
    texto=re.sub(r'^(?:'+RECUERDOS+r')\s+','',texto)
    mapa=estado.get('_lista_memorias',{})
    excepcion=re.fullmatch(r'(?:todos|todas)(?: estos| estos recuerdos| los de esta pagina)? (?:menos|excepto|salvo) (.+)',texto)
    if excepcion:
        excluidos=seleccion(excepcion[1],estado)
        if not mapa or excluidos is None or any(n not in mapa for n in excluidos):
            return None
        return [n for n in mapa if n not in excluidos] or None
    if texto in {'todos','todas','todos estos','todos esos','estos','esos','todas estas','estos recuerdos','estos de aqui','todos los de esta pagina','los de esta pagina'}:
        return list(mapa) if mapa else None
    if texto in {'lo','este','ese','esto','eso','este recuerdo','ese recuerdo','esta memoria','esa memoria',
                 'esta conversacion','esa conversacion','este chat','ese chat','esta transcripcion','esa transcripcion'}:
        foco=estado.get('_recuerdo_en_foco')
        if foco in mapa:return [foco]
        return list(mapa) if len(mapa)==1 else None
    texto=re.sub(r'\s+(?:'+RECUERDOS+r')$','',texto)
    def numero(t):
        t=re.sub(r'^(?:el|la|los|las)\s+','',t.strip())
        if t in {'ultimo','ultima','mas nuevo','mas nueva','mas reciente'}:
            return list(mapa)[-1] if mapa else None
        if t in {'penultimo','penultima'}:
            return list(mapa)[-2] if len(mapa)>1 else None
        if t in ORDINALES:
            pagina=list(mapa)
            indice=ORDINALES[t]-1
            return pagina[indice] if 0 <= indice < len(pagina) else None
        return int(t) if t.isdigit() else NUMEROS.get(t)
    rango=re.fullmatch(r'(?:del?\s+)?(.+?)\s+(?:al?|hasta el|hasta)\s+(.+)',texto)
    if rango:
        a,b=numero(rango[1]),numero(rango[2])
        return list(range(a,b+1)) if a and b and 1<=a<=b<=50 else None
    partes=re.split(r'\s*(?:,|\by\b|\be\b)\s*',texto)
    valores=[numero(p) for p in partes]
    if valores and all(n is not None and 1<=n<=50 for n in valores):
        return list(dict.fromkeys(valores))
    return None


def proyecto(nombre, estado=None):
    nombre=nombre.strip().strip('«»"\'')
    conocidos={'jarvis':'Jarvis','segundo cerebro':'Segundo Cerebro','rutalimpia':'RutaLimpia','estudios':'estudios','personal':'personal','prueba':'Prueba','sin clasificar':'sin_clasificar','sin_clasificar':'sin_clasificar'}
    for p in (estado or {}).get('_proyectos_conocidos', []):
        conocidos[normalizar(p)] = p
    return conocidos.get(normalizar(nombre),nombre)


def interpretar(frase, estado):
    t=limpiar(frase);n=normalizar(t)
    if not t or t.startswith('/'):
        return None
    if no_es_peticion(t):return None
    # Las negaciones, explicaciones hipotéticas y pedidos de otras capacidades van a Qwen.
    if re.search(r'\b(?:no|nunca|no quiero|sin mover)\b',n) and not any(s in n for s in ('no clasificados','no clasificadas')):
        return None
    if re.fullmatch(ACCIONES['mostrar']+r'\s+(?:(?:mis|los|todos los)\s+)?proyectos',t,re.I):
        return Intencion('/proyectos')
    foco=re.fullmatch(r'(?:trabajemos en|trabaja en|usa el proyecto|usar el proyecto|cambia al proyecto|proyecto activo)\s+(?:el\s+)?(?:proyecto\s+)?(.+)',t,re.I)
    if foco:
        return Intencion('/proyecto',{'proyecto':proyecto(foco[1],estado)})
    if n in {'todos los proyectos otra vez','quita el filtro de proyecto','sin proyecto activo'}:
        return Intencion('/todos')
    for accion,nombre in [('anterior','/anterior'),('actualizar','/actualizar')]:
        if n in {normalizar(s) for s in VOCABULARIO['acciones'][accion]}:
            return Intencion(nombre)
    if n in {normalizar(s) for s in VOCABULARIO['acciones']['continuar']}:
        return Intencion('/mas')
    if n in {normalizar(s) for s in VOCABULARIO['acciones']['nuevo']}:
        return Intencion('/nuevo')
    if n in {normalizar(s) for s in VOCABULARIO['acciones']['salir']}:
        return Intencion('/salir')
    tamano=re.fullmatch(r'(?:muestra|mostrar|quiero ver)\s+(.+?)\s+recuerdos por pagina',n)
    if tamano:
        valor=int(tamano[1]) if tamano[1].isdigit() else NUMEROS.get(tamano[1])
        if valor is not None:
            return Intencion('/tamano',{'tamano':valor})
    if n in {'que hiciste','cual fue el ultimo cambio','muestra la ultima accion','ultimo resultado'}:
        return Intencion('/ultima_accion')
    pagina=re.fullmatch(r'(?:(?:ve a|ir a|muestra)\s+(?:la\s+)?)?pagina\s+(.+)',n)
    if pagina:
        valor=int(pagina[1]) if pagina[1].isdigit() else NUMEROS.get(pagina[1])
        if valor is not None:
            return Intencion('/pagina',{'pagina':valor})
    detalle=re.fullmatch('(?:'+ACCIONES['mostrar']+'|abre)'+r'\s+(?:(?:el|la)\s+)?(?:recuerdo|memoria)?\s*(.+?)\s+(?:completo|completa|con detalle|en detalle)',t,re.I)
    if detalle:
        nums=seleccion(detalle[1],estado)
        if nums is None or len(nums)!=1:
            return Intencion('aclarar',respuesta='Indica un número de la página visible para ver ese recuerdo completo.')
        return Intencion('ver_recuerdo',{'numero_recuerdo':nums[0]})
    if n in {'ayuda','que puedes hacer','que sabes hacer','como te uso','que comandos tienes'}:
        return Intencion('/ayuda')
    if n in {'como esta segundo cerebro','como va segundo cerebro','funciona segundo cerebro','estado de segundo cerebro','revisa el estado de segundo cerebro'}:
        return Intencion('/estado')
    ultimo = bool(re.search(r'\b(?:ultimo|ultima|mas reciente|mas nuevo|mas nueva|lo mas nuevo)\b', n))
    tema = bool(re.search(r'\b(?:recuerdos?|memorias?|anotaciones?|datos? guardados?)\b', n))
    referencia_guardado = bool(re.search(r'\b(?:lo ultimo|lo mas reciente|el ultimo registro|la ultima anotacion)\b', n))
    pide_mover_ultimo=ultimo and tema and bool(re.match(ACCIONES['clasificar']+r'\s',t,re.I))
    pide_orden=bool(re.search(r'\b(?:ordena|ordenar|ordenados?|ordenadas?|antiguo|antigua|viejo|vieja)\b',n))
    if ultimo and tema and not pide_mover_ultimo and not pide_orden:
        return Intencion('consultar_ultimo_recuerdo')
    ultima_conversacion = ultimo and bool(re.search(
        r'\b(?:conversacion|conversa|chat|dialogo|hable|converse|charle|escribi|dije|pregunte)\b', n))
    if ultima_conversacion:
        fuentes = {
            'claude_desktop': r'\bclaude(?:\s+desktop)?\b',
            'codex': r'\bcodex\b',
            'continue': r'\bcontinue\b',
            'openwebui': r'\bopen\s*webui\b',
            'jarvis': r'\bjarvis\b',
        }
        fuente = next((nombre for nombre, patron in fuentes.items() if re.search(patron, n)), '')
        return Intencion('consultar_ultima_conversacion', {'fuente': fuente} if fuente else {})
    if ultimo and referencia_guardado:
        return Intencion('consultar_ultimo_recuerdo')
    mov=re.fullmatch(ACCIONES['clasificar']+r'\s+(.+)\s+(?:en el|dentro del|dentro de|para el|al?|en)\s+(?:proyecto\s+)?(.+)',t,re.I)
    pronombre=re.fullmatch(r'(?:mu[eé]vel[oa]s?|clasif[ií]cal[oa]s?|agr[eé]gal[oa]s?|a[nñ][aá]del[oa]s?|p[aá]sal[oa]s?|trasl[aá]dal[oa]s?|ponl[oa]s?)\s+(?:en el|dentro del|dentro de|al?|en)\s+(?:proyecto\s+)?(.+)',t,re.I)
    if mov or pronombre:
        referencia=mov[1] if mov else ('todos estos' if re.search(r'los\s',normalizar(t)) else 'este')
        tipo_listado=estado.get('_tipo_ultimo_listado')
        if tipo_listado in {'archivos','tareas','proyectos'} and not re.search(r'\b(?:recuerdos?|memorias?|recueros?)\b',normalizar(referencia)):
            return Intencion('aclarar',respuesta='El último listado era de '+estado['_tipo_ultimo_listado']+'. Indica explícitamente qué recuerdos quieres clasificar o abre /recuerdos; no usaré esos números para mover otra cosa.')
        if tipo_listado=='conversaciones' and not re.search(r'\b(?:conversacion(?:es)?|chat(?:s)?|transcripcion(?:es)?)\b',normalizar(referencia)):
            return Intencion('aclarar',respuesta='El último resultado era una conversación. Indica explícitamente si quieres mover esa conversación, para no confundirla con un recuerdo breve.')
        destino=proyecto(mov[2] if mov else pronombre[1], estado)
        # No confundir dos órdenes con un nombre de proyecto.
        if re.search(r'\b(?:y luego|despues|pero|y mueve|y borra|y elimina)\b',normalizar(destino)):
            return None
        nums=seleccion(referencia,estado)
        if nums is None:
            return Intencion('aclarar',respuesta='Indica qué números del último listado quieres mover y a qué proyecto. «Todos» se refiere solo a la página visible.')
        return Intencion('clasificar_recuerdos',{'numeros':nums,'proyecto':destino})
    crear=re.fullmatch(ACCIONES['crear_proyecto']+r'\s+(?:un\s+|el\s+)?proyecto\s+(?:(?:llamado|con el nombre|que se llame)\s+)?(.+)',t,re.I)
    if crear:
        if re.search(r'\b(?:si no|si existe|y luego|despues|y mueve|y borra|y crea)\b',normalizar(crear[1])):
            return None
        return Intencion('crear_proyecto',{'proyecto':proyecto(crear[1], estado)})
    buscar=re.fullmatch(ACCIONES['buscar']+r'\s+(?:(?:los?|las?|mis)\s+)?'+RECUERDOS+r'\s+(?:sobre|de|acerca de|relacionados con|que mencionen|que mencionan)\s+(.+)',t,re.I)
    if buscar:
        if re.search(r'\b(?:y luego|despues|y mueve|y borra|y crea)\b',normalizar(buscar[1])):
            return None
        args={'consulta':buscar[1]}
        if estado.get('_proyecto_activo'):
            args['proyecto']=estado['_proyecto_activo']
        return Intencion('buscar_memoria',args)
    mostrar=re.fullmatch(ACCIONES['mostrar']+r'\s+(.+)',t,re.I)
    objeto=normalizar(mostrar[1]) if mostrar else n
    if objeto in {'los proyectos','mis proyectos','todos los proyectos','los proyectos de segundo cerebro','mis proyectos de segundo cerebro','que proyectos tengo','cuales son mis proyectos'}:
        return Intencion('/proyectos')
    original=mostrar[1] if mostrar else t
    verproyecto=re.fullmatch(r'(?:el\s+)?proyecto\s+(.+)',original,re.I)
    if mostrar and verproyecto:
        return Intencion('listar_memorias',{'proyecto':proyecto(verproyecto[1], estado)})
    if objeto in {'que tengo guardado','que cosas tengo guardadas','que recuerdas de mi','mis recuerdos','los recuerdos','todos los recuerdos','mis memorias','las memorias'}:
        return Intencion('/recuerdos')
    pendiente=re.fullmatch(r'(?:(?:los|las|mis)\s+)?(?:'+RECUERDOS+r'\s+)?'+PENDIENTES+r'(.*)',original,re.I)
    if pendiente:
        extra=normalizar(pendiente[1]).strip()
        orden='antiguos' if re.fullmatch(r'(?:ordenados )?(?:del )?mas antiguo al mas nuevo(?: \(por fecha\))?|(?:desde )?los mas antiguos(?: primero)?',extra) else 'recientes'
        if extra and orden=='recientes' and not re.fullmatch(r'(?:ordenados )?(?:del )?mas nuevo al mas antiguo(?: \(por fecha\))?|los mas nuevos(?: primero)?',extra):
            return None
        args={'proyecto':'sin_clasificar'}
        if extra:
            args['orden']=orden
        return Intencion('listar_memorias',args)
    return None


def resumen_vocabulario(pedido=None):
    """Orienta al modelo también en acciones que requieren argumentos complejos."""
    if pedido is not None:
        texto=normalizar(pedido)
        pertinentes=[f'{frase}: {significado}.' for frase,significado in VOCABULARIO.get('chileno',{}).get('expresiones',{}).items()
                     if re.search(r'(?<!\w)'+re.escape(normalizar(frase))+r'(?!\w)',texto)]
        return '\nGlosario pertinente (no concede permisos):\n'+'\n'.join(pertinentes[:12]) if pertinentes else ''
    acciones = "\nVocabulario de intenciones (los sinónimos no autorizan cambios):\n" + "\n".join(
        f"{nombre}: {', '.join(palabras)}." for nombre,palabras in VOCABULARIO['acciones'].items()
        if nombre in {'leer_archivo','editar_archivo','revertir','olvidar_memoria','buscar','clasificar'})
    chileno = VOCABULARIO.get('chileno', {})
    expresiones = chileno.get('expresiones', {})
    glosario = "\nGlosario chileno (el significado puede depender del contexto; pregunta si cambia la acción):\n" + "\n".join(
        f"{frase}: {significado}." for frase, significado in expresiones.items())
    glosario += "\nVariantes de intención: " + "; ".join(
        f"{concepto}: {', '.join(variantes)}" for concepto, variantes in chileno.get('formas', {}).items())
    glosario += "\nEl habla informal, los modismos y las faltas de ortografía no conceden permisos ni completan por sí solos un objeto ambiguo."
    glosario += " Si aparece una expresión desconocida o escrita de forma ambigua, no inventes su significado: pregunta qué quiso decir el usuario. Corrige mentalmente errores tipográficos solo cuando la intención sea inequívoca."
    return acciones + glosario


def definir_expresion(pedido):
    """Explica términos del glosario cuando se pregunta por su significado."""
    texto=normalizar(pedido)
    if not re.search(r'\b(?:que significa|que quiere decir|significado|explicame (?:la palabra|la expresion))\b',texto):
        return ''
    conocidos=VOCABULARIO.get('chileno',{}).get('expresiones',{})
    candidatos=[(frase,significado) for frase,significado in conocidos.items()
                if re.search(r'(?<!\w)'+re.escape(normalizar(frase))+r'(?!\w)',texto)]
    unicos={normalizar(frase):(frase,significado) for frase,significado in reversed(candidatos)}
    if len(unicos)!=1:
        return ''
    frase,significado=next(iter(unicos.values()))
    return f'«{frase}»: {significado}. El sentido concreto depende de la frase en que lo uses.'

def detectar_correccion_usuario(texto_norm):
    """Detecta si el usuario está notificando un error de interpretación previo."""
    patrones_correccion = [
        "no significa eso",
        "eso no significa",
        "no quise decir",
        "no he puesto",
        "no puse",
        "te equivocaste",
        "no es lo que pedi",
        "entendiste mal"
    ]
    return any(patron in texto_norm for patron in patrones_correccion)
def detectar_error(texto_norm):
    """Detecta si el usuario está notificando un error de interpretación previo."""
    patrones_error = [
        "no entendí",
        "no puedo",
        "no puedo hacer",
        "no puedo hacer eso"
    ]
    return any(patron in texto_norm for patron in patrones_error)
