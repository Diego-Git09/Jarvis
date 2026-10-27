import io
import unittest
from unittest.mock import patch
from calculos_jarvis import calcular,presentar
from entrada_jarvis import leer_pregunta,TextoPegado,MAX_PEGADO
import jarvis_agente as J


class Pruebas(unittest.TestCase):
    def test_completar_rutas_respeta_espacios_y_carpeta(self):
        import tempfile
        from pathlib import Path
        from entrada_jarvis import completar_rutas
        with tempfile.TemporaryDirectory() as carpeta,patch.object(J.L,'RAIZ',Path(carpeta)):
            (Path(carpeta)/'mis notas.txt').write_text('x')
            self.assertEqual(completar_rutas('mis','/leer mis',6),["'mis notas.txt'"])
            self.assertEqual(completar_rutas('../','/leer ../',6),[])
            self.assertEqual(completar_rutas('mis','/buscar mis',8),[])
    def test_calculos_reales_decimales_porcentajes_y_funciones(self):
        for expresion,esperado in [('(12 + 8) * 3',60),('1,5 + 2,5',4),('15% de 200',30),('raiz(81)',9),('abs(-3)',3),('2^10',1024),('7 // 2',3),('7 % 2',1),('8 ÷ 2',4)]:
            self.assertAlmostEqual(calcular(expresion)['resultado'],esperado)
        self.assertEqual(presentar(calcular('0.1 + 0.2')),'0.1 + 0.2 = 0.3')

    def test_calculos_no_ejecutan_codigo_ni_acceden_a_atributos(self):
        for expresion in ["__import__('os').system('echo malo')",'(1).__class__','[1,2]','True + 1','open("archivo")','sum([1,2])','(lambda:1)()','x+1']:
            with self.assertRaises(ValueError):calcular(expresion)

    def test_limites_errores_y_resultados_no_reales(self):
        for expresion in ['1/0','2**100000','1e100 * 100','(-1)**0.5','raiz(-1)','x'*501,'1+'*50+'1','']:
            with self.assertRaises(ValueError):calcular(expresion)

    def test_pegar_conserva_lineas_y_no_ejecuta_accesos(self):
        cola=iter(['/pegar','compara esto','/mover a.txt b.txt','','final','/fin'])
        p=leer_pregunta(lambda _:next(cola),lambda _:None)
        self.assertIsInstance(p,TextoPegado);self.assertEqual(p,'compara esto\n/mover a.txt b.txt\n\nfinal')

    def test_pegar_cancelado_e_interrumpido(self):
        cola=iter(['/pegar','no enviar','/cancelar'])
        self.assertEqual(leer_pregunta(lambda _:next(cola),lambda _:None),'')
        with patch('builtins.print'):
            respuestas=iter(['/pegar'])
            def entrada(_):
                try:return next(respuestas)
                except StopIteration:raise KeyboardInterrupt
            self.assertEqual(leer_pregunta(entrada,lambda _:None),'')

    def test_pegar_grande_descarta_tambien_las_lineas_restantes(self):
        cola=iter(['/pegar','x'*(MAX_PEGADO+1),'/mover a b','/fin','/hora'])
        self.assertEqual(leer_pregunta(lambda _:next(cola),lambda _:None),'')
        self.assertEqual(leer_pregunta(lambda _:next(cola),lambda _:None),'/hora')

    def test_permiso_ambiguo_no_es_si_y_se_aclara(self):
        with patch('builtins.input',side_effect=['quizás','sí']),patch('sys.stdout',new_callable=io.StringIO) as salida:
            self.assertTrue(J.confirmar_en_terminal('Escribir archivo'))
        self.assertIn('todavía no lo autorizaste',salida.getvalue())
        for respuestas in (['no'],['no autorizo'],['tal vez']*3):
            with patch('builtins.input',side_effect=respuestas),patch('sys.stdout',new_callable=io.StringIO):
                self.assertFalse(J.confirmar_en_terminal('Escribir archivo'))


if __name__=='__main__':unittest.main()
