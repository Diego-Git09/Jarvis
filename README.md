# Jarvis

Asistente local en español desarrollado en Python, con interfaz gráfica y modo de terminal. Utiliza Ollama para conversar con modelos locales y ofrece herramientas para trabajar con archivos, documentos y tareas.

## Estado de esta copia

Versión de preparación para portafolio. El código se copió desde la instalación local el 27 de octubre de 2026. Se instalaron las dependencias desde PyPI en un entorno virtual nuevo y se comprobaron el arranque de terminal, la ventana gráfica y una respuesta real con `qwen2.5-coder:1.5b`. La prueba usa este mismo equipo Linux; no equivale a instalar un sistema operativo nuevo. No se atribuyen aquí los resultados históricos de la instalación original.

## Funciones presentes en el código

- Chat gráfico con Tkinter y acceso desde terminal.
- Cliente de Ollama para modelos locales.
- Lectura de documentos y referencias a archivos adjuntos.
- Propuestas de cambios de archivos con confirmación.
- Tareas, recordatorios y herramientas de diagnóstico.
- Integración con un servicio independiente llamado Segundo Cerebro.

La disponibilidad de cada función depende de sus herramientas y servicios. Esta copia no incluye Segundo Cerebro, modelos de IA ni credenciales. La integración con servicios externos requiere revisión y configuración explícita.

## Requisitos

- Linux: la instalación original utiliza Ubuntu/GNOME; otros sistemas no están verificados.
- Python 3: comprobado con 3.14.4. La versión mínima compatible todavía está por determinar.
- Tkinter para la ventana gráfica.
- Ollama instalado y un modelo local disponible.
- Los complementos de `requirements.txt` para lectura documental y métricas.

## Preparación local

Desde una terminal abierta en la carpeta de este proyecto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Se comprobó la instalación de estos paquetes en un entorno virtual sin acceso a los paquetes Python del sistema. Tkinter utiliza la biblioteca incluida por la distribución de Linux. PyGObject y el llavero GNOME son opcionales para credenciales de integraciones externas; no fueron necesarios para la prueba local. La lectura de PDF mediante Poppler necesita `pdfinfo` y `pdftotext` instalados por separado. Consulta la [verificación de instalación](documentacion/INSTALACION_VERIFICADA.md) para conocer los límites.

## Inicio

Es importante definir `JARVIS_DIR` para que esta copia utilice su propia carpeta:

```bash
export JARVIS_DIR="$PWD"
python herramientas/interfaz_grafica.py
```

Para el modo de terminal:

```bash
export JARVIS_DIR="$PWD"
python herramientas/jarvis_agente.py
```

### Elegir un modelo instalado

El valor inicial `jarvis-deepseek:8b` es un alias personalizado; no se incluye ni se descarga automáticamente. Para una primera prueba con un modelo existente:

1. Comprueba que Ollama esté instalado y que tengas un modelo local descargado.
2. Abre Jarvis como se indica arriba.
3. Escribe `/modelos` para ver los nombres disponibles.
4. Escribe `/modelo NOMBRE`, sustituyendo NOMBRE por uno de esa lista. En esta comprobación se usó `/modelo qwen2.5-coder:1.5b`.
5. Escribe `/contexto 4096` para la prueba de contexto pequeño.
6. Pregunta `Solo texto. Responde únicamente con el resultado numérico de 2 + 2.`.

Si todavía no tienes modelos, debes obtener uno mediante Ollama antes de este paso. No se comprobó aquí una descarga de modelos nuevos. Los modelos grandes exigen más memoria; la prueba con uno pequeño no acredita los demás.

En Jarvis, `/ayuda` muestra los comandos y `/diagnostico` permite consultar las conexiones. No uses el proyecto con documentos privados hasta revisar su configuración y los servicios habilitados.

## Pruebas

El proyecto incluye archivos `prueba_*.py` y un ejecutor con carpetas temporales. Algunas pruebas necesitan herramientas del sistema o una sesión gráfica. El aislamiento nativo del ejecutor requiere un kernel Linux compatible con Landlock.

```bash
python herramientas/ejecutar_pruebas.py --procesos 1
```

Resultado combinado en el entorno virtual nuevo, 27/10/2026: **2760 casos aprobados y 2 omitidos**, en 169 archivos. Incluye 34 pruebas gráficas ejecutadas por separado con Tk real. Se omiten una integración externa no configurada y un caso de PDF cifrado que necesita cryptography. Consulta el [informe de instalación](documentacion/INSTALACION_VERIFICADA.md) y la [revisión previa](documentacion/COMPROBACION_PORTAFOLIO.md) para conocer el método, las correcciones y los límites. No se promete el mismo resultado en otro equipo.

## Estructura

- `herramientas/`: programa, pruebas y recursos base.
- `herramientas/modelos/`: definición de modelo para Ollama.
- `herramientas/terceros/`: componentes incluidos con sus licencias y procedencia.
- `requirements.txt`: complementos de Python.

Los datos, conversaciones, registros y respaldos de la instalación original no se incluyen. Se conservaron los avisos de licencia de terceros. La licencia del código propio está pendiente de elección.

## Próximos pasos

1. Revisar la licencia y la selección final de archivos antes de publicar.
2. Repetir la instalación en otro equipo o sistema Linux nuevo.
3. Ampliar la demostración real más allá de una pregunta sencilla.
4. Añadir capturas con datos ficticios y una demostración breve.
