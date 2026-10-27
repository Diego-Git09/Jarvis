import unittest
from evaluar_intenciones_r3 import evaluar,corpus,variantes

class Pruebas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=evaluar()
    def test_cada_intencion_supera_meta(self):
        for nombre,c in self.r['por_intencion'].items():self.assertGreaterEqual(c['porcentaje'],95,nombre)
    def test_cada_categoria_supera_meta(self):
        for nombre,c in self.r['por_categoria'].items():self.assertGreaterEqual(c['porcentaje'],95,nombre)
    def test_cobertura_minima_no_cuenta_duplicados(self):
        self.assertGreaterEqual(len(corpus()),300)
        for nombre in self.r['por_intencion']:
            unicas={f for x in corpus() if x['intencion']==nombre for f in variantes(x['frase']).values()}
            self.assertGreaterEqual(len(unicas),25,nombre)

if __name__=='__main__':unittest.main()
