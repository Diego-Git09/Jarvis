"""Sincronización del Segundo Cerebro desde Jarvis.

Reutiliza sincronizar_panel.py, el mismo mecanismo del botón «Sincronizar
ahora» del panel. Este módulo NO escribe en la base de datos por su cuenta,
NO lanza capturadores en paralelo y NO toca el panel ni su token: solo llama a
las funciones estado() y solicitar() de ese archivo y reporta lo que ocurrió.

Estados que puede informar: sin_solicitud, solicitada, en_curso, terminada,
error y desconocido. «terminada» significa que systemd informó éxito del ciclo.
"""
import importlib.util
import os
import time
from pathlib import Path

ESPERA_PREDETERMINADA = 90   # segundos que Jarvis sigue el ciclo antes de soltarlo
INTERVALO = 2                # segundos entre consultas de estado

PEDIDO = ("Iniciar una sincronización del Segundo Cerebro.\n"
          "Ejecuta un ciclo completo: captura, guardado, índice y revisión.\n"
          "Procesa un lote: si hay muchos mensajes pendientes, quedarán algunos.\n"
          "No es un backup.")


class ErrorSincronizacion(Exception):
    pass


_cache = {}


def carpeta():
    return Path(os.environ.get("SEGUNDO_CEREBRO_DIR") or Path.home() / "SegundoCerebro")


def _cargar():
    """Carga sincronizar_panel.py desde la carpeta del Segundo Cerebro."""
    ruta = carpeta() / "sincronizar_panel.py"
    if str(ruta) in _cache:
        return _cache[str(ruta)]
    if not ruta.is_file():
        raise ErrorSincronizacion(f"No encuentro {ruta}")
    spec = importlib.util.spec_from_file_location("sincronizar_panel_cerebro", ruta)
    modulo = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(modulo)
    except Exception as e:
        raise ErrorSincronizacion(
            f"No pude cargar sincronizar_panel.py: {type(e).__name__}: {e}") from e
    for nombre in ("estado", "solicitar", "ultima"):
        if not callable(getattr(modulo, nombre, None)):
            raise ErrorSincronizacion(f"sincronizar_panel.py no tiene la función {nombre}()")
    _cache[str(ruta)] = modulo
    return modulo


def _hace(segundos):
    if segundos < 90:
        return f"hace {int(segundos)} s"
    if segundos < 90 * 60:
        return f"hace {int(segundos // 60)} min"
    if segundos < 36 * 3600:
        return f"hace {int(segundos // 3600)} h"
    return f"hace {int(segundos // 86400)} días"


def _texto_estado(estado, manual, resultado, hace_s):
    cuando = f" ({_hace(hace_s)})" if hace_s is not None else ""
    if estado == "sin_solicitud":
        return "No hay una sincronización manual registrada ni un ciclo en ejecución."
    if estado == "solicitada":
        return "La sincronización fue solicitada y todavía no se confirma su inicio."
    if estado == "en_curso":
        return ("Hay un ciclo de captura en ejecución." if manual
                else "Hay un ciclo automático de captura en ejecución.")
    if estado == "terminada":
        return f"La última sincronización manual terminó correctamente{cuando}."
    if estado == "error":
        detalle = f" Detalle: {resultado}." if resultado else ""
        return f"La última sincronización manual terminó con error{cuando}.{detalle}"
    return ("No pude determinar el estado del ciclo: systemd o la base de datos "
            "no respondieron como se esperaba.")


def consultar(ahora=time.time):
    """Estado actual del ciclo. Solo lectura."""
    try:
        modulo = _cargar()
        base = carpeta()
        r = modulo.estado(base)
        fecha = None
        try:
            solicitud = modulo.ultima(base)
            fecha = solicitud.get("fecha") if solicitud else None
        except Exception:
            pass
    except ErrorSincronizacion as e:
        return {"ok": False, "error": str(e)}
    estado = r.get("estado", "desconocido")
    manual = bool(r.get("manual"))
    hace_s = (ahora() - fecha) if (fecha and manual) else None
    return {"ok": True, "estado": estado, "manual": manual, "id": r.get("id"),
            "resultado": r.get("resultado"), "hace_s": hace_s,
            "texto": _texto_estado(estado, manual, r.get("resultado"), hace_s)}


def solicitar():
    """Pide un ciclo con el mecanismo del panel. NO espera a que termine."""
    try:
        r = _cargar().solicitar(carpeta())
    except ErrorSincronizacion as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False,
                "error": f"No se pudo solicitar la sincronización: {type(e).__name__}: {e}"}
    estado = r.get("estado", "desconocido")
    return {"ok": True, "iniciada": estado == "solicitada", "estado": estado,
            "id": r.get("id"), "mensaje": r.get("mensaje", "")}


def seguir(id_solicitud, espera=ESPERA_PREDETERMINADA, intervalo=INTERVALO,
           dormir=time.sleep, reloj=time.monotonic):
    """Consulta el estado hasta que ESA solicitud termine o se agote la espera."""
    limite = reloj() + espera
    while True:
        r = consultar()
        if not r["ok"]:
            return r
        if r.get("id") == id_solicitud and r["estado"] in ("terminada", "error"):
            return {**r, "seguimiento": "completo"}
        if reloj() >= limite:
            return {**r, "seguimiento": "agotado"}
        dormir(intervalo)


def _resultado_final(r, espera):
    estado = r.get("estado")
    if r.get("seguimiento") == "completo" and estado == "terminada":
        return {"ok": True, "estado": "terminada",
                "texto": ("La sincronización terminó: el servicio de captura informó éxito. "
                          "Procesa un lote, así que pueden quedar mensajes pendientes; "
                          "consulta el estado del Segundo Cerebro para verlo.")}
    if r.get("seguimiento") == "completo":
        return {"ok": False, "estado": "error", "texto": r["texto"],
                "error": r["texto"]}
    if estado == "desconocido":
        return {"ok": False, "estado": "desconocido",
                "error": ("No pude confirmar cómo va el ciclo. Revisa el panel en "
                          "http://127.0.0.1:8767"),
                "texto": r["texto"]}
    return {"ok": True, "estado": "en_curso", "seguimiento": "agotado",
            "texto": (f"La sincronización sigue en curso después de {int(espera)} s. "
                      "Puede tardar varios minutos; consulta su estado más tarde.")}


def sincronizar(confirmar, espera=ESPERA_PREDETERMINADA, avisar=lambda texto: None,
                intervalo=INTERVALO, dormir=time.sleep, reloj=time.monotonic):
    """Flujo completo: comprobar, pedir permiso, solicitar y seguir hasta el resultado real."""
    actual = consultar()
    if not actual["ok"]:
        return {"ok": False, "error": actual["error"], "texto": actual["error"]}
    if actual["estado"] == "desconocido":
        mensaje = ("No pude comprobar el estado del servicio de captura (systemd o la base). "
                   "No inicié nada.")
        return {"ok": False, "estado": "desconocido", "error": mensaje, "texto": mensaje}
    if actual["estado"] in ("en_curso", "solicitada"):
        return {"ok": True, "iniciada": False, "estado": "en_curso",
                "texto": "Ya hay un ciclo en curso o solicitado; no inicié otro."}

    if not confirmar(PEDIDO):
        return {"ok": False, "no_autorizada": True,
                "error": "El usuario no autorizó la sincronización. No se inició nada.",
                "texto": "No autorizaste la sincronización. No se inició nada."}

    pedido = solicitar()
    if not pedido["ok"]:
        return {"ok": False, "error": pedido["error"], "texto": pedido["error"]}
    if not pedido["iniciada"]:
        return {"ok": True, "iniciada": False, "estado": "en_curso",
                "texto": pedido["mensaje"] or "Ya había un ciclo; no inicié otro."}

    avisar("Sincronización solicitada. Siguiendo el ciclo…")
    seguimiento = seguir(pedido["id"], espera, intervalo, dormir, reloj)
    final = _resultado_final(seguimiento, espera)
    final["iniciada"] = True
    return final
