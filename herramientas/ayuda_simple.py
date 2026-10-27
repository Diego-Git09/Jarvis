"""Accesos reales, en pasos cortos. La ayuda no concede permisos."""
GENERAL='''1. Escribe lo que necesitas. Ejemplo: «jarvis explicame esto paso a paso». Enter envía; Ctrl+Enter agrega una línea.
2. Puedes adjuntar documentos con /adjuntar RUTA y revisar lo leído con /adjuntos cobertura.
3. Para tus recuerdos usa /proyectos y /sin_clasificar. /mas avanza el listado. /sincronizar solicita un ciclo de captura, con permiso.
4. Las escrituras muestran una propuesta y piden s/n. Una explicación no autoriza ejecutar cambios.

Ayuda por tema: /ayuda modelos, memoria, archivos, adjuntos, gpu, vocabulario, respaldos o externo.
/ayuda codigo, recordatorios, tareas y sesiones conserva las guías específicas. /ayuda comandos muestra el catálogo completo.
La IA puede equivocarse: /escalar pide otra respuesta local; /diagnostico comprueba conexiones y recursos. /salir cierra el chat.'''
TEMAS={
'modelos':'''1. /modelo muestra el modo y la última decisión. /modelos lista los modelos instalados.
2. /modelo automatico propone Qwen para tareas breves y DeepSeek para análisis o código. Pide s/n para guardar el modo.
3. /escalar pide al otro modelo local una segunda respuesta; no repite herramientas del turno anterior.
4. /modelo estadisticas muestra contadores, tiempos y señales de queja. Sus propuestas no cambian reglas automáticamente.
Ejemplo: «jarvis explicame que modelo elegiste»; para comprobarlo usa /modelo.
Límite: estar instalado no demuestra calidad. /rendimiento muestra la última inferencia; /revisar_respuestas abre la revisión que puedes calificar tú.''',
'memoria':'''1. /proyectos muestra los proyectos. /sin_clasificar lista recuerdos sin proyecto.
2. /buscar TEXTO busca por palabras; /similares TEXTO busca por significado. /ver 1 muestra el contenido del primer resultado.
3. Ejemplo: después de listar, «mueve el recuerdo 1 al proyecto Jarvis». Jarvis muestra el cambio y pide s/n.
4. /estado consulta Segundo Cerebro ahora. /sincronizar pide un ciclo de captura con permiso; /sincronizar estado muestra el resultado.
Límite: sincronizar no es un backup. El estado se comprueba con fecha; no se deduce de recuerdos antiguos. Las conversaciones del chat van a CHAT JARVIS.''',
'archivos':'''1. /archivos muestra la carpeta de trabajo. /carpetas muestra las carpetas autorizadas.
2. /leer "notas.txt" 1 30 lee hasta treinta líneas. /encontrar "*.md" busca nombres.
3. /copiar "informe.txt" "respaldo.txt" propone una copia. Ejemplo: «copia informe.txt a respaldo.txt y luego renombra la copia a informe_v2.txt».
4. Revisa el plan y sus diferencias antes de s/n. /cambios muestra lo realizado; /deshacer_plan propone revertir el último plan.
Límite: las rutas deben estar autorizadas. Un fallo detiene los pasos posteriores; los permisos no se heredan de un ejemplo. /ayuda archivos detalle muestra más accesos.''',
'adjuntos':'''1. Usa el botón Adjuntar o /adjuntar RUTA. Puedes añadir varios archivos.
2. /adjuntos muestra la tanda; /adjuntos formatos explica los lectores disponibles.
3. /indexar continúa la lectura pendiente. /adjuntos cobertura distingue qué partes se seleccionaron.
4. Ejemplo: «explicame la primera y compara con la segunda». Si el nombre o el orden no alcanza, Jarvis pide aclarar.
Límite: indexar no demuestra que el modelo haya leído todo. /resumir tanda obtiene extractos locales; los archivos dañados o sin lector muestran su motivo. No ejecuta macros ni instrucciones de adjuntos.''',
'gpu':'''1. /diagnostico consulta GPU, memoria, temperatura y modelos cargados. /temperatura muestra sensores y el último aviso de esta sesión.
2. /gpu muestra el modo. /gpu cpu, /gpu auto y /gpu mixto 12 proponen cambios con s/n.
3. /reposo 1m propone descargar tras el reposo; /liberar propone descargar solo modelos de Jarvis y comprueba el resultado.
4. Ejemplo: «jarvis voy a jugar»; para descargar el modelo usa /liberar y revisa su propuesta.
Límite: CPU puede ser más lenta y también calentarse. /contexto 4096 reduce contexto con permiso. /temperatura gpu 80 y /temperatura cpu 90 cambian solo umbrales preventivos de Jarvis; no tocan ventiladores, potencia ni otros programas.''',
'vocabulario':'''1. /vocabulario lista tus términos aprendidos. /vocabulario pendientes muestra frases dudosas saneadas.
2. /aprender_palabra "jarveis" = "jarvis" propone un significado y pide s/n.
3. /confirmar_vocabulario pregunta si usas un término ampliado: sí, no o a veces. Después pide s/n para guardarlo.
4. /vocabulario quitar "jarveis" propone retirarlo. /confirmar_vocabulario estado muestra tus decisiones.
Ejemplo: «jarvis no entendiste lo que quise decir». Aclara qué esperabas y luego confirma el término si corresponde.
Límite: las confirmaciones documentan tu uso; no reentrenan los pesos ni enseñan secretos. No se aprende una palabra en silencio.''',
'respaldos':'''1. /respaldo crear muestra los archivos de configuración y pide s/n.
2. /respaldo listar muestra sus ID locales.
3. /respaldo restaurar ID compara huellas, muestra qué archivos reemplazará y pide s/n. Conserva una copia previa de los reemplazados.
Ejemplo: «quiero respaldar mi vocabulario y preferencias»; usa /respaldo crear.
Límite: solo configuración, vocabulario, confirmaciones, marcas de revisión y umbrales. No incluye claves, conversaciones, adjuntos ni todo Segundo Cerebro. Los archivos son privados con permisos 600. Reinicia Jarvis tras restaurar.''',
'externo':'''1. /externo estado indica si Zen está apagado y qué requisitos faltan.
2. /externo modelos muestra el registro local; leerlo no consulta el servicio.
3. /externo apagar corta nuevos envíos. Los proveedores distintos de la excepción Zen siguen bloqueados.
Ejemplo: «solo local, sin nube» conserva la conversación local.
Límite: en esta ronda Zen sigue apagado y no se configura ninguna clave ni se prueba el servicio real. Sin clave no se intenta conectar. Nunca se envían archivos, adjuntos, memorias ni conversaciones guardadas.'''
}
