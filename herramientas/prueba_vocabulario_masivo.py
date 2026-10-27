import json
from pathlib import Path
import unittest
from corpus_vocabulario_nuevo import comprobar

CASOS=json.loads((Path(__file__).resolve().parent.parent/'documentacion/CORPUS_VOCABULARIO_NUEVO_2026-10-14.json').read_text())['frases']
class Pruebas(unittest.TestCase):pass
for c in CASOS:setattr(Pruebas,f'test_frase_{c["id"]:03d}',lambda self,c=c:self.assertTrue(comprobar(c)))
if __name__=='__main__':unittest.main()
