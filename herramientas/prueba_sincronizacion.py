"""Pruebas de la sincronización. Ejecutar:
    python3 ~/Jarvis/herramientas/prueba_sincronizacion.py

Usa el sincronizar_panel.py REAL (una copia, solo lectura) con un systemctl FALSO
y una base de datos temporal. No inicia ningún ciclo real ni toca tu Segundo Cerebro.
"""
import json
import os
import shutil
import sqlite3
import stat
import sys
import tempfile
import time
from pathlib import Path

ORIGINAL = Path(os.environ.get("PANEL_ORIGINAL")
                or Path.home() / "SegundoCerebro" / "sincronizar_panel.py")
if not ORIGINAL.is_file():
    print(f"No encuentro {ORIGINAL}. Define PANEL_ORIGINAL con su ruta.")
    sys.exit(1)

import sincronizacion_jarvis as S  # noqa: E402

FALSO = r'''#!/usr/bin/env python3
import json, os, sys, time, uuid
D = os.environ["FAKE_SYSTEMCTL_DIR"]
ruta = os.path.join(D, "estado.json")
args = sys.argv[1:]
open(os.path.join(D, "llamadas.log"), "a").write(" ".join(args) + "\n")
cfg = json.load(open(ruta))
if "show" in args:
    if time.time() < cfg["termina_en"]:
        p = {"ActiveState": "active", "SubState": "running", "InvocationID": cfg["invocacion"],
             "ExecMainStatus": "0", "Result": "success"}
    else:
        p = {"ActiveState": cfg["final_estado"], "SubState": "dead", "InvocationID": cfg["invocacion"],
             "ExecMainStatus": cfg["final_codigo"], "Result": cfg["final_resultado"]}
    print("\n".join(f"{k}={v}" for k, v in p.items()))
elif "start" in args:
    if cfg["start_falla"]:
        sys.exit(1)
    cfg["invocacion"] = uuid.uuid4().hex
    cfg["termina_en"] = time.time() + cfg["duracion"]
    json.dump(cfg, open(ruta, "w"))
'''

resultados = []
PATH_ORIGINAL = os.environ["PATH"]


def comprobar(nombre, condicion):
    resultados.append(bool(condicion))
    print(("PASÓ  " if condicion else "FALLÓ ") + nombre)


def escenario(duracion=2, final_estado="inactive", final_codigo="0",
              final_resultado="success", start_falla=False):
    raiz = Path(tempfile.mkdtemp(prefix="jarvis_sync_"))
    cerebro = raiz / "SegundoCerebro"
    bin_ = raiz / "bin"
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
    (raiz / "estado.json").write_text(json.dumps({
        "invocacion": "inicial", "termina_en": 0, "duracion": duracion,
        "final_estado": final_estado, "final_codigo": final_codigo,
        "final_resultado": final_resultado, "start_falla": start_falla}))
    os.environ.update({"SEGUNDO_CEREBRO_DIR": str(cerebro),
                       "FAKE_SYSTEMCTL_DIR": str(raiz),
                       "PATH": f"{bin_}:{PATH_ORIGINAL}"})
    # Seguridad: si el systemctl falso no es el que se usa, no seguimos.
    if shutil.which("systemctl") != str(shim):
        print("ABORTO: no se está usando el systemctl falso; no sigo para no tocar tu sistema.")
        sys.exit(2)
    return raiz, cerebro


def inicios(raiz):
    log = (raiz / "llamadas.log")
    return sum(1 for l in log.read_text().splitlines() if " start " in f" {l} ") if log.exists() else 0


def solicitud(cerebro):
    with sqlite3.connect(cerebro / "cerebro.db") as db:
        return db.execute("SELECT valor FROM monitor_estado WHERE clave='sync_solicitud'").fetchone()


def sincronizar(permiso=True, espera=20, preguntas=None):
    def confirmar(texto):
        if preguntas is not None:
            preguntas.append(texto)
        return permiso
    return S.sincronizar(confirmar, espera=espera, intervalo=0.4)


raices = []
try:
    # 1. Sin nada que informar
    raiz, cerebro = escenario(); raices.append(raiz)
    r = S.consultar()
    comprobar("consultar sin solicitudes: sin_solicitud", r["ok"] and r["estado"] == "sin_solicitud")

    # 2. Permiso denegado: no se inicia nada
    preguntas = []
    r = sincronizar(permiso=False, preguntas=preguntas)
    comprobar("sin permiso: no se inicia ni se registra nada",
              r.get("no_autorizada") and inicios(raiz) == 0 and solicitud(cerebro) is None)
    comprobar("el permiso explica el alcance y aclara que no es un backup",
              len(preguntas) == 1 and "backup" in preguntas[0] and "lote" in preguntas[0])

    # 3. Con permiso: se sigue hasta el resultado real
    r = sincronizar(permiso=True)
    comprobar("con permiso: el ciclo termina y se informa éxito",
              r["ok"] and r["estado"] == "terminada" and r["iniciada"] and inicios(raiz) == 1)
    comprobar("el mensaje final avisa que procesa un lote",
              "lote" in r["texto"] and "pendientes" in r["texto"])
    c = S.consultar()
    comprobar("consultar después: terminada, con antigüedad",
              c["estado"] == "terminada" and c["hace_s"] is not None and "hace" in c["texto"])

    # 4. No se inicia un segundo ciclo
    raiz2, cerebro2 = escenario(duracion=6); raices.append(raiz2)
    s = S.solicitar()
    comprobar("solicitar: se inicia un ciclo", s["ok"] and s["iniciada"] and inicios(raiz2) == 1)
    preguntas = []
    r = sincronizar(permiso=True, preguntas=preguntas)
    comprobar("con un ciclo activo: no inicia otro ni pregunta",
              r["ok"] and not r["iniciada"] and inicios(raiz2) == 1 and not preguntas)
    s2 = S.solicitar()
    comprobar("solicitar dos veces: la segunda no inicia otro",
              s2["ok"] and not s2["iniciada"] and inicios(raiz2) == 1)

    # 5. El ciclo falla
    raiz3, _ = escenario(duracion=1, final_estado="failed", final_codigo="1",
                         final_resultado="exit-code"); raices.append(raiz3)
    r = sincronizar(permiso=True)
    comprobar("ciclo con error: se informa como error, no como éxito",
              not r["ok"] and r["estado"] == "error" and "error" in r["texto"])

    # 6. systemctl rechaza el inicio: no queda solicitud fantasma
    raiz4, cerebro4 = escenario(start_falla=True); raices.append(raiz4)
    r = sincronizar(permiso=True)
    comprobar("si systemctl falla: error claro y sin solicitud pendiente",
              not r["ok"] and solicitud(cerebro4) is None
              and S.consultar()["estado"] == "sin_solicitud")

    # 7. El seguimiento se agota antes de que termine el ciclo
    raiz5, _ = escenario(duracion=8); raices.append(raiz5)
    t0 = time.time()
    r = sincronizar(permiso=True, espera=1.2)
    comprobar("seguimiento agotado: dice que sigue en curso, sin afirmar éxito",
              r["ok"] and r["estado"] == "en_curso" and r.get("seguimiento") == "agotado"
              and "sigue en curso" in r["texto"] and time.time() - t0 < 6)

    # 8. systemctl no disponible: no se pregunta ni se inicia nada
    raiz6, cerebro6 = escenario(); raices.append(raiz6)
    vacio = raiz6 / "vacio"
    vacio.mkdir()
    os.environ["PATH"] = str(vacio)
    preguntas = []
    r = sincronizar(permiso=True, preguntas=preguntas)
    comprobar("sin systemd: no pregunta, no inicia y lo dice",
              not r["ok"] and not preguntas and solicitud(cerebro6) is None
              and "No inicié nada" in r["texto"])

    # 9. Falta el archivo del panel
    os.environ["PATH"] = PATH_ORIGINAL
    os.environ["SEGUNDO_CEREBRO_DIR"] = str(raiz6 / "no_existe")
    r = S.consultar()
    comprobar("sin sincronizar_panel.py: error claro",
              not r["ok"] and "No encuentro" in r["error"])
finally:
    os.environ["PATH"] = PATH_ORIGINAL
    for r in raices:
        shutil.rmtree(r, ignore_errors=True)

print()
print(f"{sum(resultados)} de {len(resultados)} pruebas pasaron.")
