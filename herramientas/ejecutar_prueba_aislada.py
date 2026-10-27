"""Entrada única de pruebas con guarda Python y escritura nativa restringida."""
import os
from pathlib import Path
import runpy
import sys
from aislamiento_pruebas import instalar,verificar_previo

def main():
    ruta=Path(sys.argv.pop(1)).resolve();sys.argv[0]=str(ruta)
    if not os.environ.get('JARVIS_DIR'):raise RuntimeError('Falta una raíz temporal explícita para la prueba.')
    instalar();verificar_previo(os.environ['JARVIS_DIR'],nativo=True)
    runpy.run_path(str(ruta),run_name='__main__')

if __name__=='__main__':main()
