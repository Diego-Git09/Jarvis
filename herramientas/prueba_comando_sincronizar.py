"""Pruebas del comando /sincronizar dentro de Jarvis. Ejecutar:
    python3 ~/Jarvis/herramientas/prueba_comando_sincronizar.py

Usa interfaz_local.py, interfaz_jarvis.py, accesos_jarvis.py y ayuda_jarvis.py REALES, con un systemctl FALSO y una base
temporal (copia de tu sincronizar_panel.py). No inicia ningún ciclo real.
"""
import contextlib
import io
import json
import os
import shutil
import sqlite3
import stat
import sys
import tempfile
from pathlib import Path

ORIGINAL = Path(os.environ.get("PANEL_ORIGINAL")
                or Path.home() / "SegundoCerebro" / "sincronizar_panel.py")
if not ORIGINAL.is_file():
    print(f"No encuentro {ORIGINAL}. Define PANEL_ORIGINAL con su ruta.")
    sys.exit(1)

import accesos_jarvis as A  # noqa: E402
import interfaz_local as IL  # noqa: E402
import sincronizacion_jarvis as SYNC  # noqa: E402
import interfaz_jarvis as IJ  # noqa: E402
import ayuda_jarvis as AY  # noqa: E402

FALSO = r'''#!/usr/bin/env python3
import json, os, sys, time, uuid
D = os.environ["FAKE_SYSTEMCTL_DIR"]
ruta = os.path.join(D, "estado.json")
args = sys.argv[1:]
open(os.path.join(D, "llamadas.log"), "a").write(" ".join(args) + "\n")
cfg = json.load(open(ruta))
if "show" in args:
    activo = time.time() < cfg["termina_en"]
    p = {"ActiveState": "active" if activo else "inactive", "SubState": "running" if activo else "dead",
         "InvocationID": cfg["invocacion"], "ExecMainStatus": "0", "Result": "success"}
    print("\n".join(f"{k}={v}" for k, v in p.items()))
elif "start" in args:
    cfg["invocacion"] = uuid.uuid4().hex
    cfg["termina_en"] = time.time() + cfg["duracion"]
    json.dump(cfg, open(ruta, "w"))
'''

resultados = []
PATH_ORIGINAL = os.environ["PATH"]


def comprobar(nombre, condicion):
    resultados.append(bool(condicion))
    print(("PASÓ  " if condicion else "FALLÓ ") + nombre)


def preparar(duracion=1.5):
    raiz = Path(tempfile.mkdtemp(prefix="jarvis_cmd_sync_"))
    cerebro, bin_ = raiz / "SegundoCerebro", raiz / "bin"
    cerebro.mkdir()
    bin_.mkdir()
    shutil.copy(ORIGINAL, cerebro / "sincronizar_panel.py")
    with sqlite3.connect(cerebro / "cerebro.db") as db:
        db.execute("CREATE TABLE monitor_estado (clave TEXT PRIMARY KEY, valor TEXT)")
        db.execute("INSERT INTO monitor_estado VALUES ('ciclo','terminado')")
        db.execute("INSERT INTO monitor_estado VALUES ('ciclo_inicio','2020-01-01T00:00:00+00:00')")
    shim = bin_ / "systemctl"
    shim.write_text(FALSO)
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    (raiz / "estado.json").write_text(json.dumps(
        {"invocacion": "inicial", "termina_en": 0, "duracion": duracion}))
    os.environ.update({"SEGUNDO_CEREBRO_DIR": str(cerebro),
                       "FAKE_SYSTEMCTL_DIR": str(raiz),
                       "PATH": f"{bin_}:{PATH_ORIGINAL}"})
    if shutil.which("systemctl") != str(shim):
        print("ABORTO: no se usa el systemctl falso; no sigo para no tocar tu sistema.")
        sys.exit(2)
    return raiz


def inicios(raiz):
    log = raiz / "llamadas.log"
    return sum(1 for l in log.read_text().splitlines() if " start " in f" {l} ") if log.exists() else 0


def comando(texto, permiso=True, preguntas=None):
    estado = {}

    def confirmar(pedido):
        if preguntas is not None:
            preguntas.append(pedido)
        return permiso
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        manejado, respuesta = IL.comando_local(texto, [], estado, confirmar, {}, lambda: None, None)
    return manejado, respuesta, estado, salida.getvalue()


raiz = None
try:
    raiz = preparar()
    m, t, e, _ = comando("/sincronizar estado")
    comprobar("/sincronizar estado: sin solicitudes lo dice", m and "No hay una sincronización" in t)

    preguntas = []
    m, t, e, _ = comando("/sincronizar", permiso=False, preguntas=preguntas)
    comprobar("/sincronizar sin permiso: no inicia nada y lo registra",
              m and "No autorizaste" in t and inicios(raiz) == 0
              and e["_ultima_accion"]["ok"] is False and len(preguntas) == 1)

    m, t, e, pantalla = comando("/sincronizar", permiso=True)
    comprobar("/sincronizar con permiso: sigue el ciclo e informa éxito",
              m and "terminó" in t and inicios(raiz) == 1 and e["_ultima_accion"]["ok"] is True)
    comprobar("/sincronizar muestra que está siguiendo el ciclo", "Siguiendo el ciclo" in pantalla)

    m, t, e, _ = comando("/sincronizar estado")
    comprobar("/sincronizar estado después: terminó correctamente, con antigüedad",
              "terminó correctamente" in t and "hace" in t)

    m, t, e, _ = comando("/sincronizar ahora mismo")
    comprobar("/sincronizar con argumentos raros: muestra el uso, no inicia nada",
              m and t.startswith("Uso:") and inicios(raiz) == 1)

    # Frases naturales (dependen de limpiar() y normalizar() de tu lenguaje_jarvis.py)
    for frase in ("sincroniza los recuerdos", "Sincroniza el Segundo Cerebro", "sincroniza ahora"):
        preguntas = []
        m, t, e, _ = comando(frase, permiso=False, preguntas=preguntas)
        comprobar(f"natural «{frase}»: llega a la sincronización y pide permiso",
                  m and len(preguntas) == 1 and "No autorizaste" in t)
    m, t, e, _ = comando("¿cómo va la sincronización?")
    comprobar("natural «como va la sincronizacion»: consulta el estado",
              m and "sincronización" in t)

    # Ctrl+C mientras se sigue el ciclo: no se cae y explica qué pasó
    original = SYNC.sincronizar
    SYNC.sincronizar = lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt())
    try:
        m, t, e, _ = comando("/sincronizar")
    finally:
        SYNC.sincronizar = original
    comprobar("Ctrl+C durante el seguimiento: avisa que el ciclo continúa",
              m and "continúa por su cuenta" in t and e["_ultima_accion"]["ok"] is False)

    comprobar("/sincronizar está en el catálogo de accesos", "/sincronizar" in A.ACCESOS)
    comprobar("/sync y /sincronizacion son alias de /sincronizar",
              A.normalizar_acceso("/sync") == "/sincronizar"
              and A.normalizar_acceso("/sincronización") == "/sincronizar")
    comprobar("un error de escritura sugiere /sincronizar", "/sincronizar" in A.sugerir("/sincroniza"))
    # Ruta completa, como en el programa: interfaz_jarvis.comando() -> comando_local()
    def ruta_completa(texto, permiso=True, preguntas=None):
        estado, historial = {}, []

        def confirmar(pedido):
            if preguntas is not None:
                preguntas.append(pedido)
            return permiso
        local = lambda p, h, e: IL.comando_local(p, h, e, confirmar, {}, lambda: None, None)
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            r = IJ.comando(texto, historial, estado, lambda n, a: {"ok": False}, "sistema", local=local)
        return r, historial

    (m, t_), historial = ruta_completa("/sync estado")
    comprobar("ruta completa: /sync estado se resuelve y queda en la conversación",
              m and "sincronización" in t_ and len(historial) == 2)

    preguntas = []
    (m, t_), historial = ruta_completa("Jarvis, por favor sincroniza los recuerdos", permiso=False, preguntas=preguntas)
    comprobar("ruta completa: una frase con cortesía pide permiso y no inicia nada",
              m and len(preguntas) == 1 and "No autorizaste" in t_ and inicios(raiz) == 1)

    for frase in ("sincroniza y borra todo", "no sincronices nada", "sincroniza y luego mueve los recuerdos a Jarvis"):
        preguntas = []
        (m, t_), historial = ruta_completa(frase, permiso=True, preguntas=preguntas)
        comprobar(f"frase compuesta «{frase}»: NO inicia la sincronización",
                  not preguntas and inicios(raiz) == 1)

    comprobar("la ayuda general menciona /sincronizar", "/sincronizar" in AY.GENERAL)
    comprobar("la ayuda de memoria explica /sincronizar y que no es un backup",
              "/sincronizar estado" in AY.ayuda("memoria") and "backup" in AY.ayuda("memoria"))
finally:
    os.environ["PATH"] = PATH_ORIGINAL
    if raiz:
        shutil.rmtree(raiz, ignore_errors=True)

print()
print(f"{sum(resultados)} de {len(resultados)} pruebas pasaron.")
