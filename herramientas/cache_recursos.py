"""Caché breve de sensores, con copias e invalidación ante cargas/descargas."""
from copy import deepcopy
from functools import wraps
import threading,time

LECTURAS=[]

def invalidar():
    for f in tuple(LECTURAS):f.invalidar_cache()

def breve(clave,ttl=4):
    def decorar(funcion):
        lock=threading.RLock();guardado={}
        @wraps(funcion)
        def leer(*args,**kwargs):
            k=clave()
            with lock:
                if guardado.get('clave')==k and time.monotonic()-guardado.get('hora',-1e20)<ttl:
                    return deepcopy(guardado['valor'])
                valor=funcion(*args,**kwargs)
                guardado.update(clave=k,hora=time.monotonic(),valor=deepcopy(valor))
                return valor
        def limpiar():
            with lock:guardado.clear()
        leer.invalidar_cache=limpiar
        LECTURAS.append(leer)
        return leer
    return decorar
