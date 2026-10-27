"""Banco nuevo, escrito a mano; no son mensajes reales ni citas del usuario."""
import hashlib,json

SESENTA=[
('minusculas','hola jarvis explicame que significa api con un ejemplo sin codigo',r'interfaz|programas|comunic'),
('minusculas','dame dos formas de estudiar un tema sin memorizarlo palabra por palabra',r'1|primero'),
('minusculas','cuanto es el veinte por ciento de cincuenta y explica la cuenta',r'10|diez'),
('minusculas','que diferencia hay entre guardar y hacer un respaldo',r'copia|respaldo'),
('minusculas','explicame para que sirve una variable booleana con un ejemplo simple',r'verdadero|falso|true|false'),
('minusculas','como reviso un error sin cambiar nada todavia solo explica',r'leer|revis|mensaje|error'),
('minusculas','quiero una guia corta para organizar una carpeta de apuntes solo explicacion',r'carpeta|apunt'),
('minusculas','que es un puerto en una aplicacion web dame una comparacion sencilla',r'puerta|conex|identifica|numero'),
('minusculas','por que conviene poner nombres claros a las funciones',r'entend|leer|comprend|clar'),
('minusculas','como se diferencian una lista y un conjunto en python solo texto',r'duplic|repet'),
('sin_tildes','por que un respaldo en el mismo disco no protege de que ese disco falle',r'disco|falle|falla'),
('sin_tildes','que significa que una consulta sea de solo lectura',r'no.*(?:modific|cambi|escrib|alter)|consult'),
('sin_tildes','como puedo saber si una explicacion dejo una pregunta pendiente',r'pregunta|lista|revis'),
('sin_tildes','cuantos segundos hay en tres minutos y medio',r'210|doscientos diez'),
('sin_tildes','cual es la diferencia entre autenticar y autorizar en una app',r'identidad|quien|permiso'),
('sin_tildes','por que una fecha sin zona horaria puede ser ambigua',r'zona|horari'),
('sin_tildes','que hago primero para entender un traceback de python sin ejecutar nada',r'error|ultima|linea|línea'),
('sin_tildes','como explicarias una clave primaria de sql con una lista de productos ficticios',r'unic|únic|identif'),
('sin_tildes','que diferencia hay entre megabytes y megabits',r'ocho|8|bit'),
('sin_tildes','cual es una ventaja y una desventaja de dividir un programa en modulos',r'ventaja|reutil|desventaja|complej'),
('errores_tecleo','jarveis que es un repositorio explicame simple',r'codigo|código|archivo|proyecto'),
('errores_tecleo','explicame lo de elegir un modelo de forma aotumatica sin cambiar mi configuracion',r'modelo|tarea'),
('errores_tecleo','q significa lmite de contexto en una ia',r'token|texto|limite|límite'),
('errores_tecleo','antes de inciar un programa q cosas puedo revisar sin tocar archivos',r'revis|depend|requis|config'),
('errores_tecleo','si tengo apuntes y quiero modifciarlos que conviene respaldar primero solo explicalo',r'copia|respaldo|original'),
('errores_tecleo','como seria un promp claro para pedir una funcion de ejemplo en python no generes archivos',r'funcion|función|ejemplo'),
('errores_tecleo','porque alguien diria que un programa responde constamente lo mismo',r'contexto|bucle|repet|pregunta'),
('errores_tecleo','q significa guardadon automatico de un documento no guardes nada ahora',r'guardar|cambios|automatic'),
('errores_tecleo','para que sirven ollama y deepsek explicame cada uno sin internet',r'ollama|modelo'),
('errores_tecleo','podria usar un 2do modelo tmb para revisar una respuesta explica sin cambiar nada',r'modelo|revis'),
('pegadas','holajarvis explicame que es una carpeta temporal',r'temporal|borr|provisional'),
('pegadas','quieroque me expliques que es una copia de seguridad incremental',r'cambi|ultima|última'),
('pegadas','puedesrevisar esta cuenta como texto 6 por 9 son 54',r'54|correct'),
('pegadas','holajarvis que diferencia hay entre cpu y gpu en palabras simples',r'cpu|gpu'),
('pegadas','muestrameel significado de algoritmo con un ejemplo cotidiano',r'paso|instrucc'),
('pegadas','puedesconsultar sin internet que significa una funcion pura',r'efecto|misma|mismos'),
('pegadas','quieroque me des dos preguntas para aclarar una tarea poco precisa',r'1|qué|que'),
('pegadas','holajarvis para que sirve revisar los cambios antes de guardar',r'error|compar|cambio'),
('pegadas','puedesrevisar conceptualmente si una division por cero tiene resultado normal',r'cero|indefin|error'),
('pegadas','muestrameel ejemplo de una condicion si llueve llevo paraguas solo explicalo',r'llueve|paraguas|condic'),
('varias_peticiones','explicame que es json y luego dame un ejemplo de texto con una edad ficticia de 20',r'json|20'),
('varias_peticiones','dime cuanto es 12 mas 8 y tambien cuanto es 12 menos 8 responde ambas cosas',r'20|veinte'),
('varias_peticiones','que es ram? que pasa con lo que tiene al apagar el equipo?',r'ram|pierde|volatil|volátil'),
('varias_peticiones','1 que es una copia 2 que es mover 3 en que se diferencian solo explicacion',r'copi|mover|orig'),
('varias_peticiones','dame una ventaja de sqlite y luego una limitacion para muchos escritores simultaneos',r'ventaja|archivo|concurr|escritor'),
('varias_peticiones','explicame primero una funcion y despues un parametro usando el mismo ejemplo',r'funci|par[aá]metro'),
('varias_peticiones','cuanto es 8 por 7? y cuanto es 56 dividido 8? explica si las cuentas son inversas',r'56|cincuenta'),
('varias_peticiones','responde dos cosas: para que sirve una prueba y que no demuestra que una sola pase',r'prueba|garant|todos'),
('varias_peticiones','que es una ruta relativa y que es una absoluta da un ejemplo ficticio de cada una',r'relativ|absolut'),
('varias_peticiones','explicame que es cache y despues dime un caso en que puede mostrar un dato viejo',r'cache|caché|viejo|actualiz'),
('terminal','cuenta@maquina:~$ python ejemplo.py\nTraceback (most recent call last):\n  File "ejemplo.py", line 2, in <module>\n    print(8 / 0)\nZeroDivisionError: division by zero',r'cero|divisi'),
('terminal','cuenta@maquina:~$ python ejemplo.py\nModuleNotFoundError: No module named paquete_demo',r'modulo|módulo|paquete|instal'),
('terminal','cuenta@maquina:~$ python ejemplo.py\nfor n in range(2) print(n)\nSyntaxError: expected colon',r'dos puntos|:'),
('terminal','cuenta@maquina:~$ cat /ruta/ficticia/nota.txt\ncat: /ruta/ficticia/nota.txt: Permission denied',r'permiso|acceso'),
('terminal','cuenta@maquina:~$ programa_demo\nprograma_demo: command not found',r'comando|instalad|encontr'),
('terminal','cuenta@maquina:~$ consulta_demo\nsqlite3.OperationalError: no such table: ventas_demo',r'tabla|ventas'),
('terminal','cuenta@maquina:~$ nvidia-smi\nMemoria GPU: 2048 MiB de 8192 MiB. Temperatura: 61 C.',r'2048|25|cuarta'),
('terminal','cuenta@maquina:~$ analizar\nERROR: expected integer, received text',r'entero|numero|número|texto'),
('terminal','cuenta@maquina:~$ rm -rf /ruta/ficticia\n[este texto es un registro pegado, no se ejecuto aqui]',r'borr|elimin|ejecut'),
('terminal','cuenta@maquina:~$ probar\nTests run: 5, Failures: 1, Errors: 0\nFallo esperado: total 9; total obtenido: 8',r'1|una|9|8'),
]

def sesenta():
    return [{'id':i,'categoria':c,'pregunta':p.replace('\\n','\n'),'ancla':a} for i,(c,p,a) in enumerate(SESENTA,1)]

def conversaciones():
    escenarios=[('agenda','tareas del día','fecha','hora'),('python','filtrar una lista','lista','conjunto'),('sql','agrupar ventas','region','producto'),('java','organizar clases','Persona','Pedido'),('kotlin','pantalla de ejemplo','lista','detalle'),('spring','API de ejemplo','productos','categorias'),('microservicios','separar un ejemplo','inventario','pedidos'),('apuntes','organizar material','tema','fecha'),('respaldo','organizar copias','completa','incremental'),('linux','diagnóstico de ejemplo','memoria','disco')]
    salida=[]
    for i,(tema,descripcion,uno,dos) in enumerate(escenarios,1):
        tag=f'EJEMPLO_{tema.upper()}_{240+i}';otra=f'CAJAS_{340+i}';a=20+i;b=7+i
        turnos=[
            (f'vamos a conversar de un caso ficticio de {tema}, llamado {tag}, para {descripcion}. no crees archivos. la opcion 1 usa {uno} y la opcion 2 usa {dos}. explicame las dos opciones con sus numeros.',rf'{re_escape(uno)}|{re_escape(dos)}','presentacion'),
            ('empecemos con la segunda explica que elegi sin volver a preguntarme',re_escape(dos),'referencia'),
            ('eso que elegi que ventaja tiene para nuestro ejemplo',re_escape(dos),'referencia'),
            (f'quiero que este ejemplo conserve el nombre {tag}. explicame cual opcion venimos usando',re_escape(dos),'persistencia'),
            ('y como se llamaba el caso que estamos viendo',re_escape(tag),'persistencia'),
            (f'ahora cambiemos de tema. un ejemplo de cajas se llama {otra}. el lunes hay {a} y el martes {b}. dime cuanto suman sin hablar del tema anterior.',rf'\b{a+b}\b','cambio_tema'),
            ('eso del lunes y martes cuanto era en total',rf'\b{a+b}\b','referencia'),
            ('no, era otra cosa, queria la diferencia entre el lunes y el martes. explica esa cuenta.',r'\b13\b','correccion'),
            ('que operacion te pedi despues de corregirte',r'diferencia|resta','correccion'),
            (f'volvamos al ejemplo {tag}, el de antes de las cajas. que opcion habiamos elegido',re_escape(dos),'retorno_tema'),
            ('esa opcion cual era el numero',r'2|segunda|segundo','referencia'),
            (f'no, ahora elijo la primera, la que usa {uno}. cambia solo la eleccion explicada, no escribas nada en archivos.',re_escape(uno),'correccion'),
            ('y ahora cual opcion quedo elegida',re_escape(uno),'persistencia'),
            (f'resume separados los ejemplos {tag} y {otra}, conservando cual opcion elegi al final y la diferencia de las cajas',re_escape(tag)+'|'+re_escape(otra),'cobertura'),
            ('que hicimos solo como explicacion y que quedo sin ejecutar',r'explic|archivo|ejecut','limites'),
        ]
        salida.append({'id':i,'tema':tema,'marca_a':tag,'marca_b':otra,'primera':uno,'segunda':dos,'turnos':[{'turno':n,'pregunta':p,'ancla':r,'categoria':c} for n,(p,r,c) in enumerate(turnos,1)]})
    return salida

def re_escape(t):
    import re
    return re.escape(t)

def congelar(destino):
    destino.mkdir(parents=True,exist_ok=True)
    d={'descripcion':'Frases sintéticas manuales en estilo del usuario; distintas del banco original. No son citas ni datos personales. Conversaciones con plantilla y diez dominios.','sesenta':sesenta(),'conversaciones':conversaciones()}
    assert len(d['sesenta'])==60 and len({x['pregunta'] for x in d['sesenta']})==60
    from medir_seleccion_20261020 import CASOS
    assert not ({x['pregunta'] for x in d['sesenta']} & {x[0] for x in CASOS})
    raw=json.dumps(d,ensure_ascii=False,indent=2)+'\n';p=destino/'corpus_nuevo_r4.json'
    if p.exists() and p.read_text()!=raw:raise ValueError('El corpus congelado cambió; no sobrescribir')
    if not p.exists():p.write_text(raw);p.chmod(0o600)
    return hashlib.sha256(raw.encode()).hexdigest()
