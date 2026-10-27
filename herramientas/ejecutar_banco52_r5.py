"""Resultados por caso del banco simulado, con aislamiento previo al cliente.

Uso: python3 -B herramientas/ejecutar_banco52_r5.py > informe.txt 2>&1
No mide calidad de modelos: comprueba contratos y efectos del controlador.
"""
import os
from pathlib import Path
import tempfile
import unittest
import json
import argparse
from unittest.mock import patch


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--compacto',action='store_true')
    args=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix='jarvis-banco52-r5-') as temporal:
        os.environ.update(JARVIS_DIR=temporal, JARVIS_PRUEBAS='1')
        (Path(temporal)/'trabajo').mkdir()
        from aislamiento_pruebas import instalar, verificar_previo
        instalar()
        verificar_previo(temporal, nativo=True)
        import prueba_banco52_r5 as banco

        class Resultado(unittest.TextTestResult):
            def addSuccess(self, test):
                super().addSuccess(test)
                print(json.dumps({'caso': test._testMethodName, 'ok': True}), flush=True)

            def addFailure(self, test, error):
                super().addFailure(test, error)
                print(json.dumps({'caso': test._testMethodName, 'fallo': str(error[1])}), flush=True)

            def addError(self, test, error):
                super().addError(test, error)
                print(json.dumps({'caso': test._testMethodName, 'error': str(error[1])}), flush=True)

        import jarvis_agente as J,prompt_jarvis as P
        original=J.prompt_para_turno
        def propuesto(pedido,estado=None,compacto=False):return original(pedido,estado,compacto=True)
        with patch.object(J,'SISTEMA',P.COMPACTO if args.compacto else J.SISTEMA),patch.object(J,'prompt_para_turno',propuesto if args.compacto else original):
            resultado = unittest.TextTestRunner(verbosity=0, resultclass=Resultado).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(banco.Pruebas))
        return 0 if resultado.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
