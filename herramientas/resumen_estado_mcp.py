"""Reduce exclusivamente el estado MCP enviado al modelo."""

def resumir(resultado):
    if not isinstance(resultado, dict):
        return resultado

    claves = (
        "ok",
        "consultado",
        "memorias",
        "recuerdos",
        "conversaciones",
        "registros",
        "servicios",
        "panel",
        "alcance",
    )

    resumen = {
        clave: resultado[clave]
        for clave in claves
        if clave in resultado
    }

    resumen["resumen_para_modelo"] = True
    resumen["detalle_omitido"] = [
        clave for clave in resultado
        if clave not in claves
    ]

    return resumen
