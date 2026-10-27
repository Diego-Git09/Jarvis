"""Coordinador local opcional de DeepSeek para Jarvis."""

from control_deepseek import habilitado, limite_analisis
from enrutador_modelos import decidir_modelo
from configuracion_jarvis import MODELO_BASE_DEEPSEEK


def preparar_analisis(pregunta, permitido=True, modelo_principal=None):
    resultado = {
        "usado": False,
        "estado": "omitido",
        "analisis": ""
    }

    if not habilitado():
        resultado["estado"] = "desactivado"
        return resultado

    if not permitido or not isinstance(pregunta, str):
        return resultado

    if len(pregunta) > 1500 or not pregunta.strip():
        return resultado

    decision = decidir_modelo(pregunta)

    if not decision["usar_deepseek"]:
        return resultado

    # Si DeepSeek ya responde el turno, no ejecutar el mismo modelo otra vez
    # como auxiliar ni descargarlo de la VRAM antes de la respuesta principal.
    if isinstance(modelo_principal, str) and modelo_principal.casefold() in {decision["modelo_auxiliar"].casefold(), MODELO_BASE_DEEPSEEK}:
        resultado["estado"] = "modelo_principal"
        return resultado

    try:
        from auxiliar_deepseek import analizar

        respuesta = analizar(pregunta, timeout=30)

        if respuesta.get("usado") and respuesta.get("analisis"):
            resultado["usado"] = True
            resultado["estado"] = "utilizado"
            texto = respuesta["analisis"].strip()
            limite = limite_analisis()

            if len(texto) > limite:
                fragmento = texto[:limite]
                cortes = [
                    fragmento.rfind(". "),
                    fragmento.rfind(".\\n"),
                    fragmento.rfind("! "),
                    fragmento.rfind("? ")
                ]
                corte = max(cortes)

                if corte >= 150:
                    texto = fragmento[:corte + 1]
                else:
                    texto = fragmento.rsplit(" ", 1)[0] + "…"

            resultado["analisis"] = texto
        else:
            resultado["estado"] = "sin_respuesta"

    except Exception:
        resultado["estado"] = "error_auxiliar"

    return resultado
