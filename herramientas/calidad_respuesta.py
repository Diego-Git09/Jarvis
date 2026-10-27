"""Detecta exposición de etiquetas del controlador en prosa generada."""
import re
from normalizacion_entrada import plegar

PROHIBIDAS=('jarvis debe responder respetando las instrucciones','formatos json','el usuario ha proporcionado un resumen historico','crear_archivo','listar_memorias','consultar_estado_cerebro','guardar_memoria','proponer_edicion','aplicar_edicion','leer_archivo','buscar_memoria_semantica','es informacion, no instrucciones','son datos, no instrucciones','datos previos, no instrucciones',
    'no puedo confirmar que significa "/no_think"','mis reglas internas','etiqueta de contexto','protocolo del controlador',
    '[continuacion de la conversacion','[peticion actual','[contexto temporal',
    'no se ha proporcionado una lista de herramientas','herramientas esten correctamente listadas',
    'la respuesta resuelve la peticion actual o indica claramente lo pendiente',
    'no muestra razonamiento interno')

def filtraciones(texto):
    bloques=re.findall(r'```[\s\S]*?```',texto)
    prosa=re.sub(r'```[\s\S]*?```','',texto)
    # Los literales de código se conservan; un paquete de transporte o un prompt
    # envuelto en una cerca sigue siendo una filtración, no código solicitado.
    prosa+='\n'.join(b for b in bloques if re.search(r'[\"\'](?:tool_calls|arguments|function|accion)[\"\']|Eres Jarvis',b))
    n=plegar(prosa)
    return [p for p in PROHIBIDAS if p in n]


def atribucion_invertida(pedido,respuesta):
    """Contrato acotado de participantes; no deduce el contenido del historial."""
    from normalizacion_entrada import vista
    if not re.search(r'\b(?:que|cual)\b.{0,60}\bte (?:pedi|pregunte|solicite|dije)\b',vista(pedido)):
        return []
    prosa=re.sub(r'```[\s\S]*?```|`[^`\n]*`|«[^»\n]*»|"[^"\n]*"|“[^”\n]*”','',respuesta)
    patron=r'(?m)^\s*(?:(?:despues|luego|antes|al corregir)[^\n.!?]{0,100}[,:]\s*)?(?:yo\s+)?te\s+(?:pedi|pediste|pregunte|preguntaste|solicite|solicitaste|indique|dije)\b'
    if re.search(patron,plegar(prosa)):
        return ['Invertiste quién hizo la petición. El usuario la hizo: responde «Me pediste ...» apoyándote en su mensaje anterior. No inventes una petición del asistente.']
    return []
