"""Reglas locales de selección; sin inferencias, descargas ni llamadas a una API."""

import re
from configuracion_jarvis import MODELO_PREDETERMINADO, MODELO_COTIDIANO

MODELO_PRINCIPAL = MODELO_PREDETERMINADO
MODELO_RAZONAMIENTO = MODELO_PREDETERMINADO


def normalizar(texto):
    from normalizacion_entrada import vista
    return vista(texto)


PATRONES_COMPLEJOS = (
    r"\b(?:analiza|analizar|arquitectura|razonamiento)\b",
    r"\b(?:compara|comparar|evalua|evaluar|optimiza|optimizar)\b",
    r"\b(?:depura|depurar|debug|refactoriza|refactorizar)\b",
    r"\b(?:planifica|planificar|estrategia|disena|disenar)\b",
    r"\b(?:problema complejo|error dificil|solucion compleja)\b",
)


def decidir_modelo(pregunta):
    texto = normalizar(pregunta or "")

    if not texto.strip():
        return {
            "modelo": MODELO_PRINCIPAL,
            "usar_deepseek": False,
        }

    usar_deepseek = any(
        re.search(patron, texto)
        for patron in PATRONES_COMPLEJOS
    )

    return {
        "modelo": MODELO_PRINCIPAL,
        "usar_deepseek": usar_deepseek,
        "modelo_auxiliar": (
            MODELO_RAZONAMIENTO if usar_deepseek else None
        ),
    }


def clasificar_peticion(pregunta,adjuntos=False,anterior=None,continuar=False):
    """Reglas ordenadas sobre la petición visible, nunca sobre el documento."""
    visible=(pregunta or '').split('[Adjunto:',1)[0].strip()
    n=normalizar(visible).strip(' ¿?¡!.,;:')
    regla='consulta';clase='media';motivo='consulta o explicación breve sin análisis especializado'
    if visible.startswith('/'):
        regla='comando';clase='simple';motivo='comando directo; el controlador evita inferencia cuando puede resolverlo'
    elif re.fullmatch(r'(?:hola(?: jarvis)?|wena(?: po)?|buenas|buenos dias|buenas tardes|buenas noches|gracias|muchas gracias|como estas|como estai|que tal)',n):
        regla='saludo';clase='simple';motivo='saludo o cortesía sin otra tarea'
    elif adjuntos:
        regla='adjuntos';clase='compleja';motivo='análisis de fuentes adjuntas del turno'
    elif (decidir_modelo(visible)['usar_deepseek'] or re.search(r'\b(?:razona|razonar|demuestra|demostrar|diagnostica|diagnosticar|algoritmos?|concurrencia|interbloqueo|deadlock|vulnerabilidades?|trazabilidad|tradeoffs)\b',n)):
        regla='analisis';clase='compleja';motivo='razonamiento, comparación, diseño o depuración explícitos'
    elif re.search(r'\b(?:programa|programar|implementa|implementar|desarrolla|desarrollar|escribe|escribir|genera|generar|corrige|corregir|arregla|hazme|haceme|haz|crea|crear)\b',n) and re.search(r'\b(?:codigo|funcion|clase|script|consulta sql|python|sql|java|kotlin|android|compose|spring|api|programa|aplicacion|app)\b|```',n):
        regla='programacion';clase='compleja';motivo='creación o corrección de código solicitada'
    elif len(visible)>1500:
        regla='texto_extenso';clase='compleja';motivo='petición extensa que necesita integrar varias condiciones'
    elif continuar and anterior==MODELO_PREDETERMINADO:
        regla='continuacion';clase='compleja';motivo='continuación del análisis anterior, conservando el modelo'
    elif len(visible)<140:
        clase='simple';motivo='pregunta corta o acción directa sin señales de análisis'
    modelo=MODELO_PREDETERMINADO if clase=='compleja' else MODELO_COTIDIANO
    from comprension_peticion import principal
    return {'clase':clase,'regla':regla,'preferido':modelo,'motivo':motivo,'intencion':principal(visible)}


def seleccionar_respuesta(pregunta, instalados, respaldo, anterior=None, continuar=False,adjuntos=False,residentes=()):
    """Elige solo entre los dos modelos conocidos y el respaldo configurado.

    La decisión es una heurística de tareas, no una evaluación de calidad.
    Los nombres de modelos en un adjunto jamás se usan como destinos.
    """
    decision=clasificar_peticion(pregunta,adjuntos,anterior,continuar)
    preferido,motivo=decision['preferido'],decision['motivo']
    disponible = next((m for m in (preferido, respaldo, MODELO_COTIDIANO, MODELO_PREDETERMINADO)
                       if m in instalados), None)
    if disponible is None:
        raise ConnectionError('No hay un modelo del modo automático instalado. Usa /modelos y elige uno con /modelo NOMBRE. No descargué modelos ni consulté una API.')
    if decision['clase']!='compleja' and decision['regla']!='saludo':
        vigente=next((m for m in residentes if m in instalados and m in {MODELO_COTIDIANO,MODELO_PREDETERMINADO}),None)
        if vigente and vigente!=disponible:
            disponible=vigente;decision['motivo']+='; modelo residente suficiente para esta explicación, evita una recarga'
    return dict(decision,modelo=disponible,alternativa=disponible!=preferido)


def presentar_decision(decision):
    if not decision:return 'Todavía no hay una decisión de esta apertura.'
    if decision.get('sin_inferencia'):return 'Última respuesta: controlador, sin inferencia. '+decision['motivo']+'.'
    return 'Última elección: '+(decision.get('modelo') or decision.get('preferido','sin dato'))+' · '+decision['motivo']+'.'


def registrar_controlador(pregunta,estado,anterior):
    """Marca accesos resueltos fuera del modelo sin pisar una generación local."""
    if pregunta.strip().casefold().startswith(('/modelo','/escalar')):return
    if estado.get('_ultima_decision_modelo') is anterior:
        estado['_ultima_decision_modelo']=dict(clasificar_peticion(pregunta),sin_inferencia=True,motivo='orden resuelta por el controlador; no se llamó al modelo')
