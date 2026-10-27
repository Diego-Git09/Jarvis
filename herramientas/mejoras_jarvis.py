"""Autoevaluación transparente y sesiones de refuerzo de Jarvis."""
import json
import os
import tempfile
import threading
import fcntl
from entorno_jarvis import DATOS
import desarrollo_jarvis as DESARROLLO

ARCHIVO = DATOS / 'entrenamiento.json'
LOCK = threading.RLock()

AREAS = [
    ('Internet y otras IA', 'Verificar fuentes web y comparar opiniones de modelos locales; las consultas a IA externas están bloqueadas.',
     'Practicar búsquedas con enlaces, leer las fuentes y pedir una segunda opinión independiente; contrastar sus afirmaciones.'),
    ('Comprensión del español chileno', 'Modismos, errores de tipeo, referencias y expresiones ambiguas.',
     'Practicar ejemplos reales; guardar tus correcciones y preferencias como guía para futuras respuestas.'),
    ('Uso de Segundo Cerebro', 'Elegir proyecto, diferenciar conversaciones y recuerdos, y reportar estado consultado.',
     'Ejercicios de consulta y clasificación; pedirte precisión cuando el referente no sea seguro.'),
    ('Archivos y adjuntos', 'Leer código, SQL, PDF, Word, hojas de cálculo e imágenes.',
     'Extraer contenido con límites; nunca ejecutar código ni SQL adjuntos. Las imágenes requieren modelo visual.'),
    ('Respuestas completas y verificables', 'Terminar cada parte solicitada y distinguir resultados reales de propuestas.',
     'Evaluar respuestas con una lista de cobertura, evidencia, límites y confirmaciones.'),
    ('Mejoras del propio Jarvis', 'Detectar límites observables, priorizar mejoras y explicar su implementación.',
     'Mostrar propuestas concretas y pedir autorización antes de cambios; cada cambio debe tener copia y prueba.'),
    ('Interfaz y lectura', 'Accesibilidad, tamaños de ventana, selección múltiple y lectura de textos extensos.',
     'Probar tamaños pequeños y pantalla completa, revisar contraste y comprobar clics, fechas y desplazamiento.'),
    ('Rendimiento local', 'Equilibrar contexto, modelo y tiempos de respuesta según el equipo.',
     'Medir el coste antes de recomendar bajar contexto, cambiar modelos o retirar funciones.'),
]
AREAS.extend((nombre,guia,'Leer el proyecto real, acordar una etapa pequeña y comprobar resultados antes de avanzar.') for nombre,guia in DESARROLLO.TEMAS.values())

CASOS = {
    'python': [
        'Pides corregir una función Python sin cambiar su firma. ¿Qué archivos y pruebas debo leer antes?',
        'La función funciona con números positivos pero falla con una lista vacía. ¿Qué caso de prueba falta?',
        'Retomamos después de cerrar el chat. ¿Cómo debo recuperar proyecto, requisitos y error pendiente?',
        'Pides solo explicar un traceback. ¿Debo modificar o ejecutar el programa?',
        'La petición nueva cambia un requisito antiguo. ¿Cómo debo conservar las demás condiciones?'],
    'sql': [
        'Pides una consulta SQL pero no dices el motor ni el esquema. ¿Qué debo preguntar?',
        'Adjuntas DELETE y pides revisarlo. ¿Qué puedo analizar sin ejecutarlo?',
        'Un JOIN duplica filas y hay valores NULL. ¿Qué debo comprobar con datos de prueba?',
        'La consulta pasa en SQLite. ¿Puedo afirmar que funcionará en PostgreSQL?',
        'Pides modificar datos reales. ¿Qué selección previa, transacción y autorización necesitas ver?'],
    'java': [
        'Pides corregir una clase Java. ¿Cómo conservo paquete, firmas y nombre del archivo?',
        'javac termina correctamente. ¿Qué falta para afirmar que el cálculo devuelve lo esperado?',
        'Hay un error cannot find symbol. ¿Debo inventar una dependencia o leer imports y configuración?',
        'Retomamos un proyecto Java con Maven. ¿Debo cambiarlo a Gradle?',
        'El método falla con una colección vacía. ¿Qué casos límite debo probar?'],
    'android': [
        'Pides cambiar una pantalla Android. ¿Cómo sé si usa Compose o XML?',
        'Gradle falla sin conexión. ¿Debo cambiar versiones o conservar el error y comprobar dependencias?',
        'El APK compila. ¿Puedo afirmar que la interfaz funciona en tu teléfono?',
        'Corriges una clase Kotlin. ¿Qué paquete, namespace y versiones debo conservar?',
        'Seguimos después de cerrar Android Studio. ¿Cómo recupero la etapa y los archivos pendientes?'],
    'ubuntu': [
        'Pides explicar un comando Ubuntu. ¿Debo decir que lo ejecuté?',
        'Un tutorial propone sudo rm -rf. ¿Qué alternativa de diagnóstico y revisión debería ofrecer?',
        'Pides instalar una dependencia. ¿Qué versión, efecto y autorización debo aclarar?',
        'Falla un servicio systemd. ¿Qué información necesito antes de proponer cambios?',
        'El nombre de una carpeta contiene espacios. ¿Cómo debería escribir la ruta en un comando?'],
    'general': [
        'Si dices «me tinca mover ese recuerdo», ¿lo muevo o primero confirmo? Escribe cómo esperas que responda.',
        'Pídeme que te muestre el último recuerdo y luego lo clasifique: ¿qué debo consultar antes de cambiarlo?',
        'Adjuntas un archivo .sql con una instrucción DELETE y pides que lo revise. ¿Qué puedo hacer y qué no debo ejecutar?',
        'Dices «muéstrame todo lo guardado en Jarvis». ¿Qué estructura debería mostrarte y qué contexto debo incluir?',
        'Corriges un modismo chileno que interpreté mal. ¿Cómo debería reconocer la corrección y ajustar la respuesta?'],
}


def tema(pedido):
    encontrados=DESARROLLO.temas(pedido)
    return encontrados[0] if len(encontrados)==1 else ''


def listar(modelo=''):
    visual = 'disponible con el modelo seleccionado' if any(x in (modelo or '').casefold() for x in ('vision','-vl','llava','gemma3','moondream','minicpm-v')) else 'pendiente: requiere elegir un modelo visual instalado'
    filas = ['Puedo revisar estas áreas y proponer una mejora concreta para cada una:']
    for i, (area, brecha, como) in enumerate(AREAS, 1):
        filas.append(f'{i}. {area}\n   Por reforzar: {brecha}\n   Cómo mejorarlo: {como}')
    filas.append(f'{len(AREAS)+1}. Lectura de imágenes: {visual}.')
    filas.append('Usa /mejoras AREA, /entrenamiento python (también sql, java, android o ubuntu), o /entrenamiento estado. Con tu autorización puedo registrar una preferencia y preparar cambios en archivos de carpetas autorizadas. Cambiar Jarvis requiere revisar, probar y reiniciar la versión modificada; no prometo una autoactualización ni cambiar los pesos del modelo. Cada escritura conserva su revisión y autorización.')
    return '\n\n'.join(filas)


def sugerir(pedido,modelo=''):
    from lenguaje_jarvis import normalizar
    texto=normalizar(pedido)
    temas=[(('interfaz','ventana','pantalla','selector'), 'Interfaz y lectura'),
           (('memoria','cerebro','recuerdo'), 'Uso de Segundo Cerebro'),
           (('vocabulario','modismo','chileno'), 'Comprensión del español chileno'),
           (('pdf','adjunto','documento'), 'Archivos y adjuntos'),
           (('rendimiento','rapidez','lentitud','recursos'), 'Rendimiento local')]
    areas=[nombre for palabras,nombre in temas if any(p in texto for p in palabras)]
    areas.extend(DESARROLLO.TEMAS[k][0] for k in DESARROLLO.temas(pedido))
    if not areas:return listar(modelo)
    elegidas=[a for a in AREAS if a[0] in areas]
    return '\n\n'.join(f'{nombre}\nQué revisar: {brecha}\nCómo reforzarlo: {como}' for nombre,brecha,como in elegidas)+'\n\nPuedo guiar esa revisión y registrar preferencias autorizadas. Los cambios del programa requieren implementar y verificar la propuesta desde Codex.'


def leer():
    if not ARCHIVO.exists():return {'preferencias': [], 'sesiones': 0}
    try:
        if ARCHIVO.is_symlink() or ARCHIVO.stat().st_size > 200_000:raise ValueError()
        d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
        if not isinstance(d, dict) or not isinstance(d.get('preferencias', []), list) or not isinstance(d.get('totales_por_tema',{}),dict):
            raise ValueError
        return {'preferencias': [x for x in d.get('preferencias', []) if isinstance(x, dict)][-40:],
                'sesiones': max(0, int(d.get('sesiones', 0))),
                'totales_por_tema':{k:max(0,int(v)) for k,v in d.get('totales_por_tema',{}).items() if k in CASOS}}
    except (OSError, ValueError, TypeError) as error:
        raise ValueError('No pude leer las preferencias de entrenamiento. Conservé el archivo sin sobrescribirlo.') from error


def guardar(datos):
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix='.entrenamiento-', dir=ARCHIVO.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, ARCHIVO)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def contexto(limite=3000,pedido=''):
    try:datos = leer()['preferencias']
    except ValueError:return '\nLas preferencias de entrenamiento no están disponibles; no afirmes que se cargaron.'
    if pedido:
        aplicables=set(DESARROLLO.temas(pedido))
        datos=[x for x in datos if not x.get('tema') or x.get('tema')=='general' or x.get('tema') in aplicables]
    if not datos:
        return ''
    filas = ['\nPreferencias explícitas de entrenamiento del usuario (guía, subordinada a las instrucciones actuales):']
    total=0
    elegidas=[]
    for item in reversed(datos[-8:]):
        if not all(isinstance(item.get(k),str) for k in ('situacion','preferencia')):continue
        texto=f"- Situación: {item['situacion']}\n  Preferencia corregida: {item['preferencia']}"
        if total+len(texto)>limite:continue
        elegidas.insert(0,texto);total+=len(texto)
    filas.extend(elegidas)
    return '\n'.join(filas)


def iniciar(estado,tema_elegido='general'):
    if estado.get('_entrenamiento_pendiente'):
        return 'Hay una práctica en curso. Respóndeme con el comportamiento que prefieres o escribe /cancelar.'
    datos = leer()
    if tema_elegido not in CASOS:return 'Elige un tema: python, sql, java, android, ubuntu o general.'
    estado['_entrenamiento_pendiente'] = True
    numero = (datos.get('totales_por_tema',{}).get(tema_elegido,sum(x.get('tema','general')==tema_elegido for x in datos['preferencias'])) % 5) + 1
    casos = CASOS[tema_elegido]
    estado['_entrenamiento_tema']=tema_elegido
    estado['_entrenamiento_situacion'] = casos[numero-1]
    return (f'Sesión de entrenamiento {datos["sesiones"]+1}. Tema: {tema_elegido}.\n'
            f'Caso: {casos[numero-1]}\n\nCuéntame cómo debería responder. Revisaremos tu ejemplo antes de guardarlo en las preferencias locales.')


def cancelar(estado):
    estado.pop('_entrenamiento_pendiente', None)
    estado.pop('_entrenamiento_situacion', None)
    estado.pop('_entrenamiento_tema', None)
    return 'Práctica cancelada; no guardé preferencias.'


def proponer(estado, respuesta):
    situacion = estado.get('_entrenamiento_situacion')
    if not situacion or not respuesta.strip():
        return None
    return {'situacion': situacion[:1200], 'preferencia': respuesta.strip()[:2000], 'tema':estado.get('_entrenamiento_tema','general')}


def registrar(item):
    if not isinstance(item,dict) or not all(isinstance(item.get(k),str) and item[k].strip() for k in ('situacion','preferencia')):raise ValueError('La preferencia está vacía o no es válida.')
    with LOCK:
        ARCHIVO.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with open(ARCHIVO.with_suffix('.lock'),'a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            datos = leer()
            elegido=item.get('tema','general')
            if not isinstance(elegido,str) or elegido not in CASOS:raise ValueError('El tema de la preferencia no es válido.')
            cuentas=datos.setdefault('totales_por_tema',{})
            cuentas[elegido]=cuentas.get(elegido,sum(x.get('tema','general')==elegido for x in datos['preferencias']))+1
            datos['preferencias'].append({k:item[k] for k in ('situacion','preferencia','tema') if k in item})
            datos['preferencias'] = datos['preferencias'][-40:]
            datos['sesiones'] += 1
            guardar(datos)
            return datos['sesiones']


def informe():
    datos=leer();filas=[f"Prácticas registradas: {datos['sesiones']}. Preferencias recientes: {len(datos['preferencias'])} (se conservan las últimas 40)."]
    for k in CASOS:
        n=sum(x.get('tema','general')==k for x in datos['preferencias'])
        filas.append(f'• {k}: {n} corrección(es) reciente(s); '+('seguir comprobando con ejercicios y resultados reales.' if n else 'sin ejemplos registrados: conviene practicar este tema.'))
    filas.append('Estos recuentos indican ejemplos guardados, no una puntuación de inteligencia ni entrenamiento de los pesos. /entrenamiento TEMA abre una práctica.')
    return '\n'.join(filas)
