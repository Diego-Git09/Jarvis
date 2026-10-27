import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import planes_archivos as P
import herramientas_lectura as L
import herramientas_escritura as E

class Pruebas(unittest.TestCase):
    def test_renombrar_explicito_es_movimiento_con_diff(self):
        self.assertEqual(P.interpretar('/renombrar uno.txt dos.txt',None),('mover_archivo',{'origen':'uno.txt','destino':'dos.txt'}))
    def test_renombrar_comparte_controles_del_plan(self):
        with tempfile.TemporaryDirectory() as d:
            raiz=Path(d);(raiz/'uno.txt').write_text('literal q\n')
            with patch.object(L,'_resolver',side_effect=lambda x:raiz/x if not Path(x).is_absolute() else Path(x)):
                pasos=P.preparar(['copia uno.txt a copia.txt','renombra la copia a nueva.txt'])
            self.assertEqual(pasos[1]['nombre'],'mover_archivo');self.assertIn('nueva.txt',pasos[1]['diff']);self.assertTrue(pasos[1]['antes'])

if __name__=='__main__':unittest.main()
