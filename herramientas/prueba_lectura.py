"""Pruebas de las herramientas de escritura. Ejecutar:
    python3 ~/Jarvis/herramientas/prueba_escritura.py
Trabaja en trabajo/_pruebas_escritura/ y lo borra al terminar.
"""
import shutil

from herramientas_lectura import RAIZ
from herramientas_escritura import (
    crear_archivo, proponer_edicion, aplicar_edicion, revertir_cambio)

CARPETA = "_pruebas_escritura"
resultados = []


def comprobar(nombre, condicion):
    resultados.append(bool(condicion))
    print(("PASÓ  " if condicion else "FALLÓ ") + nombre)


def texto(ruta):
    return (RAIZ / CARPETA / ruta).read_text(encoding="utf-8")


try:
    r = crear_archivo(f"{CARPETA}/a.txt", "hola\n")
    comprobar("crear: escrito y verificado",
              r["ok"] and r["escrito"] and r["verificado"] and texto("a.txt") == "hola\n")

    r = crear_archivo(f"{CARPETA}/a.txt", "otra cosa\n")
    comprobar("crear: no pisa un archivo existente",
              not r["ok"] and texto("a.txt") == "hola\n")

    r = crear_archivo("../fuera.txt", "x")
    comprobar("crear: rechaza salir de la carpeta",
              not r["ok"] and not (RAIZ.parent / "fuera.txt").exists())

    p = proponer_edicion(f"{CARPETA}/a.txt", "adiós\n")
    comprobar("proponer: preparado pero NO escrito",
              p["ok"] and p["preparado"] and not p["escrito"]
              and texto("a.txt") == "hola\n")
    comprobar("proponer: la diferencia muestra el cambio",
              "-hola" in p["diferencia"] and "+adiós" in p["diferencia"])

    e = aplicar_edicion(p["id_propuesta"])
    comprobar("aplicar: escrito y verificado",
              e["ok"] and e["escrito"] and e["verificado"] and texto("a.txt") == "adiós\n")

    v = revertir_cambio(e["id_cambio"])
    comprobar("revertir edición: vuelve al original",
              v["ok"] and v["verificado"] and texto("a.txt") == "hola\n")

    v = revertir_cambio(e["id_cambio"])
    comprobar("revertir: no se puede hacer dos veces", not v["ok"])

    p2 = proponer_edicion(f"{CARPETA}/a.txt", "versión B\n")
    (RAIZ / CARPETA / "a.txt").write_text("cambio externo\n", encoding="utf-8")
    e2 = aplicar_edicion(p2["id_propuesta"])
    comprobar("aplicar: se niega si el archivo cambió",
              not e2["ok"] and texto("a.txt") == "cambio externo\n")

    r = aplicar_edicion("../../etc/x")
    comprobar("aplicar: rechaza identificador inválido", not r["ok"])

    c = crear_archivo(f"{CARPETA}/b.txt", "temporal\n")
    v = revertir_cambio(c["id_cambio"])
    comprobar("revertir creación: el archivo desaparece",
              v["ok"] and v["verificado"] and not (RAIZ / CARPETA / "b.txt").exists())
finally:
    shutil.rmtree(RAIZ / CARPETA, ignore_errors=True)

print()
print(f"{sum(resultados)} de {len(resultados)} pruebas pasaron.")