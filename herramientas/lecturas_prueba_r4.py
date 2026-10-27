"""Broker fijo de sensores para pruebas Landlock, sin permisos sobre el dispositivo.

El proceso restringido lee JSON reciente de un lector separado. No se sustituyen
valores de hardware ni se autorizan dispositivos NVIDIA al código de prueba.
"""
import atexit, json, subprocess, sys, time
from pathlib import Path

def iniciar(raiz):
    ruta=Path(raiz).resolve()/'sensores_reales.json'
    proceso=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),str(ruta)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    def cerrar():
        if proceso.poll() is None:
            proceso.terminate()
            try:proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:proceso.kill();proceso.wait(timeout=5)
    atexit.register(cerrar)
    def leer():
        if proceso.poll() is not None:raise ValueError('El lector real de sensores se detuvo')
        d=json.loads(ruta.read_text())
        if not 0<=time.monotonic()-d['monotonico']<=8:raise ValueError('La lectura de sensores no es reciente')
        if not isinstance(d.get('foto'),dict):raise ValueError('Lectura inválida')
        return d['foto']
    fin=time.monotonic()+15
    while not ruta.exists():
        if proceso.poll() is not None or time.monotonic()>fin:cerrar();raise RuntimeError('No se inició el lector real de sensores')
        time.sleep(.1)
    return leer,cerrar

def main():
    ruta=Path(sys.argv[1]);real=ruta.resolve()
    if not real.is_relative_to('/tmp') or ruta.is_symlink() or any(p.is_symlink() for p in ruta.parents):raise ValueError('Solo salida temporal propia')
    import control_recursos as R
    from conversaciones_jarvis import _atomic
    while True:
        foto=R.instantanea();_atomic(real,{'monotonico':time.monotonic(),'foto':foto})
        time.sleep(1)
if __name__=='__main__':main()
