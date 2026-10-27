import unittest
from unittest.mock import Mock,patch
import ordenes_compuestas as O
import clima_jarvis as C
import analisis_registros as R
import consulta_textual as T
class Pruebas(unittest.TestCase):
    def test_dos_preguntas_no_son_plan(self):
        for p in ['dame una ventaja de sqlite y luego una limitacion para muchos escritores','dime que es una pila y luego una cola']:
            self.assertEqual(O.separar(p),[])
        self.assertEqual(len(O.separar('copia a.txt b.txt y luego renombra b.txt c.txt')),2)
    def test_condicional_meteorologico_no_es_consulta_clima(self):
        self.assertIsNone(C.interpretar_clima('muestrame el ejemplo de una condicion si llueve llevo paraguas solo explicalo'))
        self.assertIsNotNone(C.interpretar_clima('puedes verificar el clima en Santiago mañana'))
    def test_log_tipo_no_inventa_comando_ni_archivo(self):
        t=R.explicar('cuenta@maquina:~$ programa\nERROR: expected integer, received text')
        self.assertIn('número entero',t);self.assertNotIn('leer_archivo',t);self.assertIn('no permite saber',t)
    def test_borrado_pegado_no_afirma_que_la_ruta_no_existe(self):
        t=R.explicar('cuenta@maquina:~$ rm -rf /ruta/ficticia\n[registro]')
        self.assertIn('No se puede saber',t);self.assertIn('No ejecuté',t)
    def test_falta_de_validacion_no_acredita_falsedad(self):
        p='Encuentra la contradicción. [Adjunto: ficha]\nFuente A: 14 cajas. Fuente B: 19 cajas. No se ha validado ninguna.'
        self.assertTrue(T.incumplimientos(p,'Ambas afirmaciones son incorrectas porque no se ha validado ninguna. 14 frente a 19.'))
        self.assertFalse(T.incumplimientos(p,'Hay 14 frente a 19 cajas. Falta verificar cuál fuente es correcta.'))
    def test_codigo_python_sin_funcion_rechazado(self):
        p='Escribe una función Python que devuelva el mayor de una lista, sin ejecutarla.'
        self.assertTrue(T.incumplimientos(p,'Falta un catálogo de herramientas'))
        self.assertFalse(T.incumplimientos(p,'def mayor(lista):\n    return max(lista)'))
    def test_analizar_registro_no_llama_modelo_ni_herramientas(self):
        import jarvis_agente as J
        h=[{'role':'user','content':'cuenta@maquina:~$ python ejemplo.py\nZeroDivisionError: division by zero'}]
        enviar=Mock(side_effect=AssertionError('No inferencia'));e={}
        r=J.responder_con_respaldo(h,enviar,lambda _:self.fail('No permiso de escritura'),e)
        self.assertIn('dividir por cero',r);enviar.assert_not_called();self.assertEqual(h[-1]['content'],r)
if __name__=='__main__':unittest.main()
