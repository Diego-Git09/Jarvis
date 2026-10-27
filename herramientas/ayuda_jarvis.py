"""Ayuda por áreas, para que la pantalla inicial siga siendo breve."""
GENERAL = '''Puedes hablarme normalmente o usar accesos directos.

Vocabulario privado: /aprender_palabra "x" = "y", /vocabulario y /vocabulario quitar "x"; cambios con permiso.
Explicaciones: /estilo simple|tecnico. Guías: /guia spring|microservicios|kotlin|oracle|linux.
Revisión de conversaciones: /revisar_fallos (solo lectura) y /novedades.
Zen opcional: /externo estado|clave|modelos|encender|apagar. Empieza apagado; nunca recibe adjuntos ni recuerdos. /externo clave usa entrada oculta, no pegues claves en el chat.

Archivos: /archivos, /leer, /info, /comparar, /encontrar, /reemplazar, /copiar, /mover.
Cambios: /cambios, /deshacer, /propuestas, /aplicar, /cancelar.
Memoria: /proyectos, /estructura [PROYECTO], /recuerdos, /buscar, /similares, /ver, /ultimo_recuerdo, /ultima_conversacion.
Guardado explícito: «Guarda un recuerdo en Segundo Cerebro, proyecto existente Jarvis.» seguido de «Título: ...» y «Contenido:» en otra línea. Muestra el texto y pide permiso.
Mejoras: /mejoras, /entrenamiento.
Documentos: /adjuntar "RUTA", /indexar, /adjuntos formatos|recursos, /resumir tanda [generado], /rango_excel.
Estado para IA: /estado_ia. Limpieza propuesta: /limpieza. Frases por revisar: /vocabulario pendientes.
Sincronización: /sincronizar, /sincronizar estado.
Navegación: /mas, /anterior, /pagina, /actualizar, /tamano.
Sesiones: /guardar, /sesiones, /continuar, /nuevo.
Tareas: /anotar, /tareas, /hecho, /reabrir, /prioridad, /editar_tarea, /buscar_tareas.
Ajustes: /config, /modo, /modelo, /modelos, /timeout SEGUNDOS|auto, /reposo, /liberar, /gpu cpu|auto|mixto N.
Potencia: /perfil rapido|equilibrado|maximo; /ollama_url URL (prueba y guarda el destino).
Revisión: /diagnostico, /rendimiento, /contexto, /ultima_accion.
Servicio local: /ollama muestra conexión y quién lo inició; /ollama reintentar recupera el inicio automático. Solo se cierra el servidor iniciado por Jarvis, al salir de su última sesión.
Utilidades: /calcular, /hora, /pegar. Exportar: /exportar_tareas, /exportar_sesion.
Escritorio: /recordatorios, /recordar, /editar_recordatorio, /posponer_recordatorio, /eliminar_recordatorio, /completar_recordatorio, /escritorio.
Acceso personal: /carpetas, /autorizar_carpeta RUTA, /revocar_carpeta RUTA.
Internet y otras IA: /internet, /web, /clima, /ias, /preguntar_ia, /ia_externa.
/salir cierra Jarvis.

/ayuda archivos|memoria|mejoras|sesiones|tareas|ajustes|utilidades|internet|recordatorios muestra ejemplos.
Las modificaciones en archivos y memorias muestran el cambio y requieren tu autorización.'''

TEMAS = {
'codigo': '''Desarrollo con etapas persistentes, separado de los proyectos de Segundo Cerebro:
/codigo iniciar NOMBRE | CARPETA | OBJETIVO [| PDF] · inicia/adopta la carpeta con autorización.
/codigo · etapa actual, archivos reales y errores pendientes.
/codigo continuar · pide a Qwen trabajar en el próximo archivo de la etapa.
/codigo proyectos · desarrollos guardados; /codigo retomar NOMBRE · vuelve a uno.
/codigo probar java|android|tests_android|sintaxis · comprobación real; Gradle pide permiso y usa --offline.
/codigo probar tests_python · ejecuta unittest con autorización; cero pruebas no acredita éxito.
/codigo probar sql|tests_sql · SQLite en memoria; tests_sql compara pruebas_sql.json. No demuestra otros motores.
/codigo probar android_online · permite descargar dependencias de Gradle solo con tu autorización.
/codigo error MENSAJE · conserva el error hasta una comprobación correcta.
/codigo cerrar · deja de usar el desarrollo activo sin borrarlo.
También «continúa con el código» o «corrige este error de MainActivity.kt».
Las etapas requieren archivos concretos y una comprobación. Sintaxis no acredita compilación Android.
El plan se guarda con actualizar_plan_codigo. Las escrituras muestran código/diff y mantienen deshacer.
No se instalan SDK ni dependencias automáticamente. Si faltan, conserva el error y permite corregirlo.''',
'recordatorios': '''«Recuérdame comprar pan mañana a las 9» crea un recordatorio de escritorio.
«Crea un recordatorio para tomar agua siempre» lo mantiene visible.
«Hazme un recordatorio de prueba para el 20 de octubre y que aparezca dos días antes» separa evento y aviso.
«Me gustaría que me hagas un recordatorio…» y «Jarbvis, puedes…» también se interpretan.
Puedes anticipar por días, horas o minutos, y decir horas como «nueve y media».
«Avísame tres días antes» modifica una nota claramente seleccionada; «ponlo siempre» cambia su visibilidad.
Si «cámbialo para el 25» puede referirse al evento o al aviso, Jarvis pregunta cuál.
/recordar Comprar pan | mañana a las 09:00 · forma directa con fecha.
/recordatorios · lista los números; /escritorio abre el panel con todos, incluidos los futuros.
«Modifica el recordatorio 1 comprar pan y leche» cambia el texto conservando su fecha.
«Pospone el recordatorio 1 para el viernes a las 18:00» cambia cuándo aparece.
/posponer_recordatorio 1 siempre · vuelve a hacerlo permanente.
«Elimina el recordatorio 1» o /eliminar_recordatorio 1 lo retira del panel.
/completar_recordatorio 1 lo marca como hecho.
Las fechas usan Chile; sin hora se usa 09:00. Siempre visible significa hasta completarlo o eliminarlo.
El panel sigue funcionando al cerrar el chat y se inicia al entrar en tu sesión de escritorio.
Si el computador estaba apagado, aparece cuando vuelvas a iniciar sesión; no enciende el PC.
También puedes crear, editar, posponer y completar desde el botón «Recordatorios».
Su editor permite «Evento con aviso anticipado» y un fin opcional de visibilidad.
Guía de frases: ~/Jarvis/documentacion/PROBAR_VOCABULARIO_JARVIS.md.''',
'internet': '''/internet BÚSQUEDA · resultados con fuentes y hora; /web https://URL · lectura de una página.
También «Puedes buscar cuánto cuesta un pisco Mistral de 750cc en Chile» o «Averigua quién inventó el transistor».
Las búsquedas públicas y el clima no necesitan una clave de IA ni saldo de API. Si falla el resumen local, se conservan las fuentes obtenidas.
/clima Santiago · clima actual con fuente; también «¿Va a llover mañana en Santiago?».
/ias · modelos locales disponibles; las consultas a IA externas están bloqueadas.
/preguntar_ia MODELO | PREGUNTA · otra opinión de un modelo local instalado.
/ia_externa · acceso bloqueado por la política local.
«Pregúntale a DeepSeek PREGUNTA» usa jarvis-deepseek:8b en Ollama local, sin API.
Si falla el modelo antes de usar herramientas, Jarvis prueba el otro modelo local.
«Complementar con modelo local» añade una opinión independiente; consulta solo la pregunta actual.
Las búsquedas públicas y el clima usan Internet; las preguntas generativas no se envían a servicios de IA externos.''',
'archivos': '''Archivos en ~/Jarvis/trabajo y carpetas personales autorizadas:
Puedes arrastrar varios archivos al chat o al cuadro de escritura. Enter envía; Ctrl+Enter añade una línea.
/adjuntos formatos muestra qué extrae cada lector y qué queda solo en metadatos.
/adjuntos pendientes lista cada fuente parcial, pendiente o ilegible y su motivo.
/adjuntos cobertura muestra los archivos con trozos seleccionados en la última consulta y los que quedaron fuera. La selección no acredita envío o lectura completa.
/adjuntos recursos muestra los plazos, el buffer y el techo de memoria virtual del proceso lector (no de todo Jarvis).
DOC/XLS/PPT antiguos: requieren LibreOffice aislado y /adjuntos recursos mb_proceso=512 con permiso. Con256 MiB quedan en metadatos; XLS con fórmulas o vínculos se rechaza.
/adjuntos analizar "datos.csv" desde=1 hasta=10 buscar="texto" calcula estadísticas locales sin indexar todo, hasta 500 MiB.
/resumir tanda conserva la síntesis extractiva. /resumir tanda generado [1 a 12] solicita un resumen local con citas y caché.
El resumen generado usa una selección del índice; no acredita haber leído todo el original. «Detener proceso» conserva los trozos confirmados.
Al reanudar con /indexar en el chat gráfico también verás progreso y podrás detener el lector.
La búsqueda combina texto y vectores locales; puedes indicar nombre/ruta y excluir una fuente con «no uses archivo.pdf».
Si fallan los embeddings, conserva el texto. /indexar completa los vectores pendientes sin duplicar trozos.
El lector actual exige /indexar en tandas anteriores. Una continuación sensible omitida o una codificación mixta se declara parcial.
/resumir tanda comprueba versión, autorización y huella antes de mostrar los extractos guardados.
Comprueba frases detectadas de condiciones y asuntos pendientes; ante una omisión conserva extractos con aviso. No es verificación universal de hechos.
La preparación de varios adjuntos ocurre en segundo plano. Una fuente corrupta se excluye con aviso; cancelar conserva la selección anterior.
SQLite muestra esquemas y muestras: hasta20 filas por tabla y1000 caracteres por celda, sin cargar completos los textos extensos. Las celdas que no admiten lectura por partes se indican como omitidas.
Los archivos con contraseña o daños muestran el motivo conocido y permiten continuar con las demás fuentes.
/carpetas muestra los accesos. Puedes usar rutas completas o ~/Documentos/notas.txt.
/autorizar_carpeta "/media/usuario/Mi disco" añade otra carpeta, con autorización y sin cambiar las rutas relativas.
El botón «Carpetas» permite elegir y administrar accesos. Las escrituras mantienen propuesta, comprobación y deshacer.
/archivos [CARPETA] · listar carpetas y archivos.
/leer "notas.txt" [INICIO] [CANTIDAD] · leer por líneas.
También puedes pegar /home/usuario/Downloads/documento.pdf directamente; conserva mayúsculas y tildes.
PDF: /leer RUTA [PÁGINA] lee una página por tramos; /mas_documento o «continúa leyendo» sigue al siguiente tramo/página.
Word, Excel y PowerPoint extraen texto local por tramos. No ejecutan macros ni necesitan una API externa.
Tras listar una carpeta, /leer nombre.pdf usa ese archivo del listado comprobado. También admite nombres entre backticks.
/buscar_archivos TEXTO · buscar dentro de los archivos.
/encontrar "*.md" [CARPETA] · buscar por nombre.
/info RUTA · tamaño, tipo y fecha real de modificación.
/comparar PRIMERO SEGUNDO · comparar dos archivos de texto.
/carpeta "carpeta nueva" · crear una carpeta.
/copiar "origen.txt" "copia.txt" · copiar sin sobrescribir.
/mover "origen.txt" "nuevo nombre.txt" · mover o renombrar.
/reemplazar "notas.txt" "texto actual" "texto nuevo" [--todos].
/cambios · ver cambios reales; /deshacer [N] · deshacer un cambio.
/propuestas, /aplicar [N], /cancelar · revisar, aplicar o descartar propuestas.
Tab completa accesos y rutas sencillas; usa comillas para nombres con espacios.
También: «Cambia Comprar pan por Comprar leche en notas.txt».''',
'memoria': '''/proyectos · todos los proyectos, incluidos los vacíos.
Guardado manual explícito: primera línea «Guarda un recuerdo en Segundo Cerebro, proyecto existente Jarvis.».
Después «Título: Mi título» y «Contenido:» con el texto debajo. Se pide autorización y se comprueba el ID.
Si ya existe igual, devuelve su ID sin duplicarlo. Un guardado incierto bloquea otra escritura hasta comprobarlo.
Comprueba hasta 10000 registros paginados; si no puede terminar, no supone que el recuerdo falte.
La captura automática sigue activa por su mecanismo habitual; no hace falta guardar manualmente cada mensaje.
/recuerdos · listado; /sin_clasificar · recuerdos sin proyecto.
/buscar TEXTO · búsqueda por palabras; /similares TEXTO · por significado.
/ver N · consultar un recuerdo completo.
/ultimo_recuerdo · mostrar el último recuerdo normal, su proyecto y fecha; queda seleccionado para moverlo o corregirlo.
/ultima_conversacion · consultar la conversación más reciente; también puedes preguntar «la última conversación de Claude/Codex/Continue/Open WebUI/Jarvis».
/mas, /anterior, /pagina N · recorrer un listado.
/actualizar · consultar de nuevo conservando filtro y orden.
/tamano N · 1 a 20 elementos por página.
/proyecto NOMBRE · proyecto activo para consultas; /todos lo quita.
/estructura [NOMBRE] · árbol de proyectos, recuerdos y conversaciones; solo lectura.
/sincronizar · pedir un ciclo de captura de Segundo Cerebro (con tu autorización) y seguirlo hasta el resultado.
/sincronizar estado · cómo va o cómo terminó la última sincronización manual.
Sincronizar no es un backup: procesa un lote de mensajes, y pueden quedar pendientes.
Ejemplos: «Enséñame los proyectos», «Pasa el primero y el último a Jarvis», «Pon todos menos el segundo en Jarvis».
También puedes decir «Mueve el recuerdo 2 de sin clasificar al proyecto Jarvis». Si nombras un proyecto que todavía no existe, te preguntaré antes de crearlo.''',
'sesiones': '''/guardar NOMBRE · guardar esta conversación con tu autorización.
/sesiones · listar lo guardado; /continuar NOMBRE · recuperarlo.
/exportar_sesion "NOMBRE" archivo.md · exportar una sesión guardada al trabajo.
/contexto · ver qué turnos recibe el modelo; la conversación completa sigue disponible para guardar.
/nuevo · limpiar la conversación actual sin borrar memorias.
Las sesiones de /guardar se conservan localmente. Cada turno normal de Jarvis también se envía automáticamente a Segundo Cerebro; si no hay conexión, queda en cola local.
Las sesiones recuperadas no restauran permisos ni referencias de recuerdos anteriores.
Las referencias de recuerdos y propuestas deben consultarse otra vez después de recuperar una sesión.''',
'tareas': '''/anotar Comprar leche · añadir una tarea local.
/tareas o /pendientes · ver las pendientes.
/hecho N · completar una tarea del listado.
/tareas todas · ver también las completadas.
/reabrir N · volver a marcarla como pendiente.
/hecho uno y dos · completar varios números del listado en una operación.
/prioridad N alta|normal|baja · las tareas se muestran por prioridad.
/editar_tarea N TEXTO · cambiar el texto; /buscar_tareas TEXTO · encontrar tareas.
/exportar_tareas tareas.md · exportar todas a un archivo, con autorización.
También: «anótame una pega llamada “Comprar café”», «marca la segunda tarea como hecha» y «pon la tarea dos con prioridad alta».
Los números corresponden al último listado de tareas. Si después miraste otro listado, usa /tareas otra vez.
Conserva títulos entre comillas, incluidas “ ” y « ». Una orden citada dentro del título es texto, no otra acción.
Las respuestas de una práctica de entrenamiento se tratan como ejemplos. «Dale» no modifica tareas por sí solo.
Esta lista es independiente de Segundo Cerebro y se mantiene entre aperturas.''',
'utilidades': '''/calcular (12 + 8) * 3 · cálculo comprobado, sin ejecutar código.
/calcular 15% de 200 · porcentajes; también «cuánto es 1,5 + 2,5».
Funciones: raiz(81), abs(-3), redondear(1.5).
/hora · fecha y hora actuales en Chile.
/pegar · introducir varias líneas; /fin envía el conjunto y /cancelar lo descarta.
Las líneas pegadas se envían como una sola petición al modelo.
Los errores en un acceso producen sugerencias; nunca se ejecuta una corrección automáticamente.''',
'ajustes': '''/config · configuración actual.
«Revisa si Ollama responde» y «qué modelo tienes activo ahora» consultan el estado actual.
Una explicación como «cómo funciona Ollama», una frase citada o una negación no disparan ese diagnóstico.
/modo breve|normal|detallado · estilo de respuesta.
/contexto N · ventana explícita 4096–32768; /mensaje_completo PREGUNTA · analiza el mensaje largo entero, sin herramientas ni recortes automáticos.
Planes de archivos: separa hasta cinco pasos con «y luego». Un permiso para el plan exacto en chat y terminal; /deshacer_plan revierte con un permiso nuevo.
/escalar · segunda respuesta del otro modelo local, sin repetir herramientas.
/modelos · modelos instalados; /modelo NOMBRE · fijar uno; /modelo automatico · Qwen + DeepSeek según la tarea.
/timeout SEGUNDOS · límite manual del modelo, entre 15 y 600. /timeout auto amplía para tareas complejas.
/reposo 0|1m|5m|10m|30m|60m · guarda cuánto permanece cargado después de responder. 0 descarga al finalizar; requiere cargarlo otra vez en cada consulta.
/liberar · muestra modelos de Jarvis cargados, pide s/n, descarga RAM/VRAM y comprueba el resultado; conserva los pesos instalados.
/gpu cpu · conserva las funciones y procesa próximas inferencias con CPU/RAM (más lento). /gpu auto vuelve a permitir aceleración. /gpu mixto N descarga N capas a GPU y el resto a CPU/RAM (se valida el modelo y la memoria). Para jugar, /liberar descarga cualquier modelo GPU ya cargado.
/diagnostico · revisar Ollama, Segundo Cerebro, modelo, GPU, reposo y almacenamiento.
/rendimiento · tiempo y tokens de la última respuesta del modelo.
Los ajustes se guardan para las próximas aperturas. No se descargan modelos automáticamente.'''
}


CATALOGO_COMPLETO=GENERAL
from ayuda_simple import GENERAL,TEMAS as TEMAS_SIMPLES

def ayuda(tema=''):
    tema=tema.strip().casefold()
    if tema=='comandos':return CATALOGO_COMPLETO
    if tema in TEMAS_SIMPLES:return TEMAS_SIMPLES[tema]
    if tema.endswith(' detalle'):return TEMAS.get(tema.removesuffix(' detalle'),'Usa /ayuda para elegir un tema.')
    if tema == 'mejoras':
        return '''/mejoras · capacidades, límites observables y formas concretas de reforzar Jarvis.
/mejoras AREA · detalle de una capacidad.
/entrenamiento · práctica guiada. Describe cómo esperas que responda; Jarvis te muestra lo que guardará y pide autorización.
/entrenamiento python|sql|java|android|ubuntu · práctica de un contexto concreto.
/entrenamiento estado · temas sin ejemplos y correcciones recientes; no es una puntuación del modelo.
Las preferencias se conservan localmente como ejemplos y guía; no cambian los pesos del modelo.'''
    return TEMAS.get(tema,'No conozco ese tema. Usa /ayuda archivos, memoria, mejoras, sesiones, tareas o ajustes.') if tema else GENERAL
