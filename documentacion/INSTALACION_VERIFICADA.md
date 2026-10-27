# Instalación e inferencia verificadas

Comprobación del 27 de octubre de 2026.

## Qué se hizo

1. Se creó un entorno virtual nuevo con Python 3.14.4, sin activar el acceso a los paquetes Python del sistema.
2. Se descargaron de PyPI las cuatro versiones declaradas en requirements.txt, sin usar caché. `pip check` no encontró incompatibilidades.
3. Se copió el proyecto a un directorio temporal con un hogar de prueba y datos nuevos, sin conversaciones ni configuración de la instalación original.
4. Se inició un servidor Ollama propio en otro puerto local. Se usó el modelo qwen2.5-coder:1.5b que ya estaba descargado; no se descargaron ni crearon modelos.
5. Se preguntó «¿cuánto es 2 + 2?» mediante el cliente real: respuesta «4», generación finalizada.
6. Se envió una consulta equivalente mediante jarvis_agente.enviar_a_ollama, sin simular el controlador ni el modelo: respuesta «4», sin llamadas a herramientas.
7. Se cerró la sesión propia y se comprobó que su puerto dejó de aceptar conexiones.
8. Se comprobó arranque de terminal, ayuda y salida en modo de pruebas con datos separados del código. Esta fase no usa inferencia; la inferencia real se comprobó por separado en los pasos anteriores.

## Pruebas en el entorno nuevo

Resultado combinado: **2760 casos aprobados y 2 omitidos**, en 169 archivos. Incluye las 34 pruebas gráficas ejecutadas por separado con Tk real. Se combina una pasada completa y repeticiones de archivos afectados, sin sumar los casos repetidos.

Los dos omitidos son:

- La comprobación del servidor de Segundo Cerebro, porque no se configuró explícitamente ese proyecto externo.
- Una prueba de PDF cifrado que necesita el complemento opcional cryptography, no incluido en los cuatro requisitos actuales.

La primera pasada detectó una carrera en una prueba de cierre: el proceso desaparecía entre abrir y leer /proc/<pid>/stat. Se amplió exclusivamente la captura a ProcessLookupError, que también acredita que ese proceso ya terminó. Se conserva la comprobación de proceso ausente o zombi. Los 38 casos del archivo pasaron al repetirlos.

## Qué queda fuera de esta evidencia

Un entorno Python nuevo no equivale a otro computador o sistema operativo nuevo. Se conservaron el Python, Tkinter, bibliotecas del sistema, herramientas de Linux y binario Ollama ya instalados. No se verificó descargar modelos desde cero, otros modelos, otros sistemas ni todas las capacidades del asistente mediante inferencia real.

Una respuesta correcta a una suma acredita la conexión y el recorrido básico, no la calidad general del modelo ni tareas complejas.

No se publicaron repositorios, archivos ni cambios en GitHub. La publicación será manual por el usuario como parte del aprendizaje.

## Evidencia resumida

- RESULTADO_INSTALACION_REAL.json: versiones, respuesta real y cierre del servidor.
- RESULTADOS_ENTORNO_LIMPIO.json: resultado por archivo, con omisiones explícitas.

Los registros detallados y las carpetas temporales no forman parte del material para publicar.
