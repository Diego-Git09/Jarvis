import unittest
import consulta_textual as T
import apoyo_conceptual as A
class Pruebas(unittest.TestCase):
    def test_abreviacion_no_se_define_como_el_objeto(self):
        p='q significa guardadon automatico de un documento no guardes nada ahora'
        s=T.sistema(p)
        self.assertIn('guardar automáticamente',s.casefold());self.assertIn('que significa',s)
    def test_contexto_no_equivale_a_caracteres(self):
        s=A.contexto('q significa lmite de contexto en una ia');self.assertIn('tokens',s);self.assertIn('no caracteres',s)
    def test_explicacion_automatica_no_es_orden_de_cambio(self):
        s=A.contexto('elegir un modelo de forma aotumatica');self.assertIn('qwen3:8b',s);self.assertIn('no cambia',s)
    def test_fechas_y_rutas_no_reciben_ejemplos_del_equipo(self):
        self.assertIn('instantes distintos',A.contexto('una fecha sin zona horaria'))
        self.assertIn('notas/archivo.txt',A.contexto('ruta relativa y absoluta'))
        self.assertIn('no es un ejemplo de ruta relativa',A.contexto('ruta relativa'))
    def test_conceptual_no_anula_acceso_a_recuerdos_o_escritura(self):
        for p in ['explicame mi recuerdo 1','que significa el recuerdo 2','explica Segundo Cerebro','explicame mis archivos','explica una variable y luego guarda un recuerdo','explicame que pide','explicame esto']:
            self.assertFalse(T.aplica(p),p)
        self.assertTrue(T.aplica('explicame para que sirve una variable booleana'))
if __name__=='__main__':unittest.main()
