"""Reserva por instalación entre chat gráfico y terminal, con plazo y limpieza."""
from contextlib import contextmanager
import fcntl
import os
import stat
import threading
import time
from entorno_jarvis import DATOS

LOCAL=threading.local()


class ColaOcupada(TimeoutError):pass


@contextmanager
def reservar(timeout):
    if getattr(LOCAL,'profundidad',0):
        LOCAL.profundidad+=1
        try:yield
        finally:LOCAL.profundidad-=1
        return
    DATOS.mkdir(parents=True,exist_ok=True,mode=0o700)
    ruta=DATOS/'ollama_inferencia.lock'
    fd=os.open(ruta,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    if not stat.S_ISREG(os.fstat(fd).st_mode):os.close(fd);raise ValueError('La reserva de inferencia no es un archivo regular.')
    fin=time.monotonic()+max(0,float(timeout));tomado=False
    try:
        while True:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);tomado=True;break
            except BlockingIOError:
                restante=fin-time.monotonic()
                if restante<=0:raise ColaOcupada('Otra ventana o terminal de Jarvis está usando el modelo; se agotó la espera en cola.')
                time.sleep(min(.05,restante))
        LOCAL.profundidad=1
        try:yield
        finally:LOCAL.profundidad=0
    finally:
        if tomado:fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)
