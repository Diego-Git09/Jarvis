"""Pruebas del controlador con un modelo FALSO (no usa Ollama). Ejecutar:
    python3 ~/Jarvis/herramientas/prueba_agente.py
Trabaja en trabajo/_pruebas_agente/ y lo borra al terminar.
"""
import json
import os
import shutil

os.environ["NO_COLOR"] = "1"  # salida sin colores, para poder comprobar el texto

import herramientas_escritura as E  # noqa: E402,F401
import jarvis_agente as J  # noqa: E402
from herramientas_lectura import RAIZ  # noqa: E402

CARPETA = "_pruebas_agente"
resultados = []


def comprobar(nombre, condicion):
    resultados.append(bool(condicion))
    print(("PASÓ  " if condicion else "FALLÓ ") + nombre)


def llamada(nombre, **argumentos):
    return {"role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": nombre, "arguments": argumentos}}]}


def texto_final(texto):
    return {"role": "assistant", "content": texto}


def guion(*mensajes):
    cola = list(mensajes)
    return lambda _historial: cola.pop(0)


def correr(enviar, confirmar=lambda t: True, mostrar=lambda *_: None):
    historial = [{"role": "system", "content": "s"},
                 {"role": "user", "content": "pregunta"}]
    salida = J.ejecutar_turno(historial, enviar, confirmar, {}, mostrar=mostrar)
    return salida, historial


def mensajes_herramienta(historial):
    return [m["content"] for m in historial if m["role"] == "tool"]


def archivo(ruta):
    return RAIZ / CARPETA / ruta


def modelo_edicion(historial):
    """Falso modelo: propone un cambio y luego lo aplica."""
    paso = sum(1 for m in historial if m["role"] == "assistant")
    if paso == 0:
        return llamada("proponer_edicion", ruta=f"{CARPETA}/a.txt",
                       contenido_nuevo="adiós\n")
    if paso == 1:
        ultimo = json.loads(mensajes_herramienta(historial)[-1])
        return llamada("aplicar_edicion", id_propuesta=ultimo["id_propuesta"])
    return texto_final("listo")


def modelo_crear_y_revertir(historial):
    """Falso modelo: crea un archivo y luego lo deshace."""
    paso = sum(1 for m in historial if m["role"] == "assistant")
    if paso == 0:
        return llamada("crear_archivo", ruta=f"{CARPETA}/c.txt", contenido="x\n")
    if paso == 1:
        ultimo = json.loads(mensajes_herramienta(historial)[-1])
        return llamada("revertir_cambio", id_cambio=ultimo["id_cambio"])
    return texto_final("listo")


try:
    salida, h = correr(guion(llamada("listar_archivos"), texto_final("Hay un archivo.")))
    comprobar("usa una herramienta y luego responde",
              salida == "Hay un archivo." and "prueba.txt" in mensajes_herramienta(h)[0])

    salida, h = correr(guion(llamada("herramienta_inventada"), texto_final("fin")))
    comprobar("herramienta desconocida: error y sigue",
              "desconocida" in mensajes_herramienta(h)[0] and salida == "fin")

    salida, h = correr(guion(llamada("leer_archivo", ruta=5), texto_final("fin")))
    comprobar("argumento que no es texto: se rechaza",
              '"ok": false' in mensajes_herramienta(h)[0])

    salida, h = correr(guion(llamada("leer_archivo", ruta="a.txt", extra="x"),
                             texto_final("fin")))
    comprobar("argumento no permitido: se rechaza",
              "no permitidos" in mensajes_herramienta(h)[0])

    salida, h = correr(guion(llamada("leer_archivo", ruta="/etc/passwd"),
                             texto_final("fin")))
    comprobar("ruta fuera de la carpeta: se rechaza",
              "Fuera de alcance" in mensajes_herramienta(h)[0])

    preguntas = []

    def negar(texto):
        preguntas.append(texto)
        return False

    salida, h = correr(guion(llamada("crear_archivo", ruta=f"{CARPETA}/a.txt",
                                     contenido="hola\n"), texto_final("fin")), negar)
    comprobar("crear sin permiso: pregunta y NO escribe",
              len(preguntas) == 1 and not archivo("a.txt").exists()
              and "no autorizó" in mensajes_herramienta(h)[0])

    salida, h = correr(guion(llamada("crear_archivo", ruta=f"{CARPETA}/a.txt",
                                     contenido="hola\n"), texto_final("fin")))
    comprobar("crear con permiso: escribe",
              archivo("a.txt").read_text(encoding="utf-8") == "hola\n")

    salida, h = correr(modelo_edicion, negar)
    comprobar("aplicar sin permiso: el archivo no cambia",
              archivo("a.txt").read_text(encoding="utf-8") == "hola\n"
              and "no autorizó" in mensajes_herramienta(h)[-1])

    vistos = []

    def aceptar(texto):
        vistos.append(texto)
        return True

    salida, h = correr(modelo_edicion, aceptar)
    comprobar("aplicar con permiso: muestra la diferencia y escribe",
              archivo("a.txt").read_text(encoding="utf-8") == "adiós\n"
              and any("+adiós" in v for v in vistos))
    comprobar("aplicar: el permiso nombra el archivo y no muestra cabeceras",
              f"{CARPETA}/a.txt" in vistos[-1] and "(propuesto)" not in vistos[-1])

    preguntas.clear()
    salida, h = correr(guion(llamada("aplicar_edicion", id_propuesta="deadbeef"),
                             texto_final("fin")), negar)
    comprobar("aplicar sin diferencia mostrada: ni siquiera pregunta",
              not preguntas and "No hay una diferencia" in mensajes_herramienta(h)[0])

    salida, h = correr(guion(llamada("revertir_cambio", id_cambio="deadbeef"),
                             texto_final("fin")), negar)
    comprobar("revertir un cambio inexistente: error y no pregunta",
              not preguntas and "No encontré" in mensajes_herramienta(h)[0])

    # Pantalla: nada de identificadores internos en lo que ve el usuario
    permisos, lineas = [], []

    def aceptar_y_guardar(texto):
        permisos.append(texto)
        return True

    salida, h = correr(modelo_crear_y_revertir, aceptar_y_guardar, lineas.append)
    id_cambio = json.loads(mensajes_herramienta(h)[0])["id_cambio"]
    pantalla = "\n".join(permisos + lineas)
    comprobar("revertir: el permiso nombra el archivo, no el identificador",
              f"{CARPETA}/c.txt" in permisos[1] and id_cambio not in pantalla)
    comprobar("revertir de una creación: el archivo desaparece",
              not archivo("c.txt").exists())
    comprobar("líneas de estado: con marca y sin identificadores",
              len(lineas) == 2 and all(l.startswith("  ✓") for l in lineas)
              and "comprobado" in lineas[0])

    comprobar("una escritura no comprobada se muestra como fallo",
              J.resumen_resultado("aplicar_edicion",
                                  {"ok": True, "verificado": False})[0] is False)
    comprobar("un error se muestra como fallo con su motivo",
              J.resumen_resultado("leer_archivo", {"ok": False, "error": "x"})
              == (False, "x"))
    comprobar("describir usa frases humanas",
              J.describir("leer_archivo", {"ruta": "a.txt"}) == "Leyendo a.txt")

    salida, h = correr(lambda _h: llamada("listar_archivos"))
    comprobar("límite de pasos: se detiene", salida.startswith("Me detuve"))

    grande = J._para_modelo({"x": "a" * 50_000})
    comprobar("resultado enorme: se recorta", len(grande) < 12_100)
finally:
    shutil.rmtree(RAIZ / CARPETA, ignore_errors=True)

print()
print(f"{sum(resultados)} de {len(resultados)} pruebas pasaron.")