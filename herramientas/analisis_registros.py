"""Explica patrones inequívocos de un log; no ejecuta ni verifica el equipo."""
import re
from comprension_peticion import solo_datos_pegados

def explicar(texto):
    if not solo_datos_pegados(texto):return None
    descripcion=paso=None
    if 'ZeroDivisionError:' in texto:
        descripcion='Python intentó dividir por cero. El traceback señala dónde ocurrió; la última línea suele indicar el tipo de excepción.'
        paso='Revisa el divisor en la línea indicada y el resultado que esperabas. Todavía no hace falta ejecutar ni cambiar nada.'
    elif 'ModuleNotFoundError:' in texto:
        descripcion='El intérprete no encontró un módulo. Puede faltar en ese entorno, tener otro nombre o estar fuera de su ruta de búsqueda.'
        paso='Comprueba qué intérprete usa el proyecto y revisa su lista de dependencias. Como lectura opcional: python3 -m pip list. No instales un paquete solo porque su nombre aparezca en un log.'
    elif 'SyntaxError:' in texto and re.search(r'colon|dos puntos|expected.*:',texto,re.I):
        descripcion='Python señala un error de sintaxis: faltan dos puntos al final de una cabecera como for, if o def.'
        paso='Lee la línea indicada. Una forma válida de un ejemplo es «for n in range(2): print(n)». Esto es texto; no se ejecutó.'
    elif re.search(r'expected\s+(?:integer|int)\b.*(?:received|got)\s+text',texto,re.I):
        descripcion='El programa esperaba un número entero y recibió texto. El registro por sí solo no permite saber qué archivo o campo lo originó.'
        paso='Revisa el valor de entrada y el tipo exigido por ese campo. Si falta el contexto, comparte la línea o formulario donde se envía el dato.'
    elif re.search(r'Tests run:\s*\d+.*Failures:\s*[1-9]',texto):
        descripcion='La ejecución registró al menos una prueba fallida. Haber ejecutado pruebas no acredita que todas pasaran.'
        paso='Lee la comparación entre esperado y obtenido y la prueba que falló antes de cambiar el código.'
    elif re.search(r'(?m)^\S+@\S+[:~].*\$\s*rm\b',texto):
        descripcion='El texto incluye una orden de borrado. No se ejecutó aquí. No se puede saber por este registro si la ruta existe ni qué habría ocurrido en otro equipo.'
        paso='Comprueba primero qué ruta se pretendía usar y qué respaldo existe. Pegar una orden no autoriza ejecutarla.'
    elif 'no such table:' in texto:
        descripcion='SQLite no encontró esa tabla en la conexión consultada. Puede ser otra base, otro nombre o una migración pendiente.'
        paso='Revisa el archivo de base elegido y su esquema con una lectura. No crees la tabla a ciegas.'
    elif 'Permission denied' in texto:
        descripcion='La operación fue rechazada por permisos. No demuestra que el archivo esté dañado o que no exista.'
        paso='Revisa la ruta y sus permisos de lectura. No uses sudo ni cambies permisos como primer paso.'
    elif 'command not found' in texto:
        descripcion='La terminal no encontró ese programa en su ruta de búsqueda. Esto no prueba por sí solo que esté sin instalar.'
        paso='Revisa el nombre y dónde está instalado. Después comprueba si esa carpeta forma parte de PATH.'
    elif 'Memoria GPU:' in texto and 'Temperatura:' in texto:
        m=re.search(r'Memoria GPU:\s*(\d+) MiB de (\d+) MiB.*Temperatura:\s*(\d+)\s*C',texto,re.S)
        if m and int(m[2])>0:
            descripcion=f"El registro dice {m[1]} de {m[2]} MiB de GPU ({100*int(m[1])/int(m[2]):.1f} %) y {m[3]} °C. Es una muestra pegada, no una lectura actual ni una prueba de sobrecalentamiento."
            paso='Como lectura actual opcional puedes usar /diagnostico o nvidia-smi. Un solo valor no explica una caída de rendimiento.'
    if not descripcion:return None
    return '1. '+descripcion+'\n2. '+paso+'\n3. No ejecuté el registro ni modifiqué archivos.'
