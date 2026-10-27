"""Notas breves verificables para conceptos confundidos; no son acciones."""
import re
from normalizacion_entrada import vista

NOTAS=(
 (r'\b(?:que|cual)\b.{0,60}\bte (?:pedi|pregunte|solicite|dije)\b', 'El usuario pregunta por su propia petición anterior: él la pidió y tú la recibiste. Consulta el historial y responde «Me pediste ...» o «Tú pediste ...», según sus palabras exactas. No inviertas los participantes diciendo «te pedí». Si no consta la petición, aclara cuál sin inventarla.'),
 (r'\b(?:copia|copias|respaldo|respalda|seguridad)\b.*\bincremental\b', 'Una copia incremental conserva los cambios desde la última copia de esa cadena, completa o incremental. No copia todo cada vez ni compara siempre con la primera completa. Para restaurar se necesita la completa de base y los incrementales posteriores hasta el punto elegido. Una diferencial guarda los cambios desde la última completa. El tamaño y tiempo dependen de los cambios; no garantices que siempre sea menor o más rápida.'),
 (r'\bmodelo\b.*\bauto(?:matic[oa])?\b', 'La selección automática de Jarvis usa reglas del controlador: qwen3:8b para consultas breves y jarvis-deepseek:8b para análisis o código. /modelo muestra la decisión y el motivo. Explicar ese modo no cambia la configuración; /modelo automatico propone guardarlo con s/n. No equivale a elegir manualmente otro modelo.'),
 (r'\blimite de contexto\b', 'El contexto de un modelo se mide en tokens: fragmentos de texto, no caracteres ni palabras exactos. La ventana incluye instrucciones, historial, fuentes y salida reservada. Si no cabe, se selecciona o divide contenido; no se promete recordar todo.'),
 (r'\bguardado(?:n)? automatico\b', 'Guardar automáticamente un documento significa conservar cambios sin que la persona pulse Guardar cada vez, por ejemplo tras un intervalo o evento. Depende del programa. La explicación no acredita que se haya guardado ese documento aquí.'),
 (r'\bruta relativa\b', 'Una ruta relativa se interpreta desde una carpeta de referencia; ejemplo ficticio: notas/archivo.txt. Una absoluta parte de la raíz; ejemplo ficticio: /tmp/ejemplo/archivo.txt. ~/ es una abreviación de la carpeta personal expandida por el intérprete de órdenes; no es un ejemplo de ruta relativa al directorio de trabajo. No uses la ruta real de Jarvis como ejemplo ficticio.'),
 (r'\bmegabytes\b.*\bmegabits\b', 'MB y Mb miden cantidades de información: un byte tiene 8 bits, por tanto 1 MB son 8 Mb con el mismo prefijo decimal. La velocidad requiere por segundo: MB/s o Mb/s. Un megabit por sí solo no es velocidad.'),
 (r'\bzona horaria\b', 'La misma fecha y hora local, por ejemplo 10:00, puede designar instantes distintos en zonas distintas. Especificar zona o desplazamiento UTC permite situarla. Esto es distinto de confundir 10 AM con 10 PM; el cambio estacional también puede repetir una hora local.'),
 (r'\bdeadlock\b', 'En el modelo clásico de recursos, las cuatro condiciones necesarias son exclusión mutua, retener mientras se espera, ausencia de expropiación y espera circular. Con dos bloqueos, un hilo puede retener A esperando B y otro retener B esperando A. No hay una condición llamada «no bloqueo mutuo». No ejecutes ni abortes procesos por explicar el concepto.'),
)
def contexto(pedido):
    n=vista(pedido)
    return '\n'.join(nota for patron,nota in NOTAS if re.search(patron,n))
