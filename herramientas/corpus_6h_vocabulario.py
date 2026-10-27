"""Corpus de lenguaje congelable: peticiones sintéticas y citas del usuario.

No llama modelos, no escribe recordatorios y no consulta Segundo Cerebro.
Las expectativas son estructuras y seguridad; no una prueba de comprensión general.
"""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPORTES = BASE / 'registros/reportes/mejora_6h_20261014'

def _fila(familia, pedido, esperado, *, modismo=False, tipeo=False, negativo=False,
          ambiguo=False, cadena=False, real=False, estado=None):
    return dict(familia=familia, pedido=pedido, esperado=esperado,
                modismo=modismo, tipeo=tipeo, negativo=negativo, ambiguo=ambiguo,
                cadena=cadena, real=real, estado=estado or {})

def _envolver(p, i):
    # Variaciones léxicas, no espacios artificiales. Nombres y rutas se conservan.
    prefijos = ['Oye compa, ', 'Jarvis, altiro ', 'Cachai, ', 'Me podís ', 'Al toque ']
    p = prefijos[i % len(prefijos)] + p + ' po'
    return p

def _typo(p, i):
    faltas = {'muestra':'muesrtame', 'crea':'creamme', 'lee':'leeme',
              'copia':'copiame', 'busca':'buskame', 'mueve':'muebe',
              'hazme':'haceme', 'genera':'generame', 'modifica':'modifca',
              'elimina':'elimna', 'recuérdame':'recuardame'}
    a, _, b = p.partition(' ')
    return ['xfa ', 'porfis ', 'me podis ', 'podrias ', 'Jarbvis, '][i % 5] + faltas.get(a, a) + (' ' + b if b else '')

def construir():
    filas = []
    fechas = ['mañana a las 08:00', 'pasado mañana a las ocho y media',
              'el lunes a las 8', 'en dos horas', 'mañana todo el día']
    verbos = ['hazme', 'crea', 'ponme', 'anótame', 'agéndame']
    lista = ['muestra mis recordatorios', 'lista los avisos de escritorio',
             'enséñame todas las notas de escritorio', 'dime qué recordatorios tengo',
             'cuéntame cuáles son mis recordatorios']
    ayuda = ['qué comandos puedo usar', 'dame la ayuda de Jarvis', 'enséñame cómo te uso',
             'muéstrame qué sabes hacer', 'tírame la ayuda']
    horas = ['dime qué hora es en Chile', 'muestra la hora actual', 'qué hora tenemos',
             'cuéntame la fecha y hora', 'pásame la hora de Santiago']
    estados = ['verifica si estás usando Ollama', 'dime qué modelo usas',
               'muéstrame tu diagnóstico', 'revisa si Ollama responde', 'qué modelo está activo']
    adjuntos = ['muestra mis adjuntos', 'dime qué documentos adjunté',
                'lista los archivos de la tanda', 'pásame los adjuntos activos',
                'enséñame las fuentes que tienes adjuntas']
    confirmaciones = ['dale', 'ya po', 'sipo', 'obvio', 'sí te confirmo', 'hazlo',
                      'mándale', 'adelante', 'bueno sigamos', 'sí, empecemos']
    for i in range(25):
        titulo = ['Lapiz Rosado', 'Prueba de kotlin', 'Revisión SQL', 'Pega Ñuñoa', 'Query literal'][i % 5] + f' {i:02d}'
        # 16 familias × 25. Quedan identificadores distintos en cada captura literal.
        bases = [
            ('recordatorio_crear', f'{verbos[i%5]} un recordatorio de "{titulo}" para {fechas[i%5]}',
             {'nombre':'crear_recordatorio', 'texto':titulo, 'fecha_canonica':fechas[i%5]}),
            ('recordatorio_listar', lista[i%5], {'nombre':'listar_recordatorios'}),
            ('recordatorio_cambiar', f'modifica el recordatorio {i%5+1} para que diga "{titulo}"',
             {'nombre':'modificar_recordatorio', 'numero':i%5+1, 'texto':titulo}),
            ('recordatorio_anticipacion', f'muestra el recordatorio {i%5+1} {i%3+1} días antes',
             {'nombre':'modificar_recordatorio', 'numero':i%5+1, 'anticipacion_dias':i%3+1}),
            ('recordatorio_eliminar', f'elimina el aviso {i+1}', {'nombre':'eliminar_recordatorio','numero':i+1}),
            ('memoria_buscar', f'busca apuntes sobre "Caso Ñuñoa {i:02d}"',
             {'nombre':'buscar_memoria','consulta':f'"Caso Ñuñoa {i:02d}"'}),
            ('memoria_mover', f'mueve las memorias {i%5+1} al proyecto "Estudios Ñuñoa {i:02d}"',
             {'nombre':'clasificar_recuerdos','numeros':[i%5+1],'proyecto':f'Estudios Ñuñoa {i:02d}'}),
            ('proyecto_crear', f'crea proyecto "Tienda Query {i:02d}"',
             {'nombre':'crear_proyecto','proyecto':f'Tienda Query {i:02d}'}),
            ('archivo_leer', f'lee el documento "Informe  Ñuñoa {i:02d}.pdf"',
             {'acceso':'/leer','literales':[f'Informe  Ñuñoa {i:02d}.pdf']}),
            ('archivo_copiar', f'copia archivo "Dato q {i:02d}.py" a "Copia po {i:02d}.py"',
             {'acceso':'/copiar','literales':[f'Dato q {i:02d}.py',f'Copia po {i:02d}.py']}),
            ('adjuntos_consultar', adjuntos[i%5], {'acceso':'/adjuntos'}),
            ('estado_diagnostico', estados[i%5], {'acceso':'/diagnostico'}),
            ('ayuda', ayuda[i%5], {'acceso':'/ayuda'}),
            ('tiempo', horas[i%5], {'acceso':'/hora'}),
            ('codigo_guia', f'hazme una guía para debug del script "Caso{i:02d}.py" en Ubuntu', {'guia':True}),
            ('conversacion_confirmacion', confirmaciones[i%10], {'confirmacion':'aceptar'}),
        ]
        for j, (f, p, e) in enumerate(bases):
            modismo = (i+j) % 2 == 0
            tipeo = (i+j) % 2 == 1
            # Para familias sin nombre variable añadimos cortesía diversa, no sufijos ID.
            if modismo: p = _envolver(p, i+j)
            else: p = _typo(p, i+j)
            if f == 'conversacion_confirmacion':
                # Las confirmaciones no usan cortesía de acción, pero mantienen énfasis.
                p = ['dale compa', 'ya po, empecemos', 'sipo, adelante', 'obvio, sigamos',
                     'sí te confirmo, continuemos'][i%5] if modismo else ['si t confirmo', 'sii, empecemos',
                     'yaaa po', 'daleee', 'ok, sigamos'][i%5]
                p += ['',' porfa',' altiro',' por favor',' po'][i//5]
            if f in {'recordatorio_listar','adjuntos_consultar','estado_diagnostico','ayuda','tiempo'}:
                # Un modificador temporal explícito cambia el enunciado y no los literales.
                p = p.replace(' po', [' ahora po', ' por favor po', ' otra vez po', ' de nuevo po', ' altiro po'][i//5],1) if modismo else p + ['', ' ahora', ' por favor', ' otra vez', ' de nuevo'][i//5]
            filas.append(_fila(f, p, e, modismo=modismo, tipeo=tipeo))

    negativas = [
        ('negativa_recordatorio', 'No crees un recordatorio llamado "NoCambiar {n}" para mañana a las 08:00.'),
        ('negativa_memoria', 'No muevas las memorias 1 y 2 al proyecto "Quieto {n}"; quiero una explicación.'),
        ('negativa_archivos', 'No copies el archivo "Dato {n}.py" a "Salida {n}.py" todavía.'),
        ('negativa_codigo', 'No compiles "Caso{n}.java", explícame el stack trace.'),
        ('ejemplo_citado', 'El ejemplo dice "crea proyecto Ejemplo {n}". Solo quiero entenderlo.'),
        ('hipotesis', 'Si te dijera "recuérdame la prueba {n} mañana", ¿qué datos faltarían?'),
        ('informativa', 'Tengo anotado un recordatorio "Evento {n}"; no es una petición de crearlo.'),
        ('pregunta_significado', '¿Qué significa "borra el aviso {n}" en un tutorial?'),
    ]
    for i in range(160):
        f,p=negativas[i%8];p=p.format(n=i)
        mod=i%4==0;typo=i%4==1
        if mod:p='cachai, '+p+' po'
        if typo:p='xfa '+p.replace('archivo','arhcivo')
        filas.append(_fila(f,p,{'seguro':True},modismo=mod,tipeo=typo,negativo=True))

    ambiguas = [
        ('ambiguo_fecha', 'Hazme un recordatorio de "Prueba {n}" para algún día.'),
        ('ambiguo_fecha', 'Agéndame "Reunión {n}" en un rato.'),
        ('ambiguo_fecha', 'Recuérdame "Control {n}" y avísame dos días antes.'),
        ('ambiguo_objeto', 'Mueve eso al proyecto "Destino {n}".'),
        ('ambiguo_objeto', 'Clasifica el que hablamos al proyecto "Caso {n}".'),
        ('ambiguo_fecha', 'Recordatorio para mañana, sin decidir la hora ni el título, caso {n}.'),
        ('ambiguo_objeto', 'Pásalo a "Pendiente {n}".'),
        ('ambiguo_fecha', 'Pon un recordatorio de "Examen {n}" para el día tanto.'),
    ]
    for i in range(80):
        f,p=ambiguas[i%8];p=p.format(n=i)
        mod=i%4==0;typo=i%4==1
        if mod:p=_envolver(p,i)
        if typo:p='xfa '+p
        filas.append(_fila(f,p,{'aclarar':True},modismo=mod,tipeo=typo,ambiguo=True))

    for i in range(80):
        primero=f'busca memorias sobre "Caso {i}"'
        segundo=f'lee archivo "Anexo {i}.txt"'
        tercero=f'muestra mis proyectos'
        p=f'{primero} y luego {segundo} y después {tercero}'
        mod=i%4==0;typo=i%4==1
        if mod:p='cachai, '+p+' po'
        if typo:p='xfa '+p.replace('busca','buskame',1)
        filas.append(_fila('ordenes_encadenadas',p,{'cadena_literales':[f'Caso {i}',f'Anexo {i}.txt'],'partes':3},
                           modismo=mod,tipeo=typo,cadena=True))

    # Citas exactas de esta conversación. No se copian respuestas de otras IA,
    # credenciales ni el documento adjunto. Su rúbrica es explícita por caso.
    reales = [
        ('Jarvis Recordatorio para mañana a las 08:00 dejalo con el titulo Lapiz Rosado Incidencia',{'nombre':'crear_recordatorio','texto':'Lapiz Rosado Incidencia','fecha_canonica':'mañana a las 08:00'}),
        ('recordatorio para mañana todo el día, Lapiz Rosado Incidencia',{'nombre':'crear_recordatorio','texto':'Lapiz Rosado Incidencia','fecha_canonica':'mañana todo el día'}),
        ('SI te confirmo empecemos',{'confirmacion':'aceptar'}),
        ('empecemos con el 1',{'continuacion':True}),
        ('empecemos a hacer el caso',{'continuacion':True}),
        ('reintenta',{'continuacion':True}),
        ('sigue',{'continuacion':True}),
        ('recuerdos sin clasificar ordenados del mas antiguo al mas nuevo (por fecha)',{'nombre':'listar_memorias','proyecto':'sin_clasificar','orden':'antiguos'}),
        ('agrega los recuerdos 1,2,3,4,5 al proyecto Segundo Cerebro',{'nombre':'clasificar_recuerdos','numeros':[1,2,3,4,5],'proyecto':'Segundo Cerebro'}),
        ('muevelo a Proyecto Segundo Cerebro',{'aclarar':True}),
        ('agrega 1 al proyecto segundo cerebro',{'nombre':'clasificar_recuerdos','numeros':[1],'proyecto':'Segundo Cerebro'}),
        ('Muestrame mis proyectos de segundo cerebro',{'acceso':'/proyectos'}),
        ('muestrame los sin clasificar',{'nombre':'listar_memorias','proyecto':'sin_clasificar'}),
        ('me los puedes listar con la fecha y hora?',{'sin_accion':True}),
        ('explicame esto',{'continuacion':True}),
        ('haceme una guia de como hacerlo',{'guia':True,'continuacion':True}),
        ('puedes ver mi segundo cerebro?',{'sin_accion':True}),
        ('a que te refieres con que no puedes verlo directamente?',{'sin_accion':True}),
        ('mi saaaaan no significa eso',{'sin_accion':True}),
        ('sabes q significa si sabes dilo en la respuesta',{'sin_accion':True}),
        ('no he puesto el comando /no_think',{'seguro':True}),
        ('dame una explicacion de que es',{'guia':True}),
        ('hola',{'sin_accion':True}),
        ('olvida eso empezaremos en otras cosas',{'sin_accion':True}),
        ('puedes revisar desde segundo cerebro lo que hable con caude hace poco?',{'sin_accion':True}),
        ('aah y no hay forma de guardaer las conversaciones?',{'sin_accion':True}),
        ('hubo un problemas con los threads no te llegan los mensajes',{'sin_accion':True}),
        ('perfecto, sigamos mejorando jarvis',{'sin_accion':True}),
        ('mas mejoras a jarvis hace',{'sin_accion':True}),
        ('añade mas mejoras',{'sin_accion':True}),
        ('hable un poco con el chat y mira',{'sin_accion':True}),
        ('la tecla copilot no me habre el original3',{'sin_accion':True}),
        ('El chat gráfico nuevo',{'sin_accion':True}),
        ('puedes revisar porque salen tantas conversaciones, cuando clickee un mensaje o recuadro que me muestre la informacion que contiene idealmente textual',{'sin_accion':True}),
        ('Hola jarvis porque no estas funcionando con ollama?',{'acceso':'/diagnostico'}),
        ('Pueden ser ambos ? para asi tener mayor amplitud',{'sin_accion':True}),
        ('como hago para darle la clave a la api y pueda conectarse con otras ias como chat gpt, gemini, claude, deepseek lo que sea',{'sin_accion':True}),
        ('Sí, al fallar y cuando active Complementar con IA',{'sin_accion':True}),
        ('hola jarvis puedes consultar en internet algo?',{'sin_accion':True}),
        ('Puedes buscar cuanto cuesta un pisco mistral de 750cc',{'sin_accion':True}),
        ('perfecto, como configuramos el gemini que pueda ser gratis ?',{'sin_accion':True}),
        ('terminaste?',{'sin_accion':True}),
        ('si le pido eso a jarvis me hara el codigo paso a paso o se perdera?',{'sin_accion':True}),
        ('y no podrias mejorar jarvis para que si pueda hacerlo',{'sin_accion':True}),
        ('continua donde lo dejaste',{'continuacion':True}),
        ('puedes guardar toda la informacion en segudno cerebro en el proyecto Jarvis',{'sin_accion':True}),
        ('Si te quedo algo pendiente termina',{'continuacion':True}),
        ('tambien diviste la informacion de jarvis en el segundo cerebro para que la forma de leerlo sea con menos tokens',{'sin_accion':True}),
        ('y ya accesible para cualquier ia, esta sincornizado?',{'sin_accion':True}),
        ('Jarvis me ayudas a empezar a eso esto en kotlin Android Studio',{'sin_accion':True}),
        ('Jarvis tu puedes acceder a un documento si te paso la ruta y leer su contenido?',{'sin_accion':True}),
        ('como debo decirte la ruta',{'sin_accion':True}),
        ('te estoy pasando la ruta',{'sin_accion':True}),
        ('puedes ir a la ruta descargas del pc',{'sin_accion':True}),
        ("no es 'Descargas' la ruta correcta es 'Downloads'",{'seguro':True}),
        ('puedes listarme los archivos que contiene esa carpeta',{'sin_accion':True}),
        ('puedes leer el archivo por partes Formato_B_Caso_DSY1105_RETAIL_CONTEO_ACCESOS_ok.pdf',{'sin_accion':True}),
        ('esa es la ruta',{'sin_accion':True}),
        ('puedes analizar el documento verdad?',{'sin_accion':True}),
        ('necesito este caso hacerlo en android studio porque tengo que presentarlo y explicar todo el codigo',{'sin_accion':True}),
        ('pero eso es lo que necesito hacer en android studio',{'continuacion':True}),
        ('puedes usar todos los tokens queme quedan 27% para entrenar a jarvis con vocabulario de como decir las cosas ejemplo, podria decirle que me haga un recordatorio de pruieba para el dia tanto y que me empiece a aparecer en desktop 2 dias antes de la fecha de prueba y mas cosas asi de como le hablo, puedes basarte en como te hablo a ti o como le hablo al chat gtp con las conversaciones',{'seguro':True}),
        ('puedes revisar esto',{'sin_accion':True}),
        ('muéstrame el último recuerdo que segundo cerebro guardó y en qué proyecto lo puso',{'nombre':'consultar_ultimo_recuerdo'}),
        ('puedes verificar el clima en santiago',{'sin_accion':True}),
        ('no guardes',{'seguro':True}),
        ('no compiles',{'seguro':True}),
        ('no uses el documento',{'seguro':True}),
        ('dime que cosas puedo mejorar de ti',{'sin_accion':True}),
        ('agrega las memorias 1,2,3,4,5 al proyecto Segundo Cerebro',{'nombre':'clasificar_recuerdos','numeros':[1,2,3,4,5],'proyecto':'Segundo Cerebro'}),
        ('recuerdos sin clasificar ordenados del mas antiguo al mas nuevo (por fecha)',{'nombre':'listar_memorias','proyecto':'sin_clasificar','orden':'antiguos'}),
        ('no modifiques argumentos',{'seguro':True}),
        ('dale',{'confirmacion':'aceptar'}),
        ('ya po',{'confirmacion':'aceptar'}),
        ('el segundo',{'continuacion':True}),
        ('la última',{'continuacion':True}),
        ('eso',{'continuacion':True}),
        ('vuelve al caso de la tienda',{'continuacion':True}),
        ('como dijimos',{'continuacion':True}),
        ('Continua',{'continuacion':True}),
    ]
    # Una cita repetida conserva un solo caso; completar con otras expresiones
    # explícitas incluidas en la misión del usuario, también tomadas literalmente.
    vistos=set()
    reales=[(p,e) for p,e in reales if not (p in vistos or vistos.add(p))]
    for p,e in [('mañana en la mañana',{'sin_accion':True}),('todo el día',{'sin_accion':True}),
                ('avísame 2 días antes',{'nombre':'modificar_recordatorio','anticipacion_dias':2}),
                ('y después?',{'continuacion':True}),('lo anterior',{'continuacion':True}),
                ('ese caso',{'continuacion':True}),('adelante',{'confirmacion':'aceptar'})]:
        if len(reales)>=80:break
        if p not in vistos:reales.append((p,e));vistos.add(p)
    assert len(reales)>=80,len(reales)
    for p,e in reales[:80]:
        filas.append(_fila('casos_usuario',p,e,real=True,negativo=bool(e.get('seguro'))))
    for i,c in enumerate(filas):c['id']=f'V6H_{i+1:04d}'
    # Algunas expresiones coloquiales cortas se repiten al combinar prefijos;
    # las combinaciones son distintas por significado o énfasis, no por espacios.
    assert len(filas)==800,len(filas)
    assert len({c['pedido'] for c in filas})==800,'Hay frases repetidas'
    anterior=json.loads((BASE/'documentacion/CORPUS_VOCABULARIO_NUEVO_2026-10-14.json').read_text())['frases']
    canon=lambda p:' '.join(p.casefold().split())
    viejos={canon(c['pedido']) for c in anterior}
    assert not [(c['id'],c['pedido']) for c in filas if canon(c['pedido']) in viejos], 'Coincide con corpus anterior'
    return dict(version=1, criterios={
        'estructura':'Nombre de intención y todos los literales/campos esperados deben coincidir.',
        'fechas':'Se compara el instante de Chile con una base fija 2026-10-14 12:00.',
        'negativos':'Ninguna vía de intérprete produce una mutación; no se llama al modelo.',
        'ambiguos':'Debe producir una sola aclaración, sin operación.',
        'confirmaciones':'Solo aceptación conversacional; el corpus no la trata como permiso.',
        'cadenas':'Tres pasos explícitos fuera de comillas; literales intactos.',
        'real':'Citas de esta conversación o frases explícitas de la misión; sin respuestas ni secretos.',
        'alcance':'Evaluación estructurada y de seguridad, sin Ollama ni ejecución de acciones.'}, frases=filas)

def congelar():
    REPORTES.mkdir(parents=True,exist_ok=True)
    destino=REPORTES/'corpus_6h_vocabulario_v1.json'
    raw=(json.dumps(construir(),ensure_ascii=False,indent=2)+'\n').encode()
    if destino.exists() and destino.read_bytes()!=raw:
        raise ValueError('El corpus V1 ya está congelado y difiere; conserva el original.')
    destino.write_bytes(raw);destino.chmod(0o600)
    sha=hashlib.sha256(raw).hexdigest()
    (REPORTES/'corpus_6h_vocabulario_v1.sha256').write_text(sha+'  '+destino.name+'\n')
    return sha

if __name__=='__main__':print(congelar())
