"""Clasificación explicable de intenciones; no concede permisos ni ejecuta."""
import re
from normalizacion_entrada import vista

REGLAS=[
 ('cancelar',r'^(?:no|nop|mejor no|para|detente|cancela|cancelar|dejalo|olvidalo|espera|no todavia|eso no|otra cosa|filo)$'),
 ('saludo',r'^(?:hola|wena|buenas|buenos dias|buenas tardes|buenas noches)(?: jarvis| po)?$'),
 ('despedida',r'^(?:adios|chao|hasta luego|hasta manana|nos vemos|salir)$'),
 ('gracias',r'^(?:muchas )?gracias(?: jarvis| por todo)?$'),
 ('deshacer',r'\b(?:deshacer|deshaz|revierte|revertir)\b'),
 ('reintentar',r'\b(?:reintenta|reintentar|intenta de nuevo|prueba otra vez)\b'),
 ('continuar',r'^(?:continua|continuar|sigue|sigamos|empecemos|empecemos con el 1|si te confirmo empecemos|que sigue|y ahora)$'),
 ('ayuda',r'^(?:ayuda|ayudame|que puedes hacer|que comandos tienes)$'),
 ('cerebro_estado',r'\b(?:estado|funciona|funcionando|conexion)\b.*\b(?:segundo cerebro|cerebro)\b|\b(?:segundo cerebro|cerebro)\b.*\b(?:estado|funciona|funcionando|conexion)\b'),
 ('cerebro_proyectos',r'\bproyectos\b.*\b(?:cerebro|registrados|tengo)\b|\b(?:muestra|muestrame|lista|dime)\b.*\bproyectos\b'),
 ('cerebro_guardar',r'\b(?:guarda|guardar|recuerda|anota)\b.*\b(?:recuerdo|memoria|cerebro)\b'),
 ('cerebro_corregir',r'\b(?:corrige|corregir|modifica|modificar|edita)\b.*\b(?:recuerdo|memoria)\b'),
 ('cerebro_olvidar',r'\b(?:olvida|olvidar|borra|borrar|elimina|eliminar)\b.*\b(?:recuerdo|memoria)\b'),
 ('cerebro_buscar',r'\b(?:busca|buscar|encuentra|consulta|muestra|muestrame)\b.*\b(?:recuerdos|memorias|cerebro)\b'),
 ('diagnostico',r'\b(?:diagnostico|diagnostica|diagnosticar)\b.*\b(?:jarvis|ollama|equipo)\b|^diagnostico$'),
 ('jarvis_estado',r'\b(?:estado|funcionas|funcionando)\b.*\bjarvis\b|\bjarvis\b.*\bestado\b'),
 ('modelo',r'\b(?:modelo|modelos)\b.*\b(?:cambia|cambiar|automatico|automatica|usa|usar|qwen|deepseek)\b|\b(?:cambia|cambiar|usa|usar)\b.*\b(?:modelo|qwen|deepseek)\b'),
 ('gpu_liberar',r'\b(?:libera|liberar|descarga|descargar)\b.*\b(?:gpu|vram|modelo|modelos)\b'),
 ('adjuntar',r'\b(?:adjunta|adjuntar|anexa|anexar)\b'),
 ('clima',r'\b(?:clima|tiempo en|temperatura en|llovera|llueve|pronostico)\b'),
 ('precio',r'\b(?:cuanto cuesta|precio|precios|valor de|cotiza|cotizar)\b'),
 ('internet',r'\b(?:internet|web|en linea|online)\b.*\b(?:busca|buscar|consulta|consulta)\b|\b(?:busca|buscar|consulta|consultar)\b.*\b(?:internet|web|en linea|online)\b'),
 ('corregir_codigo',r'\b(?:corrige|corregir|depura|depurar|arregla|arreglar)\b.*\b(?:codigo|python|java|kotlin|sql|funcion|script)\b'),
 ('pruebas',r'\b(?:corre|correr|ejecuta|ejecutar|haz|hazme)\b.*\b(?:pruebas|tests|test)\b|\b(?:prueba|testea)\b.*\bcodigo\b'),
 ('guia',r'\b(?:guia|paso a paso|tutorial|instructivo|por donde empiezo)\b'),
 ('comparar',r'\b(?:compara|comparar|diferencia|diferencias|ventajas y desventajas)\b'),
 ('recomendar',r'\b(?:recomienda|recomendar|recomiendas|conviene|vale la pena)\b'),
 ('resumir',r'\b(?:resume|resumir|resumen|resumelo)\b'),
 ('explicar',r'\b(?:explica|explicar|explicame|explicamelo|que significa|que es|como funciona|ensename)\b'),
 ('queja',r'\b(?:no cambio|no funciona|no pasa nada|se quedo pegad[oa]|se estanco|volvio a bajar|todo me sale igual|no entiendo|respuesta incompleta|malos|se cuelga|se congela|se trabo|se cayo|me tira error|me sale esto|no me deja|va lento|se demora|sigue igual|esta raro|esta pesimo|esta penca)\b'),
 ('renombrar',r'\b(?:renombra|renombrar|renombralo|cambia el nombre)\b'),
 ('copiar',r'\b(?:copia|copiar|copialo|duplica|duplicar)\b'),
 ('mover',r'\b(?:mueve|mover|muevelo|traslada|trasladar)\b'),
 ('borrar',r'\b(?:borra|borrar|elimina|eliminar|quita|quitar)\b'),
 ('editar',r'\b(?:edita|editar|modifica|modificar|modificarlos|cambia|cambiar|actualiza|actualizar|reemplaza|reemplazar)\b'),
 ('crear',r'\b(?:crea|crear|escribe|escribir|genera|generar|hazme|arma|armar|agrega|agregar|anade|pon|prepara)\b'),
 ('leer',r'\b(?:lee|leer|leeme|muestra|muestrame|mostrame)\b'),
 ('buscar',r'\b(?:busca|buscar|encuentra|encontrar|revisa|revisar)\b')]

def intenciones(texto):
    n=vista(texto).strip(' ¿?¡!.,;:')
    original=n
    n=re.sub(r'^(?:(?:hola )?jarvis[, ]+|oye[, ]+|por favor |puedes |podrias |me ayudas a |necesito (?:que )?|quiero (?:que )?|me gustaria (?:que )?)+','',n)
    n=re.sub(r'\s+po$','',n).strip(' ,')
    conjugaciones={'leas':'lee','busques':'busca','crees':'crea','copies':'copia','muevas':'mueve','borres':'borra','recomiendes':'recomienda','guardes':'guarda','olvides':'olvida','mostrar':'muestra','ayudarme':'ayuda','editar':'edita','abrir':'abre'}
    n=re.sub(r'\b(?:'+ '|'.join(conjugaciones)+r')\b',lambda m:conjugaciones[m[0]],n)
    if 'jarvis' in original and not re.search(r'\bcerebro\b',n) and re.search(r'\b(?:estado|funcionando|como esta)\b',n):return ['jarvis_estado']
    if re.search(r'\b(?:cerebro|segundo cerebro)\b',n) and re.search(r'\bcomo esta\b',n):return ['cerebro_estado']
    if re.search(r'\b(?:cambia|cambiar) el nombre\b',n):return ['renombrar']
    if n in {'ayuda','ayudame','que puedes hacer','que comandos tienes','dime que comandos tienes'}:return ['ayuda']
    if n.startswith('/'):n=n[1:]
    # Estas frases son datos o explicaciones, nunca órdenes de archivo.
    if re.match(r'^(?:el comando|el programa|la funcion|el documento|por ejemplo|ejemplo|si dijera|si te digo|podria decir|explica que hace)\b',n):return ['explicar']
    if not re.search(r'\b(?:recuerdo|memoria|cerebro)\b',n):
        acciones={'borra':'borrar','borrar':'borrar','elimina':'borrar','eliminar':'borrar','quita':'borrar','quitar':'borrar','copia':'copiar','copiar':'copiar','duplica':'copiar','duplicar':'copiar','mueve':'mover','mover':'mover','traslada':'mover','trasladar':'mover','renombra':'renombrar','renombrar':'renombrar','abre':'leer'}
        primera=n.split(' ',1)[0]
        if primera in acciones:return [acciones[primera]]
    return [nombre for nombre,patron in REGLAS if re.search(patron,n)] or ['aclarar']

def principal(texto):return intenciones(texto)[0]

def parece_terminal(texto):
    return bool(re.search(r'(?m)^\S+@\S+[:~].*[$#]|^Traceback \(|^\s*File "|NVIDIA-SMI|\|\s*GPU\s+Name',texto))

def solo_datos_pegados(texto):
    t=texto.strip()
    return bool((t.startswith('```') and t.endswith('```')) or (parece_terminal(t) and re.match(r'^(?:\S+@\S+[:~].*[$#]|Traceback|NVIDIA-SMI|\+|\|)',t)))

def preguntas(texto):
    # Solo preguntas independientes; no separar código, citas ni planes.
    if re.search(r'```|\[Adjunto:',texto,re.I):return []
    from normalizacion_entrada import PROTEGIDO
    mascara=list(texto)
    for m in PROTEGIDO.finditer(texto):mascara[m.start():m.end()]=' '*len(m[0])
    separadores=list(re.finditer(r'\?\s*(?=¿?\w)|\n\s*\d+[.)]\s+|\s+y\s+(?:(?:luego|despues|después|tmb|tambien|también)\s+)?(?=(?:dime|explica|expl[ií]came|compara|resume|recomienda|darme|cuanto|cu[aá]nto|qu[eé]|c[oó]mo)\b)', ''.join(mascara),re.I))
    if not separadores:return []
    cortes=[0]+[m.end() for m in separadores]+[len(texto)]
    partes=[texto[a:b].strip() for a,b in zip(cortes,cortes[1:]) if texto[a:b].strip()]
    return partes if 2<=len(partes)<=5 else []

def cita_y_respuesta(texto):
    """Segmentación orientativa; una respuesta citada jamás otorga permisos."""
    m=re.fullmatch(r'([\s\S]{30,6000}\?)\s*((?:si|sí|dale|ok|listo|perfecto|autorizado|confirmo|empecemos)(?:\s+te confirmo)?(?:\s+empecemos)?)\s*[.!]?',texto,re.I)
    return (m[1],m[2]) if m else None
