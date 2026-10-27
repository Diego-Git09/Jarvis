import json
import tempfile
import unittest
from pathlib import Path
from cargar_vocabulario import cargar

class Pruebas(unittest.TestCase):
    def test_ediciones_invalidas_no_se_sobrescriben(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);base={'acciones':{'leer':['lee']},'version':1};(p/'vocabulario_base.json').write_text(json.dumps(base))
            for t in ['{','{}','{"acciones":{"leer":[]},"version":1}','{"acciones":{"leer":[123]},"version":1}']:
                with self.subTest(t=t):
                    f=p/'vocabulario.json';f.write_text(t)
                    with self.assertWarns(RuntimeWarning):self.assertEqual(cargar('vocabulario.json',p),base)
                    self.assertEqual(f.read_text(),t)
    def test_variante_valida_cargada(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'vocabulario_base.json').write_text('{"leer":["lee"]}');(p/'vocabulario.json').write_text('{"leer":["lee","leeme"]}')
            self.assertEqual(cargar('vocabulario.json',p)['leer'],['lee','leeme'])
if __name__=='__main__':unittest.main()
