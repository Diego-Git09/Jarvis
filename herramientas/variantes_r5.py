"""Variantes ampliadas escritas para regresión, no confirmaciones del usuario.

Diez formulaciones por familia de fallo. Las originales están en corpus_r5.json.
Las pruebas previas conservan además variantes de estado, referencias y jerga.
No se aprende ni se añade ningún término al vocabulario privado al importarlo.
"""
def diez(texto):
    frases=texto.split('|')
    if len(frases)!=10 or len(set(frases))!=10:raise ValueError('Cada familia necesita diez frases distintas')
    return frases

FAMILIAS={
'scope_saludo':diez('hola|HOLA|holaaa|Hola Jarvis|hola jarvis|buenas|buenos dias|buenas tardes|hola!|hola ?'),
'scope_variable':diez('q es una variable|que es una variable|qué es una variable?|QUE ES UNA VARIABLE|Que es una variable|explicame que es una variable|explica una variable en programacion|para que sirve una variable|como funciona una variable|una variable que significa'),
'scope_api':diez('q es una api|que es una API|qué es una API?|QUE ES UNA API|explicame q es una api|explica una API|para que sirve una API|como funciona una api|quiero entender una API|dime que significa API'),
'scope_microservicios':diez('analiza ventajas y desventajas de microservicios|que son los microservicios|QUE SON LOS MICROSERVICIOS|explicame microservicios|para que sirven los microservicios|compara monolito y microservicios|microservicios que significa|ventajas de usar microservicios|como funcionan los microservicios|dime que son microservicios'),
'externo_apagado':diez('usa el externo para explicar una api|usa zen para responder q es una variable|utiliza el externo para explicar Docker|consulta el externo sobre microservicios|usa opencode para una explicacion|usa el externo para responder esto: q es una api|USA EL EXTERNO para explicar una API|utiliza zen para responder una pregunta|consulta zen para explicar Kotlin|usa el externo para resumir una idea'),
'lecturas_encadenadas':diez('revisa la carpeta de trabajo y luego lee prueba.txt|dime q archivos hay y luego lee prueba.txt|muestra los archivos y luego lee prueba.txt|lista archivos y luego lee prueba.txt|muestrame los archivos y luego lee prueba.txt|revisa la carpeta de trabajo, dime q archivos hay y luego lee prueba.txt|revisa mi carpeta de trabajo y luego lee prueba.txt|lee prueba.txt y luego lee notas.txt|lee "prueba.txt" y luego lee "notas.txt"|lista los archivos y luego abre prueba.txt'),
'guardado_corto':diez('guarda en el segundo cerebro q hoy probe jarvis|guarda en el segundo cerebro que hoy probe jarvis|GUARDA EN EL SEGUNDO CEREBRO QUE hoy probe jarvis|Guarda en el segundo cerebro que hoy probe jarvis|guarda en segundo cerebro que hoy probe jarvis|guarda en el 2do cerebro que hoy probe jarvis|guarda en el segundo cerebro que hoy probé Jarvis|guarda en el segundo cerebro que hoy revisé la ayuda|guarda en el segundo cerebro que hoy practique Python|guarda en el segundo cerebro que mañana sigo estudiando'),
'modelo_memoria':diez('cuanto pesa un modelo de 8b en la vram|cuanto ocupa un modelo 8b en memoria|cuanto consume un modelo de 8b en ram|CUANTO PESA UN MODELO DE 8B EN LA VRAM|cuánto pesa un modelo de 8B en la VRAM?|tamaño de un modelo de 8b en memoria|memoria necesaria para un modelo 8b en gpu|cuanto ocupa un modelo de 8b en la GPU|cuanto pesa un modelo de 8b en RAM|cuanto consume un modelo 8b en VRAM'),
'guia_room':diez('como guardo datos con room en kotlin|COMO GUARDO DATOS CON ROOM EN KOTLIN|cómo guardo datos con Room en Kotlin?|como uso room en kotlin|dame pasos para usar Room|necesito una guia de Room|tutorial de Room para Kotlin|pasos para persistencia con room|como construyo la base de Room|como hago un DAO con Room'),
'guia_apex':diez('necesito instalar apex tengo oracle 19c en docker|NECESITO INSTALAR APEX EN ORACLE|como instalo APEX en Oracle|cómo instalo APEX en Docker?|guia para instalar apex|pasos para instalacion APEX|como configurar APEX en Oracle|como configuro APEX en Docker|necesito instalar apex|tutorial de instalacion de APEX'),
'guia_spring':diez('como hago un endpoint rest en spring boot|como hago una api en Spring Boot|dame una guia de spring|pasos para Spring Boot|quiero empezar con Spring Boot|como uso Spring Boot|que es Spring Boot|guia para un proyecto Spring|COMO HAGO UN ENDPOINT EN SPRING BOOT|como hago una lista de productos con Spring'),
'sistema_ubuntu':diez('que puedo revisar en Ubuntu si va lento|como hago un diagnostico en Linux|dame una guia de Ubuntu|pasos para diagnosticar Linux|como uso ss en Ubuntu|que es un puerto en Ubuntu|como hago lecturas en Linux|COMO HAGO UN DIAGNOSTICO EN UBUNTU|quiero empezar un diagnostico Linux|que es un proceso en Ubuntu'),
}
