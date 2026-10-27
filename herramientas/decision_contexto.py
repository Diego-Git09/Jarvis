"""Decisión compartida de mensajes largos para interfaz y agente."""
def mensaje_largo(pregunta,historial,estado):
    if len(pregunta)<=12000:return None,'mensaje dentro del límite corto'
    import alcance_fuentes as A
    import externo_zen as Z
    A.preparar(historial,pregunta,estado)
    return Z.elegir(pregunta,'compleja',estado,contexto=True,renovar=True)
