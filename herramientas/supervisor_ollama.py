"""Dueño del proceso Ollama iniciado por Jarvis, sin acceso a prompts ni claves."""
import argparse
import ctypes
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from servicio_ollama import (bloqueo,clientes_vivos,comprobar,entorno_hijo,
                             guardar_json,leer_json,validar_destino,escucha_propia)

def terminar_hijo(proceso):
    """Solo el grupo creado aquí, con handle vivo; nunca PIDs del archivo."""
    if proceso is None or proceso.poll() is not None:return
    try:os.killpg(proceso.pid,signal.SIGTERM)
    except ProcessLookupError:return
    try:proceso.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:os.killpg(proceso.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        proceso.wait(timeout=2)

def _con_padre(pid_padre):
    # El supervisor no tiene otros hilos al crear el hijo. Linux/Ubuntu.
    lib=ctypes.CDLL(None,use_errno=True)
    if lib.prctl(1,signal.SIGTERM,0,0,0)!=0:os._exit(126)
    if os.getppid()!=pid_padre:os._exit(126)

def supervisar(url,raiz,token,ejecutable):
    validar_destino(url,iniciar=True)
    salir=threading.Event()
    for s in (signal.SIGTERM,signal.SIGINT):signal.signal(s,lambda *_:salir.set())
    hijo=None;inicio=time.monotonic();salud={'ok':False};error=''
    try:
        with bloqueo(raiz):
            control=leer_json(raiz/'control.json')
            if not control or control.get('token')!=token or control.get('pid')!=os.getpid():
                return
            if not clientes_vivos(raiz):return
            # Un servidor puede haber ganado el puerto después del primer sondeo.
            if comprobar(url,timeout=.4)['ok']:
                control.update(estado='preexistente');guardar_json(raiz/'control.json',control)
                return
        env=entorno_hijo(url,raiz)
        Path(env['HOME']).mkdir(mode=0o700,exist_ok=True)
        padre=os.getpid()
        hijo=subprocess.Popen([ejecutable,'serve'],env=env,stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                              start_new_session=True,close_fds=True,
                              preexec_fn=lambda:_con_padre(padre))
        with bloqueo(raiz):
            control=leer_json(raiz/'control.json') or {}
            if control.get('token')!=token:return
            control['ollama_pid']=hijo.pid
            guardar_json(raiz/'control.json',control)
        while not salir.is_set():
            if hijo.poll() is not None:
                error='proceso_terminado'
                break
            with bloqueo(raiz):
                control=leer_json(raiz/'control.json') or {}
                if control.get('token')!=token:break
                if not clientes_vivos(raiz):
                    control['estado']='cerrando';guardar_json(raiz/'control.json',control)
                    break
            if not salud['ok']:
                salud=comprobar(url,timeout=.3)
                if salud['ok']:
                    propio=escucha_propia(hijo.pid,url)
                    if propio is None:
                        error='propiedad_sin_acreditar';break
                    with bloqueo(raiz):
                        control=leer_json(raiz/'control.json') or {}
                        if control.get('token')!=token:break
                        control.update(estado='disponible' if propio else 'preexistente',ollama_pid=hijo.pid)
                        guardar_json(raiz/'control.json',control)
                    if not propio:break
                elif time.monotonic()-inicio>12:
                    error='api_sin_respuesta'
                    break
            salir.wait(.2)
    except (OSError,ValueError,RecursionError):
        error='control'
    finally:
        try:terminar_hijo(hijo)
        finally:
            with bloqueo(raiz):
                control=leer_json(raiz/'control.json') or {}
                if control.get('token')==token:
                    if control.get('estado')!='preexistente':control['estado']='error' if error else 'cerrado'
                    if error:control['error_codigo']=error
                    guardar_json(raiz/'control.json',control)
                clientes_vivos(raiz)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for nombre in ('url','raiz','token','ejecutable'):p.add_argument('--'+nombre,required=True)
    a=p.parse_args()
    if len(a.token)!=32 or any(c not in '0123456789abcdef' for c in a.token):p.error('Token de control inválido.')
    supervisar(a.url,Path(a.raiz),a.token,a.ejecutable)

if __name__=='__main__':main()
