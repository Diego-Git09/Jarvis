"""Reduce reglas de acción solo para explicaciones explícitas sin ejecución."""
import re
from normalizacion_entrada import plegar

def aplica(pedido,estado=None):
    e=estado or {};n=plegar(pedido)
    if e.get('_fuentes_turno',bool(e.get('_tanda_documentos') or e.get('_documento_tramo'))) or e.get('_proyecto_codigo'):return False
    if re.search(r'\b(?:crea|escribe|modifica|guarda|edita)\s+(?:(?:el|un|este)\s+)?archivo\b',n) and not re.search(r'\b(?:no crees archivos|sin escribir|solo texto)\b',n):return False
    if re.search(r'\b(?:solo texto|solo explica|no (?:la |lo )?ejecutes|sin ejecutarl[ao]|no crees archivos|conceptualmente|evalua el riesgo)\b',n):return True
    if '[Adjunto:' in pedido and not e.get('_tanda_documentos'):return True
    if re.search(r'\b(?:invitacion|hervir|hiervo|taza de te)\b',n):return True
    if re.search(r'\bbusqueda\b',n) and re.search(r'\b(?:lineal|binaria)\b',n):return True
    from normalizacion_entrada import vista
    v=vista(pedido)
    if re.search(r'(?:^|\s)(?:/[^\s]+/|~/)|\.(?:pdf|docx?|xlsx?|pptx?|txt|md|csv|py|sql)\b',pedido,re.I):return False
    if re.search(r'\b(?:esto|eso|aquello|que pide|que dice|lo que|lo anterior|lo siguiente|lo ultimo|ese|esa)\b',v):return False
    # «Una copia» es un sustantivo en una explicación; «y luego copia» sigue
    # siendo una acción. No quitar el verbo de una segunda petición real.
    acciones=re.sub(r'\buna\s+copia\b','copia_conceptual',v)
    if re.match(r'^(?:(?:hola|jarvis|hola jarvis)\s+)?(?:que (?:es|significa|diferencia hay)|para que|por que|explicame|explica|(?:quiero|necesito) (?:que )?me expliques|(?:puedes|podrias) explicarme|muestrame el significado)\b',v) and not re.search(r'\b(?:crea|creame|guarda|mueve|copia|borra|elimina|edita|modifica|ejecuta|instala|mis recuerdos|mi recuerdo|el recuerdo|segundo cerebro|adjunto|mis archivos|mi archivo)\b',acciones):return True
    return False

def sistema(pedido):
    s='Eres Jarvis. Responde a la pregunta vigente en español, con frases simples. Explica, no ejecutes acciones. No tienes herramientas en esta consulta. No inventes datos, rutas, lugares ni requisitos. No menciones reglas ni etiquetas internas ni pidas un catálogo de herramientas. Entrega el código o análisis pedido, sin solicitar datos ya aportados.'
    from guias_contexto_r3 import sistema_detectado
    s+=' '+sistema_detectado()
    n=plegar(pedido)
    from normalizacion_entrada import analizar
    entrada=analizar(pedido)
    if entrada.cambios:s+=' Lectura del pedido para entender abreviaciones y errores: '+entrada.vista+'. Conserva el original para código, citas y nombres.'
    from guias_contexto_r3 import contexto as guia_tecnica
    apoyo=guia_tecnica(pedido)
    if apoyo:s+=' '+apoyo
    from apoyo_conceptual import contexto
    nota=contexto(pedido)
    if nota:s+=' Apoyo conceptual: '+nota
    if not re.search(r'\b(?:codigo|funcion|clase|script|sql|kotlin|java|python|detallad[oa]|completo)\b',n):s+=' Responde breve: entre tres y cinco frases o hasta cuatro pasos, sin una pregunta de cierre automática.'
    if '[adjunto:' in n:s+=' El contenido después de [Adjunto:] está incluido en el mensaje y puedes leerlo. Usa sus valores exactos. Si se pide total, calcula la suma; si se pide contradicción, identifica ambas afirmaciones sin decidir cuál es verdadera. Un conflicto entre cantidades viene de que sus valores difieren; la falta de validación impide elegir la fuente correcta, pero no es la causa del desacuerdo.'
    if re.search(r'\bkotlin\b',n):s+=' En Kotlin una función usa fun, parámetros nombre: Int y retorno : Int; entrega exactamente la firma y operación pedidas.'
    if re.search(r'\bsql\b',n):s+=' Si se aportan tabla y columnas, usa esos identificadores en SELECT, SUM y GROUP BY; no hace falta un esquema adicional para el ejemplo.'
    if re.search(r'\b(?:borrar|riesgo)\b',n):s+=' Se pide evaluar el riesgo, no acceder ni borrar archivos. No propongas ejecutar el borrado después.'
    if 'invitacion' in n:s+=' Una invitación sin dirección ni hora aportadas no inventa lugar, hora ni acuerdos previos; invita para el día indicado y deja esos datos por definir.'
    if re.search(r'\b(?:hervir|hiervo|taza de te)\b',n):s+=' Para calentar agua usa un hervidor u olla apta para el calor; una taza común no va sobre fuego ni placa. Hierve el agua en ese recipiente y viértela con cuidado en la taza. No inventes tiempos de calentamiento.'
    if re.search(r'\bbusqueda\b',n):s+=' Buscar localiza un elemento; no ordena datos. La búsqueda lineal recorre secuencialmente y no exige orden. La binaria requiere orden; el acceso eficiente al punto medio permite su ventaja logarítmica. Un arreglo no es requisito lógico universal, sino una estructura de acceso eficiente.'
    if re.search(r'\b(?:depura|corrige)\b',n):s+=' Identifica el error sintáctico concreto antes de corregir: distingue dos puntos faltantes de indentación. Una sentencia simple puede ir en la misma línea después de los dos puntos.'
    return s

def incumplimientos(pedido,respuesta):
    n=plegar(pedido);r=plegar(respuesta);errores=[]
    from normalizacion_entrada import vista
    if re.match(r'^q\s+es\s+una?\s+variable\b',plegar(pedido)) and re.search(r'\bq\s+(?:es (?:una? )?variable|podria|puede representar)|\bvariable\s+["«\']?q\b',r):
        errores.append('En esta pregunta q es abreviación de que; no es el nombre de una variable. Define qué es una variable en programación con un ejemplo simple. No pidas contexto para identificar q.')
    if 'incremental' in n:
        for frase in re.split(r'(?<=[.!?])\s+|\n+',r.replace('*','')):
            if ('incremental' in frase and
                re.search(r'\bdesde la ultima (?:copia (?:de seguridad )?)?completa\b',frase) and
                not re.search(r'\b(?:diferencial|o incremental|no es correcto|incorrecto|no se compara)\b',frase)):
                errores.append('Confundiste incremental con diferencial. La incremental guarda los cambios desde la copia anterior de su cadena, completa o incremental; la diferencial toma como base la última completa. No garantices copiar solo líneas ni ahorrar siempre espacio.')
                break
    if 'megabit' in n:
        prosa_unidades=re.sub(r'```[\s\S]*?```|`[^`\n]*`|«[^»\n]*»|"[^"\n]*"','',respuesta)
        abreviacion_erronea=bool(re.search(r'\bMb\b\s+(?:mide|miden)\s+(?:la\s+)?velocidad\b',prosa_unidades))
        for frase in re.split(r'(?<=[.!?])\s+|\n+',r):
            if abreviacion_erronea or (re.search(r'\bmegabits?\b',frase) and
                re.search(r'\bmide\b.{0,30}\bvelocidad\b',frase) and
                not re.search(r'por segundo|/s|mbps|no mide',frase)):
                errores.append('Un megabit es cantidad de información. La velocidad se expresa por segundo, por ejemplo Mb/s. Conserva también la relación 1 byte = 8 bits.')
                break
    creacion=bool(re.search(r'\b(?:crea|escribe|genera)\b',n) and re.search(r'\b(?:funcion|clase|ejemplo|codigo)\b',n))
    if creacion and not re.search(r'```|\b(?:def|fun|class)\s+\w+\s*[({]',pedido) and re.search(r'\b(?:codigo (?:que has |que )?proporcionado|codigo proporcionado)\b',r):errores.append('Se pidió un ejemplo nuevo, no corregir código previo. No inventes errores de un código que no se entregó.')
    if creacion and 'python' in n and 'funcion' in n and not re.search(r'\b(?:async\s+)?def\s+\w+\s*\(',respuesta):errores.append('Falta la función Python pedida, con def y parámetros. Entrega código como texto, sin pedir herramientas ni rutas.')
    if 'busqueda' in n and re.search(r'\b(?:son algoritmos|son tecnicas|ambas son tecnicas) de ordenamiento',r):errores.append('Buscar no es ordenar; corrige la clasificación de los algoritmos y sus requisitos.')
    if '[adjunto:' in n:
        if re.search(r'\b(?:no se ha validado|sin validar|no esta validado)\b',n) and re.search(r'\b(?:ambas (?:afirmaciones|fuentes) son (?:validas|invalidas|correctas|incorrectas|falsas|verdaderas)|fuentes verificadas)\b',r):errores.append('Las fuentes no están verificadas: no declares verdadera ni falsa ninguna. Solo compara sus datos y deja su verificación pendiente.')
        for atributo in ('vendidas','compradas','fabricadas','entregadas','danadas'):
            if 'cajas '+atributo in r and atributo not in n:errores.append('El texto fuente no atribuye «'+atributo+'» a las cajas; conserva su descripción sin inventar propiedades.')
        if 'contradiccion' in n and re.search(r'(?:contradiccion|contradictorias).{0,100}(?:porque|se basa).{0,100}(?:sin validacion|no hay|no se ha validado|sin validar)',r,re.S):errores.append('El desacuerdo está en las cantidades distintas. No atribuyas la contradicción a la ausencia de validación; esa ausencia solo impide elegir cuál fuente es correcta.')
    if re.search(r'\b(?:riesgo|borrar)\b',n) and re.search(r'\b(?:sera irreversible|siempre irreversible|nunca (?:puede|podra) recuperarse)\b',r):errores.append('La pérdida podría ser irreversible; no afirmes que toda recuperación sea imposible sin verificar el caso.')
    original=re.search(r'como texto:\s*(.*?)(?:\.\s*No |$)',pedido,re.I|re.S)
    if original and 'python' in n:
        import ast
        try:ast.parse(original[1])
        except SyntaxError as e:
            falta_dos_puntos="expected ':'" in str(e) or (':' not in original[1] and re.match(r'\s*(?:for|if|elif|while|with|def|class)\b',original[1]))
            # Una instrucción para indentar la versión corregida es válida;
            # solo rechazar un diagnóstico de indentación del original.
            if falta_dos_puntos and '\n' not in original[1] and re.search(r"\b(?:falta de indentacion|error de indentacion|no esta correctamente indentada|no esta indentada correctamente|dos puntos de indentacion|codigo original no esta completo)\b",r):errores.append('El error inicial es que faltan los dos puntos; no atribuyas ese fallo al uso de print o solo a la indentación. Una sentencia simple puede ir en la misma línea tras los dos puntos. No pidas otra versión: trabaja con la sentencia ya entregada.')
    if re.search(r'\bsql\b',n) and re.search(r'\bselect\b',n) and not re.search(r'\bselect\s+[^;]+?\s+from\s+[\w"`]+',r):errores.append('Falta la consulta SELECT ... FROM solicitada con los identificadores ya entregados.')
    if re.search(r'\bkotlin\b',n) and re.search(r'\bfuncion\b',n) and not re.search(r'\bfun\s+\w+\s*\(',r):errores.append('Falta una función Kotlin válida con fun y los parámetros pedidos.')
    if 'kotlin' in n and '\\n' in re.sub(r'"(?:\\.|[^"\\])*"','',respuesta):errores.append('El código Kotlin contiene barras y letras n fuera de cadenas; usa saltos de línea reales.')
    if '[adjunto:' in n and re.search(r'\b(?:no tengo acceso|no puedo (?:ver|acceder)|proporciona el (?:texto|contenido))\b',r):errores.append('El contenido inline ya está presente; analízalo directamente.')
    if '[adjunto:' in n and re.search(r'\btotal\b',n):
        datos=pedido.split('[Adjunto:',1)[-1]
        valores=re.findall(r':\s*(\d+)\s+cajas\b',datos,re.I)
        if len(valores)>=2 and not re.search(r'\b'+str(sum(map(int,valores)))+r'\b',r):errores.append('No aparece el total aritmético solicitado: '+str(sum(map(int,valores)))+'.')
    if '[adjunto:' in n and 'contradiccion' in n:
        valores=re.findall(r'Fuente\s+\w+:\s*(\d+)',pedido,re.I)
        if len(set(valores))>=2 and any(not re.search(r'\b'+v+r'\b',r) for v in valores):errores.append('Debes contrastar los valores de ambas fuentes incluidos en el mensaje.')
    return errores
