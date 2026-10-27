"""Rutas del proyecto. JARVIS_DIR permite ejecutar pruebas aisladas."""
import os
import sys
from pathlib import Path

PROYECTO = Path(os.environ.get('JARVIS_DIR', str(Path.home() / 'Jarvis'))).expanduser().resolve()
TRABAJO = PROYECTO / 'trabajo'
REGISTROS = PROYECTO / 'registros'
DATOS = PROYECTO / 'datos'


def en_pruebas():
    """Detecta pruebas para impedir que utilicen la memoria y los servicios reales."""
    script = Path(sys.argv[0]).name
    return (os.environ.get('JARVIS_PRUEBAS', '').casefold() in {'1', 'true', 'si'}
            or bool(os.environ.get('PYTEST_CURRENT_TEST'))
            or script.startswith('prueba_') or script == 'ejecutar_pruebas.py')

if en_pruebas():
    from aislamiento_pruebas import instalar
    instalar()
